"""Bundled synthetic transcripts. One tap in the UI loads one of these."""

from fastapi import APIRouter, Depends

from app.ingest.samples import get_sample, list_samples
from app.models import SampleDetail, SampleSummary
from app.security import require_access_code

router = APIRouter(
    prefix="/api/samples",
    tags=["samples"],
    dependencies=[Depends(require_access_code)],
)


@router.get("", response_model=list[SampleSummary])
def samples() -> list[SampleSummary]:
    return list_samples()


@router.get("/{sample_id}", response_model=SampleDetail)
def sample(sample_id: str) -> SampleDetail:
    return get_sample(sample_id)
