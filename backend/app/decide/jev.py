"""Jev REST client.

One request per candidate carrying all item questions — the docs' speculative
fan-out: questions are independent, evaluated in parallel, and a speculative one
costs almost nothing. Requests across candidates run concurrently under a semaphore.
"""

import asyncio
import logging
import time
from typing import Any

import httpx

from app.config import Settings
from app.decide.base import DecisionError
from app.models import Decision, RunStats

log = logging.getLogger(__name__)

RETRYABLE = {429, 500, 502, 503, 504, 529}
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (0.5, 1.5, 3.0)


def parse_answer(answer: dict[str, Any]) -> Decision:
    """Turn one Jev answer into a `Decision`, whatever its type.

    Score keeps its raw float in `value` and gets no label here — banding is policy
    and lives in `routing.py`. Noul carries no confidence at all, by design.
    """
    kind = answer.get("type")
    if kind == "choice":
        return Decision(
            label=str(answer.get("choice", "")),
            confidence=_as_float(answer.get("confidence")),
            probabilities={k: float(v) for k, v in (answer.get("probabilities") or {}).items()},
        )
    if kind == "score":
        return Decision(
            label="",  # filled by routing.band_score against the question's levels
            confidence=_as_float(answer.get("confidence")),
            probabilities={k: float(v) for k, v in (answer.get("probabilities") or {}).items()},
            value=_as_float(answer.get("score")) or 0.0,
        )
    if kind == "noul":
        value = _as_float(answer.get("noul")) or 0.0
        return Decision(label="", confidence=None, probabilities=None, value=value)
    raise DecisionError(f"Unknown answer type from Jev: {kind!r}")


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class JevEngine:
    name = "jev"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._settings = settings
        self._client = client
        self._url = f"{settings.typesafe_base_url.rstrip('/')}/systemone"

    async def judge(
        self,
        states: list[dict[str, Any]],
        questions: dict[str, dict[str, Any]],
    ) -> tuple[list[dict[str, Decision]], RunStats]:
        settings = self._settings
        semaphore = asyncio.Semaphore(settings.jev_concurrency)
        started = time.monotonic()
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=settings.jev_timeout_s)

        try:
            results = await asyncio.gather(
                *[self._one(client, semaphore, state, questions) for state in states],
                return_exceptions=True,
            )
        finally:
            if owns_client:
                await client.aclose()

        answers: list[dict[str, Decision]] = []
        input_tokens = output_tokens = 0
        failures = 0
        for result in results:
            if isinstance(result, BaseException):
                failures += 1
                answers.append({})
                continue
            parsed, usage = result
            answers.append(parsed)
            input_tokens += usage.get("input_tokens", 0) or 0
            output_tokens += usage.get("output_tokens", 0) or 0

        elapsed_ms = int((time.monotonic() - started) * 1000)
        log.info(
            "jev requests=%d failures=%d concurrency=%d ms=%d in=%d out=%d",
            len(states),
            failures,
            settings.jev_concurrency,
            elapsed_ms,
            input_tokens,
            output_tokens,
        )
        if states and failures == len(states):
            # Every request failed: this is an engine-level outage, not a bad item.
            raise DecisionError("Every Jev request failed")

        return answers, RunStats(
            engine=self.name,
            requests=len(states),
            latency_ms=elapsed_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def _one(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        state: dict[str, Any],
        questions: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, Decision], dict[str, Any]]:
        payload = {
            "state": state,
            "model": self._settings.jev_model,
            "questions": questions,
        }
        headers = {"Authorization": f"Bearer {self._settings.typesafe_api_key}"}

        async with semaphore:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                response = await client.post(self._url, json=payload, headers=headers)
                if response.status_code in RETRYABLE and attempt < MAX_ATTEMPTS:
                    delay = _retry_after(response) or BACKOFF_SECONDS[attempt - 1]
                    log.warning(
                        "jev %d attempt=%d backoff=%.1fs", response.status_code, attempt, delay
                    )
                    await asyncio.sleep(delay)
                    continue
                if response.status_code != 200:
                    raise DecisionError(f"Jev returned {response.status_code}")
                body = response.json()
                return (
                    {key: parse_answer(value) for key, value in body.get("answers", {}).items()},
                    body.get("usage", {}),
                )
        raise DecisionError("Jev retries exhausted")


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None
