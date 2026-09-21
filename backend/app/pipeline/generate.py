"""Approved items -> MoM + status report.

The action-item and RAID tables are assembled **in code** from the approved items and
are never parsed out of LLM prose. The model writes narrative only. That is what makes
"no invented items" a property of the system rather than a hope about the prompt.
"""

import logging
import re

from pydantic import BaseModel

from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.prompts import (
    GENERATE_SYSTEM,
    GENERATE_USER,
    STRICTER_RETRY,
    format_items,
)
from app.models import ApprovedItem, Documents, GenerateRequest, LLMUsage

log = logging.getLogger(__name__)

CLIENT_SAFE = "client_safe"
ACTION_KIND = "action_item"
RAID_KINDS = {
    "risk": "Risks",
    "assumption": "Assumptions",
    "issue": "Issues",
    "dependency": "Dependencies",
}

EMPTY_STATUS_REPORT = """\
## Overall status: {rag}

{reason}

## No client-facing items

{withheld} of {total} items from this meeting were classified as internal only, so
there is nothing here that would go to a client.

That is a real result, not an error. {explanation}

Use the **Show internal-only items** toggle to see everything that was captured, and
the RAID log and action items tabs for the full internal picture.
"""

# A report whose sections are all headings with nothing under them is worse than an
# honest explanation: it reads as a broken app. Measured on `rough-standup-notes`,
# which cleared a single client-safe item and produced five empty headings.
MIN_SUBSTANTIVE_CHARS = 200


def substantive_body(markdown: str) -> str:
    """The report's prose, excluding headings, bullets markers and blank lines."""
    body = []
    for line in markdown.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        body.append(stripped.lstrip("-*0123456789. ").strip())
    return " ".join(part for part in body if part)

INTERNAL_STANDUP_HINT = (
    "This looks like an internal working session with no client present — the "
    "discussion is about how the team works, not about what the client receives."
)
GENERIC_HINT = (
    "Every item carried internal opinion, staffing or commercial detail, or a remark "
    "about the client, so none of it was cleared for a client-facing report."
)


class _Written(BaseModel):
    mom_markdown: str = ""
    status_report_markdown: str = ""


def build_action_items(items: list[ApprovedItem]) -> list[ApprovedItem]:
    """Action items, most severe first. Sorted on the raw float, not the band.

    Two items can both band "High" at 1.52 and 2.0; ordering by the band alone would
    present those as equal priority.
    """
    actions = [item for item in items if item.kind == ACTION_KIND]
    return sorted(actions, key=lambda item: (-item.severity_value, item.id))


def build_raid_log(items: list[ApprovedItem]) -> dict[str, list[ApprovedItem]]:
    log_: dict[str, list[ApprovedItem]] = {label: [] for label in RAID_KINDS.values()}
    for item in items:
        label = RAID_KINDS.get(item.kind)
        if label:
            log_[label].append(item)
    for label in log_:
        log_[label].sort(key=lambda item: (-item.severity_value, item.id))
    return log_


def _significant_terms(text: str) -> set[str]:
    """Distinctive words from an internal item, for the leak check."""
    words = re.findall(r"[a-z][a-z'\-]{4,}", text.lower())
    return {w for w in words if w not in _STOPWORDS}


_STOPWORDS = {
    "about", "after", "again", "their", "there", "these", "those", "which", "would",
    "could", "should", "being", "other", "still", "while", "where", "every", "until",
    "because", "between", "before", "during", "since", "under", "above", "items",
    "item", "project", "client", "report", "status", "meeting", "team", "teams",
    "work", "working", "needs", "need", "date", "dates",
}


# An internal item needs at least this many distinctive terms before a match means
# anything. Below it, ordinary project vocabulary produces coincidences.
MIN_DISTINCTIVE_TERMS = 4
# And this share of them must appear, so a partial vocabulary overlap is not a leak.
LEAK_OVERLAP_RATIO = 0.75


def detect_leak(
    report: str,
    internal_items: list[ApprovedItem],
    client_items: list[ApprovedItem] | None = None,
) -> ApprovedItem | None:
    """Fuzzy check: does the client report echo an *internal-only* item?

    The decisive rule is the exclusion of shared vocabulary. A word that also appears
    in an item already cleared for the client cannot be evidence of a leak — the
    report is *supposed* to talk about that. Without this, an internal note reading
    "anonymised data would be available by end of March" matches a perfectly proper
    client sentence about anonymised test data dates, and the stripper then deletes
    legitimate content. That was observed: it emptied a whole "Next steps" section.

    Still biased toward catching leaks, since missing one puts blame or staffing
    detail in front of a client. But it no longer treats project nouns as secrets.
    """
    client_vocabulary: set[str] = set()
    for item in client_items or []:
        client_vocabulary |= _significant_terms(item.text)

    haystack = set(re.findall(r"[a-z][a-z'\-]{4,}", report.lower()))
    for item in internal_items:
        terms = _significant_terms(item.text) - client_vocabulary
        if len(terms) < MIN_DISTINCTIVE_TERMS:
            continue
        overlap = terms & haystack
        if len(overlap) >= max(
            MIN_DISTINCTIVE_TERMS, int(len(terms) * LEAK_OVERLAP_RATIO)
        ):
            return item
    return None


def strip_leaked_sentences(report: str, item: ApprovedItem) -> str:
    """Last resort: remove sentences that echo the internal item."""
    terms = _significant_terms(item.text)
    kept = []
    for line in report.split("\n"):
        sentences = re.split(r"(?<=[.!?])\s+", line)
        surviving = [
            s for s in sentences if len(_significant_terms(s) & terms) < max(2, len(terms) // 2)
        ]
        kept.append(" ".join(surviving) if sentences != surviving else line)
    return "\n".join(kept)


def _empty_report(payload: GenerateRequest, withheld: int) -> str:
    attendees = " ".join(payload.meta.attendees).lower()
    client_present = any(word in attendees for word in ("client", "customer"))
    explanation = GENERIC_HINT if client_present else INTERNAL_STANDUP_HINT
    return EMPTY_STATUS_REPORT.format(
        rag=payload.rag.status,
        reason=payload.rag.reason,
        explanation=explanation,
        withheld=withheld,
        total=len(payload.items),
    )


async def run_generation(
    *,
    payload: GenerateRequest,
    provider: LLMProvider,
    settings: Settings,
) -> tuple[Documents, LLMUsage]:
    client_items = [item for item in payload.items if item.audience == CLIENT_SAFE]
    internal_items = [item for item in payload.items if item.audience != CLIENT_SAFE]

    user = GENERATE_USER.format(
        title=payload.meta.title,
        project=payload.project_name or payload.meta.title,
        period=payload.reporting_period or "Not specified",
        rag_status=payload.rag.status,
        rag_reason=payload.rag.reason,
        attendees=", ".join(payload.meta.attendees) or "Not recorded",
        agenda=", ".join(payload.meta.agenda) or "Not recorded",
        discussion="\n".join(f"- {p}" for p in payload.discussion_points) or "(none)",
        items=format_items(payload.items),
    )

    written, usage = await provider.complete_json(
        system=GENERATE_SYSTEM, user=user, schema_model=_Written, stage="generate"
    )

    status_report = written.status_report_markdown
    leak_stripped = False

    if client_items:
        leaked = detect_leak(status_report, internal_items, client_items)
        if leaked is not None:
            log.warning("status report echoed an internal item; regenerating")
            retried, retry_usage = await provider.complete_json(
                system=GENERATE_SYSTEM,
                user=user + STRICTER_RETRY,
                schema_model=_Written,
                stage="generate",
            )
            usage.input_tokens += retry_usage.input_tokens
            usage.output_tokens += retry_usage.output_tokens
            status_report = retried.status_report_markdown
            still_leaking = detect_leak(status_report, internal_items, client_items)
            if still_leaking is not None:
                # Type only, never content (Hard Rule 5).
                log.warning("status report still leaked after retry; stripping sentences")
                status_report = strip_leaked_sentences(status_report, still_leaking)
                leak_stripped = True
    # Two ways to end up with nothing worth showing: no client-safe item at all, or
    # so few that the model returns a skeleton of empty headings. Both get the honest
    # explanation rather than a blank or near-blank panel.
    if not client_items or len(substantive_body(status_report)) < MIN_SUBSTANTIVE_CHARS:
        status_report = _empty_report(payload, len(internal_items))
        status_report_empty = True
    else:
        status_report_empty = False

    documents = Documents(
        mom_markdown=written.mom_markdown,
        status_report_markdown=status_report,
        action_items=build_action_items(payload.items),
        raid_log=build_raid_log(payload.items),
        status_report_empty=status_report_empty,
        leak_stripped=leak_stripped,
    )
    log.info(
        "generate items=%d client_safe=%d internal=%d empty=%s stripped=%s in=%d out=%d",
        len(payload.items),
        len(client_items),
        len(internal_items),
        documents.status_report_empty,
        leak_stripped,
        usage.input_tokens,
        usage.output_tokens,
    )
    return documents, usage
