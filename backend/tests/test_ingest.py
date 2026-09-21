"""Phase 2: parsers, line numbering, speaker detection, size guards."""

import io

import pytest
from fastapi import HTTPException

from app.ingest.lines import normalize_text, split_speaker, to_lines
from app.ingest.parse import decode_text, parse_captions, parse_docx, parse_upload


class TestSpeakerDetection:
    @pytest.mark.parametrize(
        "line,speaker,text",
        [
            ("Priya Nair: We are on track.", "Priya Nair", "We are on track."),
            ("Marcus: Done.", "Marcus", "Done."),
            ("Sam O'Brien: I will check.", "Sam O'Brien", "I will check."),
            ("Dr. Anita Rao: Defects are down.", "Dr. Anita Rao", "Defects are down."),
        ],
    )
    def test_detects_a_speaker(self, line, speaker, text):
        assert split_speaker(line) == (speaker, text)

    @pytest.mark.parametrize(
        "line",
        [
            "Note: remember the UAT window.",
            "Risks: none today.",
            "Action: chase the vendor.",
            "Attendees: Priya, Marcus, Anita",
            "- maybe look at perf?",
            "10:30 standup started",
            "This sentence: has a colon in the middle of a long clause that is not a name.",
        ],
    )
    def test_does_not_invent_a_speaker(self, line):
        """A false speaker would be attributed as an owner downstream, so these matter."""
        assert split_speaker(line)[0] is None


class TestNormalize:
    def test_collapses_whitespace_and_drops_blank_lines(self):
        text, truncated = normalize_text("A:  hello   there\n\n\n\nB: bye  ", 1000)
        assert text == "A: hello there\nB: bye"
        assert truncated is False

    def test_handles_windows_and_classic_mac_line_endings(self):
        text, _ = normalize_text("A: one\r\nB: two\rC: three", 1000)
        assert text == "A: one\nB: two\nC: three"

    def test_truncates_on_a_line_boundary(self):
        """A mid-sentence cut would be quoted back as evidence, so cuts land on lines."""
        source = "\n".join(f"Speaker: line number {i}" for i in range(50))
        text, truncated = normalize_text(source, 100)
        assert truncated is True
        assert len(text) <= 100
        assert not text.endswith(" ")
        for line in text.split("\n"):
            assert line in source.split("\n")


class TestLineNumbering:
    def test_numbers_from_one_and_keeps_speakers(self):
        text = "Priya Nair: One.\nMarcus Webb: Two.\nPlain narration."
        lines = to_lines(text)
        assert [line.n for line in lines] == [1, 2, 3]
        assert lines[0].speaker == "Priya Nair"
        assert lines[0].text == "One."
        assert lines[2].speaker is None
        assert lines[2].text == "Plain narration."


class TestCaptions:
    def test_vtt_strips_cues_and_merges_the_same_speaker(self):
        vtt = (
            "WEBVTT\n\nNOTE auto-generated\n\n"
            "1\n00:00:01.000 --> 00:00:04.000\n<v Priya Nair>I'll take the timeout,\n\n"
            "2\n00:00:04.000 --> 00:00:07.000\n<v Priya Nair>done by Thursday.\n\n"
            "3\n00:00:07.500 --> 00:00:09.000 align:start position:10%\n"
            "<v Marcus Webb>Thanks.\n"
        )
        out = parse_captions(vtt)
        assert out == "Priya Nair: I'll take the timeout, done by Thursday.\nMarcus Webb: Thanks."
        assert "WEBVTT" not in out and "-->" not in out

    def test_srt_uses_the_name_prefix_inside_the_cue(self):
        srt = (
            "1\n00:00:01,000 --> 00:00:04,000\nPriya Nair: I'll take the timeout,\n\n"
            "2\n00:00:04,000 --> 00:00:07,000\nPriya Nair: done by Thursday.\n"
        )
        assert parse_captions(srt) == "Priya Nair: I'll take the timeout, done by Thursday."

    def test_different_speakers_are_not_merged(self):
        srt = (
            "1\n00:00:01,000 --> 00:00:02,000\nA: first\n\n"
            "2\n00:00:02,000 --> 00:00:03,000\nB: second\n"
        )
        assert parse_captions(srt) == "A: first\nB: second"


class TestDecoding:
    def test_utf8(self):
        assert decode_text("Zoë: café".encode()) == "Zoë: café"

    def test_falls_back_to_latin1_rather_than_failing(self):
        assert decode_text(b"Zo\xeb: caf\xe9") == "Zoë: café"


class TestDispatch:
    def test_txt(self):
        assert parse_upload("notes.txt", b"A: hi") == "A: hi"

    def test_extension_is_case_insensitive(self):
        assert parse_upload("NOTES.TXT", b"A: hi") == "A: hi"

    @pytest.mark.parametrize("name", ["notes.pdf", "notes.exe", "notes", "notes.doc"])
    def test_rejects_anything_not_allow_listed(self, name):
        with pytest.raises(HTTPException) as err:
            parse_upload(name, b"x")
        assert err.value.status_code == 400

    def test_docx_round_trip(self):
        docx = pytest.importorskip("docx")
        buf = io.BytesIO()
        document = docx.Document()
        document.add_paragraph("Priya Nair: We are on track.")
        table = document.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = "Owner"
        table.rows[0].cells[1].text = "Marcus"
        document.save(buf)
        out = parse_docx(buf.getvalue())
        assert "Priya Nair: We are on track." in out
        assert "Owner | Marcus" in out

    def test_corrupt_docx_gives_a_clean_400(self):
        with pytest.raises(HTTPException) as err:
            parse_docx(b"this is not a docx")
        assert err.value.status_code == 400
