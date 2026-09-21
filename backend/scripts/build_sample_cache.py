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
        extracted, _ = await run_extraction(
            text=text, lines=lines, provider=LLMRouter(settings), settings=settings
        )
        classified = await run_classification(extracted=extracted, settings=settings)
        documents, _ = await run_generation(
            payload=GenerateRequest(
                meta=extracted.meta,
                discussion_points=extracted.discussion_points,
                items=approve_all(classified),
                rag=classified.rag,
                project_name=None,
                reporting_period=None,
            ),
            provider=LLMRouter(settings),
            settings=settings,
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
