#!/usr/bin/env python
"""Rebuild the cached run for ONE sample.

Writes to a temporary path and swaps only on success, so the committed cache is
never removed before a working replacement exists. (An earlier rebuild deleted the
good cache first and left nothing when the build failed.)

    ./.venv/bin/python scripts/rebuild_one_sample.py northwind-sprint-review
"""

import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.ingest.lines import normalize_text, to_lines  # noqa: E402
from app.ingest.samples import get_sample  # noqa: E402
from app.llm.router import LLMRouter  # noqa: E402
from app.models import GenerateRequest  # noqa: E402
from app.pipeline import cache as cache_module  # noqa: E402
from app.pipeline.classify import run_classification  # noqa: E402
from app.pipeline.extract import run_extraction  # noqa: E402
from app.pipeline.generate import run_generation  # noqa: E402
from scripts.build_sample_cache import approve_all  # noqa: E402


async def main(sample_id: str) -> int:
    settings = get_settings()
    if settings.llm_primary != "groq" or settings.decision_engine != "jev":
        print("Refusing to rebuild from mock engines.")
        return 1

    target = cache_module.CACHE_DIR / f"{sample_id}.json"
    backup = target.with_suffix(".json.previous")
    if target.is_file():
        shutil.copy2(target, backup)
        print(f"kept the current cache at {backup.name}")

    detail = get_sample(sample_id)
    text, _ = normalize_text(detail.text, settings.max_input_chars)
    lines = to_lines(text)

    print(f"{sample_id}: extracting...", flush=True)
    extracted, ex_usage = await run_extraction(
        text=text, lines=lines, provider=LLMRouter(settings), settings=settings
    )
    print(f"{sample_id}: classifying {len(extracted.candidates)} candidates...", flush=True)
    classified = await run_classification(extracted=extracted, settings=settings)
    print(f"{sample_id}: generating...", flush=True)
    documents, gen_usage = await run_generation(
        payload=GenerateRequest(
            meta=extracted.meta,
            discussion_points=extracted.discussion_points,
            items=approve_all(classified),
            rag=classified.rag,
        ),
        provider=LLMRouter(settings),
        settings=settings,
    )
    documents.cached = True
    cache_module.save(sample_id, extracted, classified, documents)
    cache_module._index.cache_clear()

    review = sum(1 for i in classified.items if i.routing == "review")
    groq = (
        ex_usage.input_tokens + ex_usage.output_tokens
        + gen_usage.input_tokens + gen_usage.output_tokens
    )
    print(
        f"\n{sample_id}: candidates={len(extracted.candidates)} items={len(classified.items)} "
        f"review={review} RAG={classified.rag.status}"
    )
    print(f"  Groq consumed: {groq:,}")
    print(f"  previous draw kept at {backup.name} — delete it once you are happy")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1])))
