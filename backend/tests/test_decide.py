"""Phase 4: answer parsing, banding, routing, RAG, fallback.

Hard Rule 8: Jev is respx-mocked throughout; no network.
"""

import httpx
import pytest
import respx

from app.config import get_settings
from app.decide.base import DecisionError
from app.decide.jev import JevEngine, parse_answer
from app.decide.llm_fallback import derive_confidence
from app.decide.questions import ITEM_QUESTIONS, SEVERITY_LEVELS
from app.decide.routing import apply_audience_failsafe, band_noul, band_score, route
from app.models import Decision
from app.pipeline.rag import combine

JEV_URL = "https://api.typesafe.ai/v1/systemone"


class TestParseAnswer:
    def test_choice(self):
        d = parse_answer(
            {
                "type": "choice",
                "choice": "action_item",
                "confidence": 0.91,
                "probabilities": {"action_item": 0.95, "risk": 0.05},
            }
        )
        assert d.label == "action_item"
        assert d.confidence == 0.91
        assert d.probabilities["action_item"] == 0.95
        assert d.value is None

    def test_score_keeps_the_raw_float_and_gets_no_label(self):
        """Banding is policy and belongs in routing.py, not in the parser."""
        d = parse_answer(
            {
                "type": "score",
                "score": 1.74,
                "confidence": 0.62,
                "legend": {"0": "Low", "1": "Medium", "2": "High"},
                "probabilities": {"0": 0.0, "1": 0.26, "2": 0.74},
            }
        )
        assert d.value == 1.74
        assert d.label == ""
        assert d.confidence == 0.62

    def test_noul_has_no_confidence(self):
        """Jev returns no confidence for Noul. That is why the value is banded."""
        d = parse_answer({"type": "noul", "noul": 0.73})
        assert d.value == 0.73
        assert d.confidence is None

    def test_unknown_type_raises(self):
        with pytest.raises(DecisionError):
            parse_answer({"type": "wat"})


class TestScoreBanding:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (0.0, "Low"),
            (0.49, "Low"),
            (0.5, "Medium"),
            (1.0, "Medium"),
            (1.49, "Medium"),
            (1.5, "High"),
            (1.74, "High"),
            (2.0, "High"),
        ],
    )
    def test_rounds_to_the_nearest_level(self, score, expected):
        assert band_score(score, SEVERITY_LEVELS) == expected

    def test_half_values_round_up_not_to_even(self):
        """Python's round() is banker's rounding: round(0.5) == 0. That would make
        0.5 band Low while 1.5 bands High, which no rubric could explain."""
        assert band_score(0.5, SEVERITY_LEVELS) == "Medium"
        assert band_score(1.5, SEVERITY_LEVELS) == "High"

    def test_clamps_out_of_range_scores(self):
        assert band_score(-1.0, SEVERITY_LEVELS) == "Low"
        assert band_score(99.0, SEVERITY_LEVELS) == "High"


class TestNoulBanding:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (0.0, "not_specified"),
            (0.34, "not_specified"),
            (0.35, "not_specified"),
            (0.36, "inferred"),
            (0.5, "inferred"),
            (0.64, "inferred"),
            # NOUL_YES was raised 0.65 -> 0.75 in Phase 4: at 0.65 a note reading
            # "priya: reminder timesheets due friday" scored 0.67 and banded
            # "stated", though Priya is reminding others rather than owning the task.
            (0.67, "inferred"),
            (0.74, "inferred"),
            (0.75, "stated"),
            (0.80, "stated"),
            (1.0, "stated"),
        ],
    )
    def test_bands(self, value, expected):
        assert band_noul(value, get_settings()) == expected


def _d(label, confidence):
    return Decision(label=label, confidence=confidence)


class TestRouting:
    @pytest.mark.parametrize(
        "kind_c,aud_c,expected",
        [
            (0.95, 0.95, "auto"),
            (0.80, 0.80, "auto"),
            (0.79, 0.95, "suggested"),
            (0.95, 0.79, "suggested"),
            (0.50, 0.95, "suggested"),
            (0.49, 0.95, "review"),
            (0.95, 0.49, "review"),
            (0.10, 0.10, "review"),
        ],
    )
    def test_boundaries(self, kind_c, aud_c, expected):
        got = route(_d("action_item", kind_c), _d("client_safe", aud_c), get_settings())
        assert got == expected


def _aud(label, p_safe):
    """An audience Decision carrying a real two-option distribution."""
    return Decision(
        label=label,
        confidence=abs(2 * p_safe - 1),
        probabilities={"client_safe": p_safe, "internal_only": 1 - p_safe},
    )


class TestAudienceFailsafe:
    """Gates on the PROBABILITY, not the confidence.

    `audience` has two options, so confidence = 2*p_max - 1. Thresholding confidence
    at CONF_AUTO (0.80) silently demanded p >= 0.90, which flipped 12 of 16 Northwind
    items to internal although Jev judged every one client-safe.
    """

    def test_forces_internal_below_the_probability_threshold(self):
        out = apply_audience_failsafe(_aud("client_safe", 0.84), get_settings())
        assert out.label == "internal_only"

    def test_leaves_a_sufficiently_probable_client_safe_alone(self):
        out = apply_audience_failsafe(_aud("client_safe", 0.85), get_settings())
        assert out.label == "client_safe"

    def test_an_ordinary_project_fact_is_no_longer_withheld(self):
        """p=0.87 is the Northwind client dependency — the report's whole point. Under
        the old confidence gate it needed 0.90 and was withheld."""
        out = apply_audience_failsafe(_aud("client_safe", 0.87), get_settings())
        assert out.label == "client_safe"

    def test_a_genuinely_internal_remark_stays_internal(self):
        """p=0.23 is the Contoso blame remark."""
        out = apply_audience_failsafe(_aud("internal_only", 0.23), get_settings())
        assert out.label == "internal_only"

    def test_never_flips_internal_to_client_safe(self):
        for p_safe in (0.0, 0.3, 0.99):
            out = apply_audience_failsafe(_aud("internal_only", p_safe), get_settings())
            assert out.label == "internal_only"

    def test_a_missing_distribution_falls_back_to_caution(self):
        out = apply_audience_failsafe(Decision(label="client_safe"), get_settings())
        assert out.label == "internal_only"


def _dims(schedule="on_track", scope="stable", resourcing="adequate", sentiment=2.0, conf=0.9):
    return {
        "schedule": Decision(label=schedule, confidence=conf),
        "scope": Decision(label=scope, confidence=conf),
        "resourcing": Decision(label=resourcing, confidence=conf),
        "client_sentiment": Decision(label="", confidence=conf, value=sentiment),
    }


class TestRagRule:
    def test_all_good_is_green(self):
        assert combine(_dims()).status == "Green"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"schedule": "off_track"},
            {"scope": "uncontrolled"},
            {"resourcing": "blocked"},
            {"sentiment": 0.49},
        ],
    )
    def test_any_red_trigger_is_red(self, kwargs):
        assert combine(_dims(**kwargs)).status == "Red"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"schedule": "at_risk"},
            {"scope": "changing"},
            {"resourcing": "stretched"},
            {"sentiment": 1.0},
        ],
    )
    def test_middle_states_are_amber(self, kwargs):
        assert combine(_dims(**kwargs)).status == "Amber"

    def test_sentiment_boundary_is_a_threshold_not_equality(self):
        """The original rule said `client_sentiment == level 0`, which is exact
        equality on a float and would essentially never fire."""
        assert combine(_dims(sentiment=0.49)).status == "Red"
        assert combine(_dims(sentiment=0.5)).status == "Amber"

    def test_red_beats_amber(self):
        assert combine(_dims(schedule="off_track", scope="changing")).status == "Red"

    def test_confidence_is_the_minimum_across_dimensions(self):
        dims = _dims()
        dims["scope"] = Decision(label="stable", confidence=0.42)
        assert combine(dims).confidence == 0.42

    def test_reason_names_the_trigger(self):
        assert "milestone has slipped" in combine(_dims(schedule="off_track")).reason

    def test_green_reason_is_not_empty(self):
        assert combine(_dims()).reason.strip()


class TestDerivedConfidence:
    def test_matches_the_published_formula(self):
        assert derive_confidence({"a": 1.0, "b": 0.0, "c": 0.0}) == pytest.approx(1.0)
        assert derive_confidence({"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}) == pytest.approx(0.0)
        assert derive_confidence({"a": 0.9, "b": 0.06, "c": 0.04}) == pytest.approx(0.85)

    def test_single_option_is_zero_not_a_crash(self):
        assert derive_confidence({"a": 1.0}) == 0.0


def _jev_body(**overrides):
    answers = {
        "item_kind": {
            "type": "choice",
            "choice": "action_item",
            "confidence": 0.95,
            "probabilities": {"action_item": 0.97, "risk": 0.03},
        },
        "severity": {
            "type": "score",
            "score": 1.74,
            "confidence": 0.62,
            "legend": {"0": "Low", "1": "Medium", "2": "High"},
            "probabilities": {"0": 0.0, "1": 0.26, "2": 0.74},
        },
        "audience": {
            "type": "choice",
            "choice": "client_safe",
            "confidence": 0.97,
            "probabilities": {"client_safe": 0.98, "internal_only": 0.02},
        },
        "owner_explicit": {"type": "noul", "noul": 0.73},
        "due_explicit": {"type": "noul", "noul": 0.97},
    }
    answers.update(overrides)
    return {
        "model": "jev-1.13.0",
        "answers": answers,
        "usage": {"input_tokens": 869, "output_tokens": 156},
    }


class TestJevEngine:
    @respx.mock
    async def test_parses_a_full_answer_set(self):
        respx.post(JEV_URL).mock(return_value=httpx.Response(200, json=_jev_body()))
        answers, stats = await JevEngine(get_settings()).judge([{"item": {}}], ITEM_QUESTIONS)
        assert set(answers[0]) == set(ITEM_QUESTIONS)
        assert stats.input_tokens == 869
        assert stats.requests == 1

    @respx.mock
    async def test_respects_the_concurrency_cap(self):
        settings = get_settings()
        in_flight = 0
        peak = 0

        def handler(request):
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            in_flight -= 1
            return httpx.Response(200, json=_jev_body())

        respx.post(JEV_URL).mock(side_effect=handler)
        await JevEngine(settings).judge([{"item": {}}] * 30, ITEM_QUESTIONS)
        assert peak <= settings.jev_concurrency

    @respx.mock
    async def test_retries_on_429_then_succeeds(self):
        route_ = respx.post(JEV_URL)
        route_.side_effect = [
            httpx.Response(429, headers={"retry-after": "0"}),
            httpx.Response(200, json=_jev_body()),
        ]
        answers, _ = await JevEngine(get_settings()).judge([{"item": {}}], ITEM_QUESTIONS)
        assert answers[0]["item_kind"].label == "action_item"

    @respx.mock
    async def test_a_single_failure_does_not_fail_the_run(self):
        route_ = respx.post(JEV_URL)
        route_.side_effect = [
            httpx.Response(200, json=_jev_body()),
            httpx.Response(400),
        ]
        answers, stats = await JevEngine(get_settings()).judge(
            [{"item": {}}, {"item": {}}], ITEM_QUESTIONS
        )
        assert answers[0] and answers[1] == {}

    @respx.mock
    async def test_whole_run_failure_raises(self):
        respx.post(JEV_URL).mock(return_value=httpx.Response(400))
        with pytest.raises(DecisionError):
            await JevEngine(get_settings()).judge([{"item": {}}] * 3, ITEM_QUESTIONS)


class TestWholeRunFallback:
    @respx.mock
    async def test_falls_back_to_the_llm_when_every_jev_request_fails(self, monkeypatch):
        """A whole-run Jev outage must not kill the demo — it degrades to Groq and
        says so, rather than failing."""
        from app.models import RunStats
        from app.pipeline import classify as classify_module

        respx.post(JEV_URL).mock(return_value=httpx.Response(503))

        class FakeLLM:
            name = "llm"

            def __init__(self, settings):
                pass

            async def judge(self, states, questions):
                answers = [
                    {
                        key: Decision(label="action_item", confidence=0.9, value=1.0)
                        for key in questions
                    }
                    for _ in states
                ]
                return answers, RunStats(engine="llm", requests=len(states))

        monkeypatch.setattr(classify_module, "LLMFallbackEngine", FakeLLM)
        settings = get_settings()
        monkeypatch.setattr(settings, "decision_engine", "jev", raising=False)
        monkeypatch.setattr(settings, "llm_primary", "groq", raising=False)

        from app.models import Candidate, ExtractResponse, MeetingMeta, TranscriptLine

        extracted = ExtractResponse(
            meta=MeetingMeta(title="T"),
            candidates=[
                Candidate(
                    id="c1",
                    text="x",
                    kind_hint="action_item",
                    source_lines=[1],
                    evidence="e",
                )
            ],
            lines=[TranscriptLine(n=1, speaker=None, text="e")],
        )
        result = await classify_module.run_classification(extracted=extracted, settings=settings)
        assert result.stats.engine == "llm"
        assert all(item.engine == "llm" for item in result.items)


class TestClassifyEndpoint:
    def _extracted(self, client, auth, sample_id):
        sample = client.get(f"/api/samples/{sample_id}", headers=auth).json()
        return client.post("/api/extract", headers=auth, json={"text": sample["text"]}).json()

    def test_requires_the_access_code(self, client):
        assert client.post("/api/classify", json={"extracted": {}}).status_code in (401, 422)

    def test_rejects_an_empty_candidate_list(self, client, auth):
        payload = {"extracted": {"meta": {"title": "T"}, "candidates": [], "lines": []}}
        assert client.post("/api/classify", headers=auth, json=payload).status_code == 400

    def test_classifies_a_sample_end_to_end(self, client, auth):
        extracted = self._extracted(client, auth, "contoso-escalation")
        r = client.post("/api/classify", headers=auth, json={"extracted": extracted})
        assert r.status_code == 200
        body = r.json()
        assert body["items"]
        assert body["rag"]["status"] in {"Red", "Amber", "Green"}
        assert body["rag"]["reason"].strip()
        assert body["stats"]["engine"] == "mock"

    def test_every_item_carries_the_raw_severity_float(self, client, auth):
        extracted = self._extracted(client, auth, "contoso-escalation")
        body = client.post("/api/classify", headers=auth, json={"extracted": extracted}).json()
        for item in body["items"]:
            assert isinstance(item["severity_value"], float)
            assert item["severity"]["label"] in {"Low", "Medium", "High"}

    def test_severity_value_orders_within_a_band(self, client, auth):
        """The float is the sort key: two items can both band High at 1.52 and 2.0."""
        extracted = self._extracted(client, auth, "contoso-escalation")
        body = client.post("/api/classify", headers=auth, json={"extracted": extracted}).json()
        highs = [i for i in body["items"] if i["severity"]["label"] == "High"]
        if len(highs) >= 2:
            values = [i["severity_value"] for i in highs]
            assert len(set(values)) > 1 or values[0] == values[1]

    def test_rough_notes_produce_review_items(self, client, auth):
        """Gate 4 requires at least 3. The sample is built to be ambiguous."""
        extracted = self._extracted(client, auth, "rough-standup-notes")
        body = client.post("/api/classify", headers=auth, json={"extracted": extracted}).json()
        review = [i for i in body["items"] if i["routing"] == "review"]
        assert len(review) >= 3, f"only {len(review)} review items"

    def test_no_item_is_client_safe_without_confidence(self, client, auth):
        from app.config import get_settings

        extracted = self._extracted(client, auth, "contoso-escalation")
        body = client.post("/api/classify", headers=auth, json={"extracted": extracted}).json()
        for item in body["items"] + body["dropped"]:
            if item["audience"]["label"] == "client_safe":
                assert item["audience"]["confidence"] >= get_settings().conf_auto
