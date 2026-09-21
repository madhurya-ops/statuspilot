"""Normalise raw transcript text into numbered, speaker-attributed lines."""

import re

from app.models import TranscriptLine

# "Priya Nair:", "Dev-Ops Lead:", "Sam O'Brien:" but not "Note: remember to..."
# or "10:30: standup". The name side is deliberately narrow: letters, spaces and
# a few name punctuation marks, at most four words, no sentence punctuation.
_SPEAKER = re.compile(
    r"^(?P<speaker>[A-Za-z][A-Za-z.'\-]*(?: [A-Za-z][A-Za-z.'\-]*){0,3}):"
    r"\s(?P<text>\S.*)$"
)

# Words that look like a name before a colon but introduce a clause instead.
_NOT_SPEAKERS = {
    "note", "notes", "action", "actions", "agenda", "attendees", "present",
    "apologies", "decision", "decisions", "risk", "risks", "issue", "issues",
    "assumption", "assumptions", "dependency", "dependencies", "todo", "to do",
    "next steps", "date", "time", "project", "subject", "topic", "summary",
    "update", "status", "blocker", "blockers", "aob", "apologies for absence",
}


def split_speaker(line: str) -> tuple[str | None, str]:
    """Split `Name: text` into (speaker, text), or (None, line) when there is no speaker."""
    match = _SPEAKER.match(line)
    if not match:
        return None, line
    speaker = match.group("speaker").strip()
    if speaker.lower() in _NOT_SPEAKERS:
        return None, line
    # Every word must be capitalised. Without this, an ordinary sentence that
    # happens to contain a colon ("One thing: we need sign-off") is read as a
    # speaker, and a false speaker becomes a false *owner* further down the
    # pipeline, which Hard Rule 7 forbids.
    if not all(word[:1].isupper() for word in speaker.split()):
        return None, line
    return speaker, match.group("text").strip()


def normalize_text(raw: str, max_chars: int) -> tuple[str, bool]:
    """Collapse whitespace and truncate to `max_chars`.

    Returns the text and whether it was truncated. Truncation happens on a line
    boundary so a cut never leaves a half sentence that the LLM would then quote as
    evidence.
    """
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    kept: list[str] = []
    for line in raw.split("\n"):
        line = re.sub(r"[ \t ]+", " ", line).strip()
        if line:
            kept.append(line)
    text = "\n".join(kept)
    if len(text) <= max_chars:
        return text, False

    truncated: list[str] = []
    used = 0
    for line in kept:
        if used + len(line) + 1 > max_chars:
            break
        truncated.append(line)
        used += len(line) + 1
    return "\n".join(truncated), True


def to_lines(text: str) -> list[TranscriptLine]:
    """Number the lines of already-normalised text, detecting `Name:` speakers."""
    lines: list[TranscriptLine] = []
    for i, raw in enumerate(text.split("\n"), start=1):
        raw = raw.strip()
        if not raw:
            continue
        speaker, body = split_speaker(raw)
        lines.append(TranscriptLine(n=i, speaker=speaker, text=body))
    return lines
