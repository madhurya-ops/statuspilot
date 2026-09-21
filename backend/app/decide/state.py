"""Builds the `state` object Jev evaluates, one per candidate.

The docs recommend a JSON object with named fields over one blob of prose, so each
part of the context has a name the questions can reference with a backticked path
(`item.evidence`). Jev state is data by construction — there is no instruction
channel inside it — which is what makes Hard Rule 6 hold here for free.
"""

from typing import Any

from app.models import Candidate, MeetingMeta, TranscriptLine

CONTEXT_LINES = 2


def build_item_state(
    candidate: Candidate,
    lines: list[TranscriptLine],
    meta: MeetingMeta,
    *,
    project_name: str | None = None,
    client_present: bool | None = None,
) -> dict[str, Any]:
    by_number = {line.n: line for line in lines}
    cited = candidate.source_lines or []
    first, last = (min(cited), max(cited)) if cited else (0, 0)

    context: list[str] = []
    for n in range(first - CONTEXT_LINES, last + CONTEXT_LINES + 1):
        line = by_number.get(n)
        if line is None:
            continue
        context.append(f"{line.speaker}: {line.text}" if line.speaker else line.text)

    return {
        "meeting": {
            "title": meta.title,
            "project": project_name or meta.title,
            "client_present": (
                client_present if client_present is not None else _infer_client(meta)
            ),
        },
        "item": {
            "text": candidate.text,
            "evidence": candidate.evidence,
            "source_lines": cited,
            "stated_owner": candidate.owner,
            "stated_due": candidate.due_date,
        },
        "surrounding_context": "\n".join(context),
    }


def _infer_client(meta: MeetingMeta) -> bool:
    """Best-effort: does an attendee line mark someone as being on the client side?"""
    blob = " ".join(meta.attendees).lower()
    return any(word in blob for word in ("client", "customer")) or "(" in blob


def build_rag_state(
    items: list[dict[str, Any]],
    summary: list[str],
    meta: MeetingMeta,
    *,
    project_name: str | None = None,
) -> dict[str, Any]:
    """State for the single project-level RAG request.

    Only accepted items are passed, reduced to the fields the RAG questions actually
    need. Sending whole candidates would spend context on evidence text that the
    project-level questions do not use.
    """
    return {
        "project": project_name or meta.title,
        "summary": summary[:3],
        "items": items,
    }
