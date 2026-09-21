"""POST /api/extract — transcript text to candidate items."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.ingest.lines import normalize_text, to_lines
from app.llm.base import JSONInvalid, LLMError, RateLimited
from app.llm.router import LLMRouter
from app.models import ExtractResponse
from app.pipeline.extract import run_extraction
from app.security import require_access_code

log = logging.getLogger(__name__)

router = APIRouter(tags=["pipeline"], dependencies=[Depends(require_access_code)])

MIN_INPUT_CHARS = 200


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1)


@router.post("/api/extract", response_model=ExtractResponse)
async def extract(
    payload: ExtractRequest,
    settings: Settings = Depends(get_settings),
) -> ExtractResponse:
    text, truncated = normalize_text(payload.text, settings.max_input_chars)
    if len(text) < MIN_INPUT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Transcript is too short to summarise "
                f"(minimum {MIN_INPUT_CHARS} characters)."
            ),
        )
    lines = to_lines(text)

    try:
        result, usage = await run_extraction(
            text=text, lines=lines, provider=LLMRouter(settings), settings=settings
        )
    except RateLimited as err:
        # Surfaced as a clean "busy" state, never a stack trace. The router has
        # already backed off; a 429 here means it genuinely could not get through.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_rate_limit_detail(err),
            headers={"Retry-After": str(int(err.retry_after or 20))},
        ) from err
    except JSONInvalid as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The model could not produce a usable result. Please try again.",
        ) from err
    except LLMError as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The model provider is unavailable. Please try again.",
        ) from err

    log.info(
        "extract chars=%d truncated=%s lines=%d candidates=%d model=%s in=%d out=%d ms=%d",
        len(text),
        truncated,
        len(lines),
        len(result.candidates),
        usage.model,
        usage.input_tokens,
        usage.output_tokens,
        usage.latency_ms,
    )
    return result


def _rate_limit_detail(err: RateLimited) -> str:
    """Two limits, two very different things to tell the user."""
    if getattr(err, "scope", "minute") == "day":
        minutes = int((err.retry_after or 0) // 60)
        when = f" It resets in about {minutes} minutes." if minutes else ""
        return (
            "The free-tier daily token budget for this project is used up."
            + when
            + " Bundled sample reports still work — they are precomputed."
        )
    seconds = int(err.retry_after or 20)
    return (
        f"The free-tier token budget is refilling — about {seconds}s. "
        "This is a rate limit, not an error."
    )
