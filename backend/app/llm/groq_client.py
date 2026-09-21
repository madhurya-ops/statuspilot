"""Groq provider, via the OpenAI-compatible endpoint.

Structured output uses `response_format: json_schema` with `strict: true`, which
Phase 0 verified on every candidate model. There is deliberately no "JSON mode plus
schema in the prompt" fallback branch — it was dead code.
"""

import contextlib
import json
import logging
import math
import time
from typing import Any, TypeVar

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from openai import RateLimitError as OpenAIRateLimit
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.llm.base import JSONInvalid, LLMError, RateLimited, Transient, Truncated
from app.models import LLMUsage

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
REQUEST_TIMEOUT_S = 45.0

# Groq charges its tokens-per-minute limit on **requested** tokens
# (`prompt + max_completion_tokens`), not consumed ones. Measured directly: one
# extraction with a 2,520-token prompt and a 4,500 cap took
# `x-ratelimit-remaining-tokens` from 7,927 to 980 — a deduction of exactly
# prompt + cap — while consuming only 5,415. A fixed cap therefore reserves, and pays
# for, tokens it never uses, and that waste directly lengthens the refill wait before
# the next call.
#
# So the cap is scaled from the prompt instead.
#
# The ratio must be generous, because a truncation retry is FAR more expensive than
# over-reserving: the retry re-requests prompt + ceiling, so one truncated extraction
# costs ~11.6k requested tokens against an 8k/min budget, versus ~6.2k for a single
# correctly-sized call. Measured completion/prompt ratios across live runs span
# 0.65-1.85 — bullet notes pack many more items per prompt token than meeting
# dialogue, and `rough-standup-notes` needed 3,804 completion tokens on a 2,060-token
# prompt. 2.0 covers the worst case with margin; `Truncated` remains as a safety net
# for anything beyond it.
COMPLETION_RATIO = {"extract": 2.0, "generate": 1.6}
COMPLETION_FLOOR = {"extract": 2000, "generate": 2000}
COMPLETION_CEILING = {"extract": 4500, "generate": 3500}

# Conservative: the worst measured density across the three samples was 3.196
# characters per token (rough-standup-notes: 6,223 chars -> 1,948 tokens). 3.1 leaves
# margin below that, so the estimate never underestimates the prompt and the cap is
# never scaled down off a too-small number.
CHARS_PER_TOKEN = 3.1


def estimate_prompt_tokens(system: str, user: str) -> int:
    return math.ceil((len(system) + len(user)) / CHARS_PER_TOKEN)


def completion_cap(stage: str, prompt_tokens: int) -> int:
    ratio = COMPLETION_RATIO.get(stage, 1.4)
    floor = COMPLETION_FLOOR.get(stage, 1200)
    ceiling = COMPLETION_CEILING.get(stage, 2500)
    return max(floor, min(ceiling, math.ceil(prompt_tokens * ratio)))


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Build a `json_schema` payload that satisfies Groq's strict mode.

    Strict mode requires every property to be listed in `required` and
    `additionalProperties: false` on every object, which pydantic does not emit by
    default for optional fields.
    """
    schema = model.model_json_schema()
    _tighten(schema, schema.get("$defs", {}))
    return {
        "type": "json_schema",
        "json_schema": {"name": model.__name__, "strict": True, "schema": schema},
    }


def _tighten(node: Any, defs: dict[str, Any]) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"].keys())
        for value in node.values():
            _tighten(value, defs)
    elif isinstance(node, list):
        for item in node:
            _tighten(item, defs)


class GroqProvider:
    def __init__(self, settings: Settings, model: str | None = None):
        self._settings = settings
        self._model = model or settings.groq_model
        self._client = AsyncOpenAI(
            api_key=settings.groq_api_key,
            base_url=GROQ_BASE_URL,
            timeout=REQUEST_TIMEOUT_S,
            max_retries=0,  # retries are the router's job, so backoff stays visible
        )

    @property
    def model(self) -> str:
        return self._model

    def _effort(self, stage: str) -> str:
        return (
            self._settings.groq_reasoning_effort_generate
            if stage == "generate"
            else self._settings.groq_reasoning_effort_extract
        )

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_model: type[T],
        stage: str,
        max_completion_tokens: int | None = None,
    ) -> tuple[T, LLMUsage]:
        started = time.monotonic()
        cap = max_completion_tokens or completion_cap(
            stage, estimate_prompt_tokens(system, user)
        )
        try:
            raw = await self._client.chat.completions.with_raw_response.create(
                model=self._model,
                temperature=0,
                reasoning_effort=self._effort(stage),
                max_completion_tokens=cap,
                response_format=strict_schema(schema_model),
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except OpenAIRateLimit as err:
            scope = _limit_scope(err)
            raise RateLimited(
                f"Groq rate limit ({scope})",
                status=429,
                retry_after=_retry_after(err),
                scope=scope,
            ) from err
        except APIStatusError as err:
            if err.status_code == 429:
                scope = _limit_scope(err)
                raise RateLimited(
                    f"Groq rate limit ({scope})",
                    status=429,
                    retry_after=_retry_after(err),
                    scope=scope,
                ) from err
            code = _error_code(err)
            # Truncation has two faces. When the constrained decoder manages to close
            # the JSON, Groq returns 200 with finish_reason="length". When it cannot,
            # it returns 400 json_validate_failed whose body says "max completion
            # tokens reached before generating a valid document". Both are the same
            # problem and both must retry at the ceiling, not surface as a dead error.
            if code == "json_validate_failed" and _mentions_truncation(err):
                raise Truncated("Response hit the completion cap (400)") from err
            if err.status_code >= 500:
                raise Transient(f"Groq returned {err.status_code}") from err
            raise LLMError(
                f"Groq returned {err.status_code}: {code}", status=err.status_code
            ) from err
        except (APITimeoutError, httpx.TimeoutException) as err:
            raise Transient("Groq request timed out") from err
        except APIConnectionError as err:
            raise Transient("Could not reach Groq") from err

        elapsed_ms = int((time.monotonic() - started) * 1000)
        _record_budget(raw.headers)
        response = raw.parse()
        choice = response.choices[0]
        usage = LLMUsage(
            model=self._model,
            input_tokens=getattr(response.usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(response.usage, "completion_tokens", 0) or 0,
            latency_ms=elapsed_ms,
            finish_reason=getattr(choice, "finish_reason", None),
        )
        if usage.finish_reason == "length":
            log.warning(
                "groq output truncated at cap=%d stage=%s model=%s out=%d",
                cap,
                stage,
                self._model,
                usage.output_tokens,
            )
            raise Truncated(f"Response hit the completion cap of {cap}")

        content = choice.message.content or ""
        # Sizes and outcomes only. Never the prompt, never the completion.
        log.info(
            "groq model=%s stage=%s in=%d out=%d cap=%d ms=%d finish=%s",
            self._model,
            stage,
            usage.input_tokens,
            usage.output_tokens,
            cap,
            elapsed_ms,
            usage.finish_reason,
        )
        try:
            parsed = schema_model.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError) as err:
            raise JSONInvalid(
                f"Model output did not satisfy the schema: {type(err).__name__}"
            ) from err
        return parsed, usage


def _error_code(err: Exception) -> str:
    """Groq's machine-readable error code, e.g. `json_validate_failed`.

    Worth surfacing: a bare "400" is indistinguishable between a malformed schema, a
    truncated document and a bad parameter, and the three need different fixes.
    Only the code and type are read — never `failed_generation`, which contains
    transcript-derived content.
    """
    for source in (getattr(err, "body", None), _json_body(err)):
        if isinstance(source, dict):
            error = source.get("error", source)
            if isinstance(error, dict):
                code = error.get("code") or error.get("type")
                if code:
                    return str(code)
    return "unknown"


def _limit_scope(err: Exception) -> str:
    """Which Groq limit was hit: the per-minute bucket or the per-day cap.

    Only the 429 body says. The `x-ratelimit-*` headers cover requests/minute,
    requests/day and tokens/minute — **not** tokens/day, so a TPD exhaustion looks
    perfectly healthy in the headers right up until it refuses every request.
    """
    for source in (getattr(err, "body", None), _json_body(err)):
        if isinstance(source, dict):
            blob = json.dumps(source).lower()
            if "per day" in blob or "tpd" in blob or "rpd" in blob:
                return "day"
    return "minute"


def _mentions_truncation(err: Exception) -> bool:
    """Does the error body blame the completion cap?"""
    for source in (getattr(err, "body", None), _json_body(err)):
        if isinstance(source, dict):
            blob = json.dumps(source).lower()
            if "max completion tokens" in blob or "max_completion_tokens" in blob:
                return True
    return False


def _json_body(err: Exception) -> Any:
    response = getattr(err, "response", None)
    if response is None:
        return None
    try:
        return response.json()
    except Exception:
        return None


def _retry_after(err: Exception) -> float | None:
    headers = getattr(getattr(err, "response", None), "headers", None)
    if not headers:
        return None
    raw = headers.get("retry-after")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


# Last rate-limit snapshot seen on any Groq response. Groq reports the remaining
# per-minute token budget on every call, so the app can tell the user exactly how long
# the next stage must wait instead of showing a bare spinner or a 429.
_BUDGET: dict[str, float] = {}


def _record_budget(headers: Any) -> None:
    if headers is None:
        return
    for key, name in (
        ("x-ratelimit-limit-tokens", "limit"),
        ("x-ratelimit-remaining-tokens", "remaining"),
    ):
        value = headers.get(key)
        if value is not None:
            with contextlib.suppress(TypeError, ValueError):
                _BUDGET[name] = float(value)
    _BUDGET["at"] = time.time()


def budget_snapshot() -> dict[str, float]:
    return dict(_BUDGET)
