"""Precomputed results for the three bundled samples.

Phase 4 measured a full report at ~11,500 **requested** tokens against an 8,000/min
ceiling, so a live run cannot complete inside one minute. During a demo that is a
429 in front of an audience. The bundled samples therefore serve committed results.

Two rules keep this honest:
  * The response is flagged `cached: true` and the UI labels it visibly. It is never
    passed off as live.
  * Only the bundled samples hit the cache. Pasted or uploaded text always goes live,
    so the live path is provable with the audience's own text.
"""

import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.ingest.lines import normalize_text
from app.ingest.samples import SAMPLES_DIR, get_sample, list_samples
from app.models import ClassifyResponse, Documents, ExtractResponse

log = logging.getLogger(__name__)

CACHE_DIR = SAMPLES_DIR / "cached"


def fingerprint(text: str) -> str:
    """Hash of the **normalised** text.

    Normalised, not the sample id, so pasting a sample's text into the box also hits
    the cache — the PM should not get a different experience for the same content.
    """
    normalised, _ = normalize_text(text, 10_000_000)
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:16]


@lru_cache
def _index() -> dict[str, str]:
    """fingerprint -> sample id, for every bundled sample."""
    out: dict[str, str] = {}
    for summary in list_samples():
        out[fingerprint(get_sample(summary.id).text)] = summary.id
    return out


def lookup_id(text: str) -> str | None:
    return _index().get(fingerprint(text))


def _path(sample_id: str) -> Path:
    return CACHE_DIR / f"{sample_id}.json"


def has_cache(sample_id: str) -> bool:
    return _path(sample_id).is_file()


def load(sample_id: str) -> dict[str, Any] | None:
    """Load a cached run, validating it against the **live** models.

    Validation is the point: a schema change in a later phase must fail loudly here
    rather than quietly serving a stale shape to the UI.
    """
    path = _path(sample_id)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {
            "extract": ExtractResponse.model_validate(raw["extract"]),
            "classify": ClassifyResponse.model_validate(raw["classify"]),
            "documents": Documents.model_validate(raw["documents"]),
        }
    except (KeyError, ValidationError, json.JSONDecodeError) as err:
        log.warning(
            "cached sample %s no longer matches the current schema (%s); ignoring it",
            sample_id,
            type(err).__name__,
        )
        return None


def save(sample_id: str, extract, classify, documents) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _path(sample_id)
    path.write_text(
        json.dumps(
            {
                "extract": extract.model_dump(),
                "classify": classify.model_dump(),
                "documents": documents.model_dump(),
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    return path
