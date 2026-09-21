"""Health endpoint. The only route that does not require an access code."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import VERSION, Settings, get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_primary: str
    decision_engine: str
    groq_model: str


@router.get("/api/health", response_model=HealthResponse, tags=["meta"])
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Liveness plus the active model configuration.

    Deliberately reports which models are wired up so a deploy can be verified from
    a phone without shell access. It reports no key material and no key presence.
    """
    return HealthResponse(
        status="ok",
        version=VERSION,
        llm_primary=settings.llm_primary,
        decision_engine=settings.decision_engine,
        groq_model=settings.groq_model,
    )
