"""Retry and escalation policy.

Two failure paths that must never be conflated:

  429 / 5xx (rate limit)   -> back off on the SAME model, up to 3 attempts.
                              Never escalate: Phase 0 measured that both Groq models
                              draw on one shared 8k tokens/min bucket, so swapping
                              model for a rate limit buys nothing at all.

  Schema failure (quality)  -> one repair retry on the primary model, then escalate
                              to GROQ_MODEL_ESCALATION. This is the only thing the
                              second model exists for.
"""

import asyncio
import logging
from typing import TypeVar

from pydantic import BaseModel

from app.config import Settings
from app.llm.base import (
    JSONInvalid,
    LLMError,
    LLMProvider,
    RateLimited,
    Transient,
    Truncated,
)
from app.llm.groq_client import COMPLETION_CEILING, GroqProvider
from app.llm.mock import MockProvider
from app.models import LLMUsage

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

BACKOFF_SECONDS = (1.0, 2.0, 4.0)
MAX_RATE_LIMIT_ATTEMPTS = 3

# Never sleep longer than this inside a request, however long `retry-after` asks for.
#
# Groq returned `retry-after: 612` during a cache build and the router honoured it
# literally, stalling for ten minutes with no output. On Vercel that is worse than a
# stall: `maxDuration` is 60 s, so the function would be killed mid-sleep and the user
# would get a timeout instead of an explanation. Beyond this ceiling the wait is no
# longer something to sit through — it is something to tell the user about.
MAX_BACKOFF_SECONDS = 30.0

REPAIR_HINT = (
    "\n\nYour previous response did not match the required JSON schema. "
    "Return only valid JSON matching the schema exactly, with no commentary."
)


def build_provider(settings: Settings, model: str | None = None) -> LLMProvider:
    if settings.llm_primary == "mock":
        return MockProvider(settings)
    return GroqProvider(settings, model=model)


class LLMRouter:
    """Wraps a provider with the retry and escalation policy above."""

    def __init__(self, settings: Settings, sleep=asyncio.sleep):
        self._settings = settings
        self._sleep = sleep  # injectable so tests do not actually wait

    async def complete_json(
        self, *, system: str, user: str, schema_model: type[T], stage: str
    ) -> tuple[T, LLMUsage]:
        settings = self._settings
        attempts = 0
        totals = LLMUsage(model=settings.groq_model)

        for model, is_escalation in (
            (settings.groq_model, False),
            (settings.groq_model_escalation, True),
        ):
            provider = build_provider(settings, model=model)
            prompt = user if not is_escalation else user + REPAIR_HINT
            schema_failures = 0
            forced_cap: int | None = None

            while True:
                attempts += 1
                try:
                    parsed, usage = await provider.complete_json(
                        system=system,
                        user=prompt,
                        schema_model=schema_model,
                        stage=stage,
                        max_completion_tokens=forced_cap,
                    )
                except Transient as err:
                    # Timeouts and 5xx are worth one more attempt on the same model.
                    if attempts >= MAX_RATE_LIMIT_ATTEMPTS:
                        log.warning("groq transient failure, giving up after %d", attempts)
                        raise
                    delay = BACKOFF_SECONDS[min(attempts - 1, len(BACKOFF_SECONDS) - 1)]
                    log.warning(
                        "groq transient (%s) stage=%s attempt=%d backoff=%.1fs",
                        err,
                        stage,
                        attempts,
                        delay,
                    )
                    await self._sleep(delay)
                    continue
                except RateLimited as err:
                    # Same model, always. Escalating here would spend the same bucket.
                    if attempts >= MAX_RATE_LIMIT_ATTEMPTS:
                        log.warning("groq rate limited, giving up after %d attempts", attempts)
                        raise
                    delay = err.retry_after or BACKOFF_SECONDS[
                        min(attempts - 1, len(BACKOFF_SECONDS) - 1)
                    ]
                    if delay > MAX_BACKOFF_SECONDS:
                        # Surface it rather than sleep through it. `retry_after` is
                        # carried on the exception so the UI can show a real figure.
                        log.warning(
                            "groq asked for a %.0fs wait; surfacing instead of sleeping",
                            delay,
                        )
                        raise
                    log.warning(
                        "groq 429 stage=%s attempt=%d backoff=%.1fs", stage, attempts, delay
                    )
                    await self._sleep(delay)
                    continue
                except Truncated:
                    # The dynamic cap under-estimated this response. Retry once at the
                    # ceiling rather than reserving the ceiling on every call: a rare
                    # retry is cheaper than permanent over-reservation, and truncation
                    # is invisible otherwise because the JSON still parses.
                    if forced_cap is None:
                        forced_cap = COMPLETION_CEILING.get(stage, 2500)
                        log.warning(
                            "groq truncated stage=%s, retrying at the ceiling cap %d",
                            stage,
                            forced_cap,
                        )
                        continue
                    log.warning("groq truncated stage=%s even at the ceiling cap", stage)
                    raise
                except JSONInvalid:
                    schema_failures += 1
                    if schema_failures == 1 and not is_escalation:
                        log.warning("groq schema failure stage=%s, repairing on same model", stage)
                        prompt = user + REPAIR_HINT
                        continue
                    log.warning(
                        "groq schema failure stage=%s model=%s, %s",
                        stage,
                        model,
                        "escalating" if not is_escalation else "no further fallback",
                    )
                    break  # move to the escalation model, or out of the loop
                except LLMError:
                    raise

                totals = LLMUsage(
                    model=usage.model,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    latency_ms=usage.latency_ms,
                    attempts=attempts,
                    escalated=is_escalation,
                    # Must be propagated: under strict json_schema a truncated
                    # response still parses, because the constrained decoder closes
                    # the JSON. Candidates are then silently lost and the only
                    # evidence is this field.
                    finish_reason=usage.finish_reason,
                )
                return parsed, totals

        raise JSONInvalid(
            "The model could not produce valid JSON, even after escalating to "
            f"{settings.groq_model_escalation}."
        )
