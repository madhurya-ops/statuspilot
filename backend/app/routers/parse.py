"""File upload -> plain transcript text."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.config import Settings, get_settings
from app.ingest.lines import normalize_text
from app.ingest.parse import ALLOWED_EXTENSIONS, parse_upload
from app.models import ParseResponse
from app.security import require_access_code

log = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"], dependencies=[Depends(require_access_code)])


@router.post("/api/parse", response_model=ParseResponse)
async def parse(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> ParseResponse:
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"File is {len(data):,} bytes; the limit is "
                f"{settings.max_upload_bytes:,}."
            ),
        )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="That file is empty."
        )

    raw = parse_upload(file.filename or "", data)
    text, truncated = normalize_text(raw, settings.max_input_chars)
    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No readable text was found in that file.",
        )

    # Sizes and outcomes only — never the transcript itself (Hard Rule 5).
    log.info(
        "parse ext=%s bytes=%d chars=%d truncated=%s",
        (file.filename or "").rsplit(".", 1)[-1].lower(),
        len(data),
        len(text),
        truncated,
    )
    return ParseResponse(text=text, chars=len(text), truncated=truncated)


@router.get("/api/parse/formats", response_model=list[str])
def formats() -> list[str]:
    """What the upload control should accept."""
    return sorted(ALLOWED_EXTENSIONS)
