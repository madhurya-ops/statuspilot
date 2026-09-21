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


class MeetingMeta(BaseModel):
    title: str
    date: str | None = None
    attendees: list[str] = Field(default_factory=list)
    agenda: list[str] = Field(default_factory=list)


class Candidate(BaseModel):
    """One extracted item, before Jev judges what it actually is.

    `kind_hint` is the LLM's guess and is informational only — Phase 4's `item_kind`
    judgment decides the real type. Nothing downstream may branch on `kind_hint`.
    """

    id: str
    text: str
    kind_hint: str
    owner: str | None = None
    due_date: str | None = None
    source_lines: list[int] = Field(default_factory=list)
    evidence: str = ""


class ExtractResponse(BaseModel):
    meta: MeetingMeta
    discussion_points: list[str] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
    lines: list[TranscriptLine] = Field(default_factory=list)


class LLMUsage(BaseModel):
    """Token accounting for one LLM call. Reported so cost is never guessed at."""

    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    attempts: int = 1
    escalated: bool = False
    # "stop" = the model finished on its own; "length" = it hit the completion cap
    # and the output is truncated. Recorded because a low candidate count means very
    # different things in the two cases: prompt behaviour vs. a budget that is too
    # tight, and only one of those is fixed by changing the prompt.
    finish_reason: str | None = None


# What the extraction model is asked to produce, per candidate. No `id`: ids are
# assigned in code (validate_candidates renumbers contiguously), so asking the model
# for them only spends output tokens on something we discard. No docstring, for the
# same schema-size reason as ExtractionPayload.
class CandidateDraft(BaseModel):
    text: str
    kind_hint: str
    owner: str | None = None
    due_date: str | None = None
    source_lines: list[int] = Field(default_factory=list)
    evidence: str = ""


# The extraction call's response schema: `ExtractResponse` MINUS `lines`.
#
# `lines` is the numbered transcript we already hold. Including it in the schema made
# strict mode require the model to re-emit the whole transcript as output, which
# exhausted max_completion_tokens and returned 400 json_validate_failed. The server
# fills `lines` in afterwards.
#
# Deliberately no docstring: pydantic emits a class docstring into the JSON schema as
# a "description", which is then sent to the model as input tokens on every call.
class ExtractionPayload(BaseModel):
    meta: MeetingMeta
    discussion_points: list[str] = Field(default_factory=list)
    candidates: list[CandidateDraft] = Field(default_factory=list)
