#!/usr/bin/env python
"""Build the precomputed runs for the bundled samples.

Run this deliberately, never on request:

    cd backend && ./.venv/bin/python scripts/build_sample_cache.py

It spends real Groq and Jev tokens, so it paces itself: a full report requests
~11,500 tokens against an 8,000/min ceiling, and this does three of them.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.ingest.lines import normalize_text, to_lines  # noqa: E402
from app.ingest.samples import get_sample, list_samples  # noqa: E402
from app.llm.base import RateLimited  # noqa: E402
from app.llm.router import LLMRouter  # noqa: E402
from app.models import ApprovedItem, GenerateRequest  # noqa: E402
from app.pipeline import cache as cache_module  # noqa: E402
from app.pipeline.classify import run_classification  # noqa: E402
from app.pipeline.extract import run_extraction  # noqa: E402
from app.pipeline.generate import run_generation  # noqa: E402

PACE_SECONDS = 95


def approve_all(classified) -> list[ApprovedItem]:
    """Accept every item as the PM would after review.

    The cached run represents "the PM accepted the defaults", which is what a demo
    tap-through produces.
    """
    return [
        ApprovedItem(
            id=item.candidate.id,
            text=item.candidate.text,
            kind=item.kind.label,
            severity=item.severity.label,
            severity_value=item.severity_value,
            audience=item.audience.label,
            owner=item.candidate.owner,
            owner_status=item.owner_status,
            due_date=item.candidate.due_date,
            due_status=item.due_status,
            source_lines=item.candidate.source_lines,
            edited_by_user=False,
        )
        for item in classified.items
    ]


async def with_patience(label: str, factory):
    """Run a stage, waiting out a long rate-limit window **visibly**.

    The router refuses to sleep more than 30 s inside a request, because on Vercel a
    longer sleep is a killed function rather than a wait. This script is offline
    tooling, so here a long wait is fine — but it must announce itself. A silent
    ten-minute stall is what made an earlier build look hung.
    """
    for attempt in range(1, 4):
        try:
            return await factory()
        except RateLimited as err:
            wait = min(float(err.retry_after or 60.0), 660.0) + 2.0
            print(
                f"   {label}: rate limited, waiting {wait:.0f}s (attempt {attempt}/3)",
                flush=True,
            )
            await asyncio.sleep(wait)
    raise SystemExit(f"{label}: still rate limited after 3 waits")


async def main() -> int:
    settings = get_settings()
    if settings.llm_primary != "groq" or settings.decision_engine != "jev":
        print(f"Refusing to build a cache from {settings.llm_primary}/{settings.decision_engine}.")
        print("Set LLM_PRIMARY=groq and DECISION_ENGINE=jev.")
        return 1

    samples = list_samples()
    for index, summary in enumerate(samples):
        detail = get_sample(summary.id)
        text, _ = normalize_text(detail.text, settings.max_input_chars)
        lines = to_lines(text)

        started = time.monotonic()
        print(f"{summary.id}: extracting...", flush=True)
        extracted, _ = await with_patience(
            summary.id,
            lambda t=text, ln=lines: run_extraction(
                text=t, lines=ln, provider=LLMRouter(settings), settings=settings
            ),
        )
        print(f"{summary.id}: classifying {len(extracted.candidates)} candidates...", flush=True)
        classified = await run_classification(extracted=extracted, settings=settings)
        print(f"{summary.id}: generating...", flush=True)
        documents, _ = await with_patience(
            summary.id,
            lambda ex=extracted, cl=classified: run_generation(
                payload=GenerateRequest(
                    meta=ex.meta,
                    discussion_points=ex.discussion_points,
                    items=approve_all(cl),
                    rag=cl.rag,
                    project_name=None,
                    reporting_period=None,
                ),
                provider=LLMRouter(settings),
                settings=settings,
            ),
        )
        documents.cached = True
        path = cache_module.save(summary.id, extracted, classified, documents)
        elapsed = time.monotonic() - started

        review = sum(1 for i in classified.items if i.routing == "review")
        print(
            f"{summary.id:26} items={len(classified.items):3} review={review:3} "
            f"RAG={classified.rag.status:5} empty_report={documents.status_report_empty} "
            f"{elapsed:.1f}s -> {path.name}"
        )
        if index < len(samples) - 1:
            print(f"   pacing {PACE_SECONDS}s for the token bucket")
            await asyncio.sleep(PACE_SECONDS)

    cache_module._index.cache_clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
