"""Status report as a PDF, via fpdf2 (pure Python — no system libraries)."""

import re
import unicodedata

from fpdf import FPDF

from app.export.audience import prepare
from app.models import Documents

RAG_RGB = {"Red": (180, 35, 24), "Amber": (181, 71, 8), "Green": (6, 118, 71)}
INK = (35, 36, 51)
SOFT = (85, 87, 107)


class _Report(FPDF):
    def header(self) -> None:  # noqa: D102
        pass

    def footer(self) -> None:  # noqa: D102
        self.set_y(-14)
        self.set_font("Helvetica", size=8)
        self.set_text_color(*SOFT)
        self.cell(0, 8, f"Page {self.page_no()}", align="R")


def _line(pdf: FPDF, height: float, text: str) -> None:
    """Write a full-width line from the left margin.

    `multi_cell(0, ...)` measures the available width from the *current* x, so a
    cursor left mid-page by an earlier cell eventually leaves no usable width and
    fpdf2 raises "Not enough horizontal space to render a single character".
    """
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, height, _pdf_text(text))


# fpdf2's core fonts are latin-1 only, so anything outside it renders as "?". The
# generator was observed emitting U+2011 (non-breaking hyphen) and U+2019 (right
# single quote) — "go-live" came out as "go?live" four times in one report. Rather
# than patch those two, everything outside latin-1 is folded.
_PUNCTUATION = {
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
    "\u2015": "-", "\u2212": "-",
    "\u2018": "'", "\u2019": "'", "\u201a": ",", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
    "\u2032": "'", "\u2033": '"',
    "\u2026": "...", "\u2022": "-", "\u00b7": "-", "\u2043": "-",
    "\u00a0": " ", "\u2007": " ", "\u2009": " ", "\u200a": " ", "\u202f": " ",
    "\u200b": "", "\u200c": "", "\u200d": "", "\ufeff": "",
    "\u2192": "->", "\u2190": "<-", "\u21d2": "=>",
    "\u2264": "<=", "\u2265": ">=", "\u2260": "!=",
    "\u00d7": "x", "\u2044": "/", "\u2122": "(TM)", "\u2117": "(P)",
}


def _pdf_text(text: str) -> str:
    """Make a string safe for fpdf2's latin-1 core fonts without losing meaning.

    Three passes: map punctuation that has a sensible ASCII equivalent; decompose
    anything still outside latin-1 so accented characters keep their base letter
    (Zoë survives as latin-1 anyway, but Ž -> Z rather than "?"); then encode,
    replacing whatever is genuinely unrepresentable.
    """
    for source, target in _PUNCTUATION.items():
        text = text.replace(source, target)
    try:
        return text.encode("latin-1").decode("latin-1")
    except UnicodeEncodeError:
        pass
    folded = []
    for char in text:
        try:
            char.encode("latin-1")
            folded.append(char)
        except UnicodeEncodeError:
            decomposed = unicodedata.normalize("NFKD", char)
            keep = "".join(c for c in decomposed if not unicodedata.combining(c))
            try:
                keep.encode("latin-1")
                folded.append(keep or "?")
            except UnicodeEncodeError:
                folded.append("?")
    return "".join(folded)


def build_pdf(documents: Documents, project: str, rag: str) -> bytes:
    pdf = _Report(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_compression(False)
    pdf.add_page()
    pdf.set_margins(18, 16, 18)

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*INK)
    _line(pdf, 9, project or "Project status report")
    pdf.ln(2)

    # The RAG block: the one piece of colour, carrying real meaning.
    red, green, blue = RAG_RGB.get(rag, INK)
    pdf.set_fill_color(red, green, blue)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(34, 9, _pdf_text(f"  {rag}"), fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_text_color(*INK)
    for raw in documents.status_report_markdown.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*SOFT)
            _line(pdf, 6, heading.group(2))
            pdf.set_text_color(*INK)
            pdf.ln(1)
            continue
        if line.strip().startswith("|"):
            continue
        bullet = re.match(r"^\s*[-*+]\s+(.*)$", line)
        pdf.set_font("Helvetica", size=10)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", bullet.group(1) if bullet else line)
        _line(pdf, 5.5, ("  - " if bullet else "") + text)

    # THE PDF IS THE CLIENT-FACING EXPORT. The prose arrives already filtered from the
    # generator, but this table does not: `Documents.action_items` carries every
    # approved item. Without this filter, internal-only remarks were appended to a
    # file intended for the client.
    actions = prepare(documents.action_items, "client")
    if actions:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*SOFT)
        _line(pdf, 6, "Action items")
        pdf.set_text_color(*INK)
        pdf.set_font("Helvetica", size=10)
        for item in actions:
            owner = item.owner or "Not assigned"
            due = item.due_date or "No date"
            _line(pdf, 5.5, f"  - [{item.severity}] {item.text} ({owner}, {due})")

    output = pdf.output()
    return bytes(output) if not isinstance(output, bytes) else output
