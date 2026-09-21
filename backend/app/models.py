"""Pydantic data contracts (Section 7 of execution.md).

`frontend/src/types.ts` mirrors this file. Models are added as the phases that need
them arrive; this file grows through Phases 2-5.
"""

from pydantic import BaseModel, Field


class TranscriptLine(BaseModel):
    """One normalised line of transcript, numbered from 1.

    The number is the anchor for source traceability: every candidate item cites
    `source_lines`, and the UI resolves those back to these lines.
    """

    n: int = Field(ge=1)
    speaker: str | None = None
    text: str


class SampleSummary(BaseModel):
    """A bundled synthetic transcript, as listed by `GET /api/samples`."""

    id: str
    title: str
    description: str
    chars: int


class SampleDetail(SampleSummary):
    text: str


class ParseResponse(BaseModel):
    text: str
    chars: int
    truncated: bool
