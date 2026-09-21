"""POST /api/generate — approved items to finished documents."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.llm.base import LLMError, RateLimited
from app.llm.router import LLMRouter
from app.models import Documents, GenerateRequest
from app.pipeline import cache as cache_module
from app.pipeline.generate import run_generation
from app.security import require_access_code

log = logging.getLogger(__name__)

router = APIRouter(tags=["pipeline"], dependencies=[Depends(require_access_code)])


@router.post("/api/generate", response_model=Documents)
async def generate(
    payload: GenerateRequest,
    settings: Settings = Depends(get_settings),
) -> Documents:
    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There are no approved items to write up.",
        )
    try:
        documents, usage = await run_generation(
            payload=payload, provider=LLMRouter(settings), settings=settings
        )
    except RateLimited as err:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "The free-tier token budget is still refilling. "
                "Please try again in a moment."
            ),
            headers={"Retry-After": str(int(err.retry_after or 20))},
        ) from err
    except LLMError as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The model provider is unavailable. Please try again.",
        ) from err
    return documents


@router.get("/api/cached/{sample_id}", response_model=dict)
def cached_run(
    sample_id: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    """The full precomputed run for a bundled sample, or 404 if there is none."""
    if not settings.cached_samples:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sample cache is disabled."
        )
    loaded = cache_module.load(sample_id)
    if loaded is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No cached run for '{sample_id}'.",
        )
    documents = loaded["documents"]
    documents.cached = True
    return {
        "cached": True,
        "sample_id": sample_id,
        "extract": loaded["extract"].model_dump(),
        "classify": loaded["classify"].model_dump(),
        "documents": documents.model_dump(),
    }


@router.post("/api/cached/lookup", response_model=dict)
def cached_lookup(
    payload: dict,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Does this exact text match a bundled sample that has a cached run?

    Matching is on a hash of the **normalised** text, not on a sample id, so pasting a
    sample's text hits the cache too. Anything else goes live.
    """
    text = str(payload.get("text", ""))
    if not settings.cached_samples or not text.strip():
        return {"cached": False, "sample_id": None}
    sample_id = cache_module.lookup_id(text)
    if sample_id and cache_module.has_cache(sample_id):
        return {"cached": True, "sample_id": sample_id}
    return {"cached": False, "sample_id": None}
