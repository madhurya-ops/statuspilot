"""Deterministic offline provider. No network, no cost, no variance.

Hard Rule 8: every automated test uses this. It derives its output from the
transcript itself rather than returning one fixed blob, so tests can assert on real
relationships (owners that do appear in the text, line numbers that exist) instead
of on a hard-coded fixture.
"""

import re
import time
from typing import TypeVar

from pydantic import BaseModel

from app.config import Settings
from app.llm.base import JSONInvalid
from app.models import CandidateDraft, ExtractionPayload, LLMUsage, MeetingMeta

T = TypeVar("T", bound=BaseModel)

# Phrases that signal a commitment, a problem, or an agreement.
# Two families, because the bundled samples are two shapes of input. Meeting dialogue
# announces commitments ("I'll take that"); bullet notes state bare conditions
# ("staging box still on the old image"). A signal list written only for the first
# finds almost nothing in the second, which would leave the review queue untested.
_SIGNALS = (
    # meeting dialogue
    "will ", "i'll", "to fix", "to raise", "to provide", "to deliver", "to confirm",
    "to update", "to escalate", "to reissue", "risk", "issue", "defect", "assum",
    "depend", "waiting on", "blocked", "decision", "agreed", "slip", "delay",
    "action", "chase", "by thursday", "by monday", "overdue",
    # bullet notes
    "maybe", "should", "never", "nobody", "still ", "pending", "stale", "unclear",
    "chk", "tbd", "need ", "missing", "down to", "went up", "no plan", "?",
)

_LINE = re.compile(r"^L(?P<n>\d+):\s*(?P<body>.*)$")


class MockProvider:
    """Mirrors GroqProvider's interface without touching the network."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self.model = "mock"

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_model: type[T],
        stage: str,
        max_completion_tokens: int | None = None,
    ) -> tuple[T, LLMUsage]:
        started = time.monotonic()
        if schema_model is ExtractionPayload:
            payload = self._extract(user)
        elif set(schema_model.model_fields) >= {"mom_markdown", "status_report_markdown"}:
            # Generation. Derived from the prompt's own item lines so the offline flow
            # produces documents that actually reflect the items, including the
            # client/internal split — without which Phases 6-7 cannot be built or
            # demonstrated with the API budget exhausted.
            payload = schema_model.model_validate(self._write(user))
        else:
            raise JSONInvalid(f"MockProvider has no canned output for {schema_model.__name__}")

        usage = LLMUsage(
            model="mock",
            input_tokens=len(user) // 4,
            output_tokens=120,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return schema_model.model_validate(payload.model_dump()), usage

    def _write(self, user: str) -> dict[str, str]:
        """Build minutes and a status report from the tagged item lines in the prompt."""
        client: list[str] = []
        internal: list[str] = []
        for raw in user.split("\n"):
            line = raw.strip()
            if line.startswith("- [client]"):
                client.append(_item_text(line))
            elif line.startswith("- [internal]"):
                internal.append(_item_text(line))

        status = _field(user, "Overall status:") or "Amber"
        attendees = _field(user, "Attendees:") or "Not recorded"
        everything = client + internal

        mom = [
            f"# {_field(user, 'Meeting:') or 'Meeting'}",
            f"## Attendees\n{attendees}",
            "## Key discussion points",
        ]
        mom.append("\n".join(f"- {t}" for t in everything[:6]) or "- Nothing recorded.")
        mom.append("## Action items")
        mom.append("\n".join(f"- {t}" for t in everything) or "- None.")

        report = [f"## Overall status: {status.split(chr(8212))[0].strip()}"]
        report.append(
            "This report covers the items cleared for sharing with the client."
        )
        report.append("## Summary")
        report.append(
            " ".join(f"{t}." for t in client[:3])
            or "No client-facing items were identified."
        )
        report.append("## Progress this period")
        report.append("\n".join(f"- {t}" for t in client[:4]) or "- Nothing to report.")
        report.append("## Next steps")
        report.append("\n".join(f"- {t}" for t in client[4:8]) or "- Continue as planned.")
        return {
            "mom_markdown": "\n\n".join(mom),
            "status_report_markdown": "\n\n".join(report),
        }

    def _extract(self, user: str) -> ExtractionPayload:
        numbered: list[tuple[int, str]] = []
        for raw in user.split("\n"):
            match = _LINE.match(raw.strip())
            if match:
                numbered.append((int(match.group("n")), match.group("body")))

        attendees: list[str] = []
        for _, body in numbered:
            if ":" in body:
                name = body.split(":", 1)[0].strip()
                if name and name not in attendees and len(name.split()) <= 4:
                    attendees.append(name)

        candidates: list[CandidateDraft] = []
        for n, body in numbered:
            lowered = body.lower()
            if not any(signal in lowered for signal in _SIGNALS):
                continue
            speaker = body.split(":", 1)[0].strip() if ":" in body else None
            text = body.split(":", 1)[1].strip() if ":" in body else body
            owner = speaker if speaker in attendees else None
            due = None
            for token in ("Thursday", "Monday", "Tuesday", "Friday", "this week"):
                if token.lower() in lowered:
                    due = token
                    break
            candidates.append(
                CandidateDraft(
                    text=text[:200],
                    kind_hint="action_item" if "will" in lowered or "i'll" in lowered else "issue",
                    owner=owner,
                    due_date=due,
                    source_lines=[n],
                    evidence=body[:300],
                )
            )
            if len(candidates) >= self._settings.max_candidates:
                break

        title = numbered[0][1] if numbered else "Meeting"
        return ExtractionPayload(
            meta=MeetingMeta(
                title=title,
                date=None,
                attendees=attendees[:12],
                agenda=[],
            ),
            discussion_points=[body for _, body in numbered[:5]],
            candidates=candidates,
        )


def _item_text(line: str) -> str:
    """Strip the `- [tag][kind/severity] ` prefix from a prompt item line."""
    body = line.split("]", 2)[-1].strip()
    return body.split(";")[0].strip() or body


def _field(user: str, label: str) -> str:
    for raw in user.split("\n"):
        if raw.startswith(label):
            return raw[len(label) :].strip()
    return ""
