"""Phase 8: every generated file must re-open in the library that made it."""

import io

import pytest

from app.models import ApprovedItem, Documents
from app.routers.export import safe_filename


def _item(**kw):
    base = dict(
        id="c1",
        text="Fix the orphaned document reference — before UAT",
        kind="action_item",
        severity="High",
        severity_value=1.92,
        audience="client_safe",
        owner="Marcus Webb",
        owner_status="stated",
        due_date="Thursday",
        due_status="stated",
        source_lines=[19, 20],
    )
    base.update(kw)
    return ApprovedItem(**base)


@pytest.fixture
def documents():
    return Documents(
        mom_markdown="## Attendees\nPriya Nair\n\n## Decisions\n- Ship it",
        status_report_markdown=(
            "## Overall status: Red\n\nThe date **moved** — badly.\n\n"
            "## Next steps\n- Complete the fix by 27 March"
        ),
        action_items=[
            _item(),
            _item(id="c2", severity="Low", severity_value=0.2, owner=None, due_date=None),
        ],
        raid_log={
            "Risks": [_item(id="c3", kind="risk", audience="internal_only")],
            "Assumptions": [],
            "Issues": [],
            "Dependencies": [],
        },
    )


class TestDocx:
    def test_reopens_in_python_docx(self, documents):
        from docx import Document

        from app.export.docx_export import build_docx

        blob = build_docx(documents, "Contoso Insurance", "Red")
        reopened = Document(io.BytesIO(blob))
        text = "\n".join(p.text for p in reopened.paragraphs)
        assert "Contoso Insurance" in text
        assert "Red" in text
        assert reopened.tables, "the action-item table must be present"

    def test_the_action_table_comes_from_the_data(self, documents):
        from docx import Document

        from app.export.docx_export import build_docx

        reopened = Document(io.BytesIO(build_docx(documents, "P", "Red")))
        rows = reopened.tables[0].rows
        assert len(rows) == 1 + len(documents.action_items)
        assert rows[1].cells[1].text == "Marcus Webb"
        assert rows[2].cells[1].text == "Not assigned"

    def test_markdown_tables_are_never_carried_into_the_document(self, documents):
        from docx import Document

        from app.export.docx_export import build_docx

        documents.status_report_markdown += "\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
        reopened = Document(io.BytesIO(build_docx(documents, "P", "Red")))
        text = "\n".join(p.text for p in reopened.paragraphs)
        assert "| a | b |" not in text


class TestXlsx:
    def test_reopens_with_all_five_sheets(self, documents):
        from openpyxl import load_workbook

        from app.export.xlsx_export import build_xlsx

        book = load_workbook(io.BytesIO(build_xlsx(documents)))
        assert book.sheetnames == ["Action Items", "Risks", "Assumptions", "Issues", "Dependencies"]

    def test_header_is_frozen_and_the_raw_score_is_present(self, documents):
        from openpyxl import load_workbook

        from app.export.xlsx_export import build_xlsx

        sheet = load_workbook(io.BytesIO(build_xlsx(documents)))["Action Items"]
        assert sheet.freeze_panes == "A2"
        header = [c.value for c in sheet[1]]
        assert "Score" in header
        # The float is exported so a PM can sort by real priority, not by a band
        # that ties 1.52 with 2.0.
        assert sheet.cell(row=2, column=header.index("Score") + 1).value == 1.92

    def test_an_empty_category_says_so(self, documents):
        from openpyxl import load_workbook

        from app.export.xlsx_export import build_xlsx

        sheet = load_workbook(io.BytesIO(build_xlsx(documents)))["Issues"]
        assert sheet.cell(row=2, column=1).value


class TestPdf:
    def test_produces_a_valid_pdf(self, documents):
        from app.export.pdf_export import build_pdf

        blob = build_pdf(documents, "Contoso Insurance", "Red")
        assert blob.startswith(b"%PDF-")
        assert blob.rstrip().endswith(b"%%EOF")

    def test_survives_long_text_and_many_items(self, documents):
        """A drifting cursor once made fpdf2 raise "Not enough horizontal space"."""
        from app.export.pdf_export import build_pdf

        documents.action_items = [_item(text="A very long action item. " * 12)] * 12
        assert build_pdf(documents, "A very long project name " * 3, "Amber").startswith(b"%PDF-")

    def test_non_latin1_characters_do_not_crash_it(self, documents):
        from app.export.pdf_export import build_pdf

        documents.status_report_markdown = "## Status\n\nZoë — café, naïve… “quoted”"
        assert build_pdf(documents, "Zoë Café", "Green").startswith(b"%PDF-")


class TestFilename:
    @pytest.mark.parametrize(
        "project,expected_stem",
        [
            ("Contoso Insurance", "Contoso-Insurance"),
            ("../../etc/passwd", "etc-passwd"),
            ('a"; rm -rf /', "a-rm-rf"),
            (None, "Project"),
            ("", "Project"),
        ],
    )
    def test_is_sanitised(self, project, expected_stem):
        """The project name is user input and lands in a response header."""
        name = safe_filename(project, "pdf")
        assert name.startswith(f"StatusReport_{expected_stem}_")
        assert name.endswith(".pdf")
        assert "/" not in name and '"' not in name


class TestExportEndpoint:
    def _payload(self, documents):
        return {"documents": documents.model_dump(), "project_name": "Contoso", "rag": "Red"}

    def test_requires_the_access_code(self, client, documents):
        assert client.post("/api/export/pdf", json=self._payload(documents)).status_code == 401

    @pytest.mark.parametrize("fmt", ["docx", "xlsx", "pdf"])
    def test_each_format_downloads(self, client, auth, documents, fmt):
        r = client.post(f"/api/export/{fmt}", headers=auth, json=self._payload(documents))
        assert r.status_code == 200
        assert len(r.content) > 500
        assert "attachment" in r.headers["content-disposition"]
        assert fmt in r.headers["content-disposition"]

    def test_an_unknown_format_is_rejected(self, client, auth, documents):
        r = client.post("/api/export/exe", headers=auth, json=self._payload(documents))
        assert r.status_code == 400
