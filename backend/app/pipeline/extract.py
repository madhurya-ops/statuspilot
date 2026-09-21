"""Transcript -> candidates, with the anti-hallucination rules from Section 8.

The LLM is instructed to over-extract; this module is the part that refuses to trust
it. Every rule here exists to make Hard Rule 7 enforceable rather than aspirational:
no item survives that cites a line which does not exist, quotes evidence it did not
find, or names an owner who never appears in the transcript.
"""

import logging
import re
import unicodedata

from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.prompts import build_extract_messages, number_for_prompt
from app.models import (
    Candidate,
    ExtractionPayload,
    ExtractResponse,
    LLMUsage,
    TranscriptLine,
)

log = logging.getLogger(__name__)

EVIDENCE_MAX_CHARS = 300


def _squash(text: str) -> str:
    """Normalise for comparison: fold unicode, collapse whitespace, lowercase."""
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _name_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[A-Za-z][A-Za-z'\-]+", text) if len(token) > 1}


async def run_extraction(
    *,
    text: str,
    lines: list[TranscriptLine],
    provider: LLMProvider,
    settings: Settings,
) -> tuple[ExtractResponse, LLMUsage]:
    prompt_body = number_for_prompt(lines)
    system, user = build_extract_messages(prompt_body)
    payload, usage = await provider.complete_json(
        system=system, user=user, schema_model=ExtractionPayload, stage="extract"
    )
    drafts = [
        Candidate(id=f"c{i}", **draft.model_dump())
        for i, draft in enumerate(payload.candidates, start=1)
    ]
    result = ExtractResponse(
        meta=payload.meta,
        discussion_points=payload.discussion_points,
        candidates=validate_candidates(drafts, lines, settings),
        # Filled in by the server: the model is never asked to re-emit the
        # transcript, which is what blew the completion-token limit.
        lines=lines,
    )
    result.meta.attendees = _validated_attendees(result.meta.attendees, text)
    return result, usage


def _validated_attendees(attendees: list[str], transcript: str) -> list[str]:
    """Drop attendee names that appear nowhere in the transcript."""
    haystack = _squash(transcript)
    return [name for name in attendees if name.strip() and _squash(name) in haystack]


def validate_candidates(
    candidates: list[Candidate],
    lines: list[TranscriptLine],
    settings: Settings,
) -> list[Candidate]:
    by_number = {line.n: line for line in lines}
    transcript_names = _name_tokens(" ".join(line.text for line in lines))
    transcript_names |= {
        token for line in lines if line.speaker for token in _name_tokens(line.speaker)
    }

    kept: list[Candidate] = []
    dropped_bad_lines = 0
    repaired_evidence = 0
    nulled_owners = 0

    for candidate in candidates:
        valid_lines = sorted({n for n in candidate.source_lines if n in by_number})
        if not valid_lines:
            # No real citation means no traceability, which is the whole product.
            dropped_bad_lines += 1
            continue
        candidate.source_lines = valid_lines

        cited = " ".join(by_number[n].text for n in valid_lines)
        if not candidate.evidence or _squash(candidate.evidence) not in _squash(cited):
            candidate.evidence = cited[:EVIDENCE_MAX_CHARS]
            repaired_evidence += 1
        else:
            candidate.evidence = candidate.evidence[:EVIDENCE_MAX_CHARS]

        if candidate.owner:
            owner_tokens = _name_tokens(candidate.owner)
            # An owner is only real if every word of the name occurs in the
            # transcript. This is the check that stops a fabricated assignee.
            if not owner_tokens or not owner_tokens.issubset(transcript_names):
                candidate.owner = None
                nulled_owners += 1

        if candidate.due_date is not None and not candidate.due_date.strip():
            candidate.due_date = None

        kept.append(candidate)

    kept = _cap(kept, settings.max_candidates)
    for index, candidate in enumerate(kept, start=1):
        candidate.id = f"c{index}"

    log.info(
        "extract_validate in=%d kept=%d dropped_lines=%d repaired_evidence=%d nulled_owners=%d",
        len(candidates),
        len(kept),
        dropped_bad_lines,
        repaired_evidence,
        nulled_owners,
    )
    return kept


def _cap(candidates: list[Candidate], limit: int) -> list[Candidate]:
    """Trim to `limit`, keeping the highest-signal candidates.

    Section 8: those with owners and dates first. Ordering within a band preserves
    transcript order so the review queue still reads chronologically.
    """
    if len(candidates) <= limit:
        return candidates

    def rank(item: tuple[int, Candidate]) -> tuple[int, int]:
        index, candidate = item
        signal = (1 if candidate.owner else 0) + (1 if candidate.due_date else 0)
        return (-signal, index)

    ordered = sorted(enumerate(candidates), key=rank)[:limit]
    return [candidate for _, candidate in sorted(ordered, key=lambda pair: pair[0])]
