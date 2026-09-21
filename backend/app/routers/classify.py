"""POST /api/classify — candidates to typed judgments."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.decide.base import DecisionError
from app.llm.base import LLMError, RateLimited
from app.models import ClassifyResponse, ExtractResponse
from app.pipeline.classify import run_classification
from app.security import require_access_code

log = logging.getLogger(__name__)

router = APIRouter(tags=["pipeline"], dependencies=[Depends(require_access_code)])


class ClassifyRequest(BaseModel):
    extracted: ExtractResponse
    project_name: str | None = None


@router.post("/api/classify", response_model=ClassifyResponse)
async def classify(
    payload: ClassifyRequest,
    settings: Settings = Depends(get_settings),
) -> ClassifyResponse:
    if not payload.extracted.candidates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There are no candidate items to classify.",
        )
    try:
        return await run_classification(
            extracted=payload.extracted,
            settings=settings,
            project_name=payload.project_name,
        )
    except RateLimited as err:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="The judgment service is rate limited. Please try again in a moment.",
            headers={"Retry-After": str(int(err.retry_after or 20))},
        ) from err
    except (DecisionError, LLMError) as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The judgment service is unavailable. Please try again.",
        ) from err
