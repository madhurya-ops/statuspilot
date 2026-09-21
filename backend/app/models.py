"""Pydantic data contracts (Section 7 of execution.md).

`frontend/src/types.ts` mirrors this file. Models are added as the phases that need
them arrive; this file grows through Phases 2-5.
"""

from typing import Literal

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


class Decision(BaseModel):
    """One typed judgment from the decision engine.

    `confidence` is None for Noul answers: Jev returns no confidence for that type,
    only a probability. That is why Noul values are banded rather than thresholded on
    a confidence (see `decide/routing.py`).
    """

    label: str
    confidence: float | None = None
    probabilities: dict[str, float] | None = None
    value: float | None = None  # raw Score float; None for choice and noul


class ClassifiedItem(BaseModel):
    candidate: Candidate
    kind: Decision
    severity: Decision
    audience: Decision
    # The raw Score float, kept alongside the banded label. Two items can both band
    # "High" at 1.52 and 2.0; the action list must not rank those equally.
    severity_value: float
    owner_explicit: float
    due_explicit: float
    owner_status: Literal["stated", "inferred", "not_specified"]
    due_status: Literal["stated", "inferred", "not_specified"]
    routing: Literal["auto", "suggested", "review"]
    engine: Literal["jev", "llm", "mock"]


class RagResult(BaseModel):
    status: Literal["Red", "Amber", "Green"]
    confidence: float
    dimensions: dict[str, Decision] = Field(default_factory=dict)
    reason: str = ""


class RunStats(BaseModel):
    engine: str
    requests: int = 0
    latency_ms: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None


class ClassifyResponse(BaseModel):
    items: list[ClassifiedItem] = Field(default_factory=list)
    rag: RagResult
    stats: RunStats
    dropped: list[ClassifiedItem] = Field(default_factory=list)


class ApprovedItem(BaseModel):
    """An item after the PM has reviewed it. Sent back from the client."""

    id: str
    text: str
    kind: str
    severity: str
    severity_value: float = 0.0
    audience: str
    owner: str | None = None
    owner_status: Literal["stated", "inferred", "not_specified"] = "not_specified"
    due_date: str | None = None
    due_status: Literal["stated", "inferred", "not_specified"] = "not_specified"
    source_lines: list[int] = Field(default_factory=list)
    edited_by_user: bool = False


class GenerateRequest(BaseModel):
    meta: MeetingMeta
    discussion_points: list[str] = Field(default_factory=list)
    items: list[ApprovedItem] = Field(default_factory=list)
    rag: RagResult
    project_name: str | None = None
    reporting_period: str | None = None


class Documents(BaseModel):
    mom_markdown: str
    status_report_markdown: str
    # Built in code from `items`, never parsed out of LLM prose. This is what makes
    # "no invented items" enforceable rather than aspirational.
    action_items: list[ApprovedItem] = Field(default_factory=list)
    raid_log: dict[str, list[ApprovedItem]] = Field(default_factory=dict)
    # True when no item is client_safe. A real path: `rough-standup-notes` yields 0 of
    # 17. The UI must render an explanation, never a blank panel.
    status_report_empty: bool = False
    cached: bool = False
    leak_stripped: bool = False


class GenerateResponse(Documents):
    pass


class BudgetStatus(BaseModel):
    """Groq's per-minute token budget, for an honest wait instead of a spinner."""

    limit_tokens: int
    remaining_tokens: int
    refill_per_second: float
    wait_seconds: float
    needed_tokens: int
    known: bool
