"""Phase 2: /api/samples and /api/parse endpoints."""

import io

import pytest

EXPECTED_IDS = {"northwind-sprint-review", "contoso-escalation", "rough-standup-notes"}


class TestSamplesEndpoints:
    def test_listing_requires_the_access_code(self, client):
        assert client.get("/api/samples").status_code == 401

    def test_lists_all_three_samples(self, client, auth):
        r = client.get("/api/samples", headers=auth)
        assert r.status_code == 200
        body = r.json()
        assert {s["id"] for s in body} == EXPECTED_IDS
        for s in body:
            assert s["title"] and s["description"] and s["chars"] > 0

    @pytest.mark.parametrize("sample_id", sorted(EXPECTED_IDS))
    def test_each_sample_loads_and_reports_its_own_length(self, client, auth, sample_id):
        r = client.get(f"/api/samples/{sample_id}", headers=auth)
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == sample_id
        assert body["chars"] == len(body["text"])

    @pytest.mark.parametrize("sample_id", sorted(EXPECTED_IDS))
    def test_every_sample_is_within_the_token_budget(self, client, auth, sample_id):
        """Section 2: samples are capped at ~5000 chars so a full run fits in 8k TPM."""
        body = client.get(f"/api/samples/{sample_id}", headers=auth).json()
        assert body["chars"] <= 5000, f"{sample_id} is {body['chars']} chars"

    def test_unknown_sample_is_404_not_500(self, client, auth):
        assert client.get("/api/samples/nope", headers=auth).status_code == 404

    def test_sample_id_cannot_traverse_the_filesystem(self, client, auth):
        r = client.get("/api/samples/..%2F..%2Fconfig", headers=auth)
        assert r.status_code == 404


class TestParseEndpoint:
    def test_requires_the_access_code(self, client):
        r = client.post("/api/parse", files={"file": ("a.txt", b"A: hi", "text/plain")})
        assert r.status_code == 401

    def test_parses_a_txt_upload(self, client, auth):
        content = b"Priya Nair: We are on track.\n\nMarcus Webb: Agreed."
        r = client.post(
            "/api/parse", headers=auth, files={"file": ("notes.txt", content, "text/plain")}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["text"] == "Priya Nair: We are on track.\nMarcus Webb: Agreed."
        assert body["chars"] == len(body["text"])
        assert body["truncated"] is False

    def test_rejects_an_oversized_upload(self, client, auth):
        from app.config import get_settings

        oversized = b"x" * (get_settings().max_upload_bytes + 1)
        r = client.post(
            "/api/parse", headers=auth, files={"file": ("big.txt", oversized, "text/plain")}
        )
        assert r.status_code == 413

    def test_rejects_a_disallowed_extension(self, client, auth):
        r = client.post(
            "/api/parse",
            headers=auth,
            files={"file": ("resume.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert r.status_code == 400

    def test_rejects_an_empty_file(self, client, auth):
        r = client.post("/api/parse", headers=auth, files={"file": ("a.txt", b"", "text/plain")})
        assert r.status_code == 400

    def test_rejects_a_file_with_no_readable_text(self, client, auth):
        r = client.post(
            "/api/parse", headers=auth, files={"file": ("a.txt", b"   \n\n  \n", "text/plain")}
        )
        assert r.status_code == 400

    def test_truncates_above_max_input_chars(self, client, auth):
        from app.config import get_settings

        settings = get_settings()
        big = ("Speaker: a line of talking here\n" * 2000).encode()
        assert len(big) > settings.max_input_chars
        r = client.post(
            "/api/parse", headers=auth, files={"file": ("big.txt", big, "text/plain")}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["truncated"] is True
        assert body["chars"] <= settings.max_input_chars

    def test_parses_a_vtt_upload(self, client, auth):
        vtt = (
            b"WEBVTT\n\n1\n00:00:01.000 --> 00:00:04.000\n"
            b"<v Priya Nair>I'll take it,\n\n"
            b"2\n00:00:04.000 --> 00:00:06.000\n<v Priya Nair>by Thursday.\n"
        )
        r = client.post("/api/parse", headers=auth, files={"file": ("m.vtt", vtt, "text/vtt")})
        assert r.status_code == 200
        assert r.json()["text"] == "Priya Nair: I'll take it, by Thursday."

    def test_parses_a_docx_upload(self, client, auth):
        docx = pytest.importorskip("docx")
        buf = io.BytesIO()
        document = docx.Document()
        document.add_paragraph("Priya Nair: We are on track.")
        document.save(buf)
        r = client.post(
            "/api/parse",
            headers=auth,
            files={
                "file": (
                    "m.docx",
                    buf.getvalue(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert r.status_code == 200
        assert "Priya Nair: We are on track." in r.json()["text"]

    def test_reports_the_supported_formats(self, client, auth):
        r = client.get("/api/parse/formats", headers=auth)
        assert r.status_code == 200
        assert set(r.json()) == {".txt", ".docx", ".vtt", ".srt"}
