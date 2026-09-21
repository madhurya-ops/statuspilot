"""Groq provider, via the OpenAI-compatible endpoint.

Structured output uses `response_format: json_schema` with `strict: true`, which
Phase 0 verified on every candidate model. There is deliberately no "JSON mode plus
schema in the prompt" fallback branch — it was dead code.
"""

import json
import logging
import time
from typing import Any, TypeVar

import httpx
from openai import APIStatusError, AsyncOpenAI
from openai import RateLimitError as OpenAIRateLimit
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.llm.base import JSONInvalid, LLMError, RateLimited
from app.models import LLMUsage

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
REQUEST_TIMEOUT_S = 45.0

# Explicit, because the provider default truncated extraction mid-document and
# returned 400 json_validate_failed rather than a short answer.
#
# But keep it TIGHT. Groq counts `max_completion_tokens` against the tokens-per-minute
# limit as *requested* tokens, not as tokens actually used: a 429 body reads
# "Limit 8000, Used 5645, Requested 5274". Reserving 6000 for a ~2500-token prompt
# therefore needs 8500 against an 8000/min ceiling, so a single request could exceed
# the budget on its own. Measured extraction output is ~1700-2800 tokens, so 3200
# leaves headroom without reserving budget we never spend.
MAX_COMPLETION_TOKENS = {"extract": 3200, "generate": 2500}
DEFAULT_MAX_COMPLETION_TOKENS = 2500


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
        self, *, system: str, user: str, schema_model: type[T], stage: str
    ) -> tuple[T, LLMUsage]:
        started = time.monotonic()
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                reasoning_effort=self._effort(stage),
                max_completion_tokens=MAX_COMPLETION_TOKENS.get(
                    stage, DEFAULT_MAX_COMPLETION_TOKENS
                ),
                response_format=strict_schema(schema_model),
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except OpenAIRateLimit as err:
            raise RateLimited(
                "Groq rate limit", status=429, retry_after=_retry_after(err)
            ) from err
        except APIStatusError as err:
            if err.status_code == 429:
                raise RateLimited(
                    "Groq rate limit", status=429, retry_after=_retry_after(err)
                ) from err
            raise LLMError(
                f"Groq returned {err.status_code}: {_error_code(err)}",
                status=err.status_code,
            ) from err
        except httpx.TimeoutException as err:
            raise LLMError("Groq request timed out") from err

        elapsed_ms = int((time.monotonic() - started) * 1000)
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
                "groq output truncated at the completion cap stage=%s model=%s out=%d",
                stage,
                self._model,
                usage.output_tokens,
            )

        content = choice.message.content or ""
        # Sizes and outcomes only. Never the prompt, never the completion.
        log.info(
            "groq model=%s stage=%s in=%d out=%d ms=%d finish=%s",
            self._model,
            stage,
            usage.input_tokens,
            usage.output_tokens,
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
    body = getattr(err, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            return str(error.get("code") or error.get("type") or "unknown")
    return "unknown"


def _retry_after(err: Exception) -> float | None:
    headers = getattr(getattr(err, "response", None), "headers", None)
    if not headers:
        return None
    raw = headers.get("retry-after")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None
