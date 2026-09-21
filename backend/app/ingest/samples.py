"""Loader for the bundled synthetic transcripts.

Vercel's Python runtime sets the working directory to the project root, not to the
directory of the module being executed, so every path here is built from `__file__`.
A relative `open("app/samples/...")` works locally and 500s in production.
"""

import json
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, status

from app.models import SampleDetail, SampleSummary

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
INDEX_PATH = SAMPLES_DIR / "index.json"


@lru_cache
def _index() -> dict[str, dict[str, str]]:
    entries = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in entries}


def _read(entry: dict[str, str]) -> str:
    path = SAMPLES_DIR / entry["filename"]
    # Defend against a traversal via a hand-edited index.json.
    if path.parent != SAMPLES_DIR:
        raise HTTPException(status_code=500, detail="Invalid sample configuration.")
    return path.read_text(encoding="utf-8")


def list_samples() -> list[SampleSummary]:
    return [
        SampleSummary(
            id=entry["id"],
            title=entry["title"],
            description=entry["description"],
            chars=len(_read(entry)),
        )
        for entry in _index().values()
    ]


def get_sample(sample_id: str) -> SampleDetail:
    entry = _index().get(sample_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No sample with id '{sample_id}'.",
        )
    text = _read(entry)
    return SampleDetail(
        id=entry["id"],
        title=entry["title"],
        description=entry["description"],
        chars=len(text),
        text=text,
    )
