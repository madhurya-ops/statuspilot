"""Status report as a PDF, via fpdf2 (pure Python — no system libraries)."""

import re

from fpdf import FPDF

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
    pdf.multi_cell(0, height, _ascii(text))


def _ascii(text: str) -> str:
    """fpdf2's core fonts are latin-1 only; keep the text readable rather than crash."""
    return (
        text.replace("—", "-")
        .replace("–", "-")
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("…", "...")
        .replace(" ", " ")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )


def build_pdf(documents: Documents, project: str, rag: str) -> bytes:
    pdf = _Report(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
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
    pdf.cell(34, 9, _ascii(f"  {rag}"), fill=True, new_x="LMARGIN", new_y="NEXT")
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

    if documents.action_items:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*SOFT)
        _line(pdf, 6, "Action items")
        pdf.set_text_color(*INK)
        pdf.set_font("Helvetica", size=10)
        for item in documents.action_items:
            owner = item.owner or "Not assigned"
            due = item.due_date or "No date"
            _line(pdf, 5.5, f"  - [{item.severity}] {item.text} ({owner}, {due})")

    output = pdf.output()
    return bytes(output) if not isinstance(output, bytes) else output
