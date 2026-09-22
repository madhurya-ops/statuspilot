"""Phase 3: extraction post-validation and the router's two failure paths.

Hard Rule 8: no real API calls. The Groq client is replaced by fakes throughout.
"""

import json

import pytest

from app.config import get_settings
from app.llm.base import JSONInvalid, LLMError, RateLimited
from app.llm.groq_client import strict_schema
from app.llm.router import LLMRouter
from app.models import (
    Candidate,
    ExtractionPayload,
    ExtractResponse,
    LLMUsage,
    MeetingMeta,
    TranscriptLine,
)
from app.pipeline.extract import validate_candidates

LINES = [
    TranscriptLine(n=1, speaker="Priya Nair", text="Marcus will fix the gateway by Thursday."),
    TranscriptLine(n=2, speaker="Marcus Webb", text="Agreed, Thursday works."),
    TranscriptLine(n=3, speaker=None, text="The vendor API is still outstanding."),
]


def _candidate(**kwargs) -> Candidate:
    base = dict(
        id="c1",
        text="Fix the gateway",
        kind_hint="action_item",
        owner=None,
        due_date=None,
        source_lines=[1],
        evidence="Marcus will fix the gateway by Thursday.",
    )
    base.update(kwargs)
    return Candidate(**base)


class TestSourceLineValidation:
    def test_drops_candidates_citing_lines_that_do_not_exist(self):
        """No real citation means no traceability, which is the product."""
        out = validate_candidates([_candidate(source_lines=[99])], LINES, get_settings())
        assert out == []

    def test_keeps_only_the_valid_line_numbers(self):
        out = validate_candidates([_candidate(source_lines=[1, 99, 2])], LINES, get_settings())
        assert out[0].source_lines == [1, 2]

    def test_deduplicates_and_sorts_line_numbers(self):
        out = validate_candidates([_candidate(source_lines=[2, 1, 2])], LINES, get_settings())
        assert out[0].source_lines == [1, 2]


class TestEvidence:
    def test_keeps_verbatim_evidence(self):
        out = validate_candidates([_candidate()], LINES, get_settings())
        assert out[0].evidence == "Marcus will fix the gateway by Thursday."

    def test_replaces_evidence_that_is_not_in_the_cited_lines(self):
        """A paraphrase presented as a quote is a fabricated citation."""
        out = validate_candidates(
            [_candidate(evidence="Marcus promised to sort out the payment problem")],
            LINES,
            get_settings(),
        )
        assert out[0].evidence == "Marcus will fix the gateway by Thursday."

    def test_tolerates_whitespace_differences(self):
        out = validate_candidates(
            [_candidate(evidence="Marcus  will   fix the gateway by Thursday.")],
            LINES,
            get_settings(),
        )
        assert "Marcus" in out[0].evidence

    def test_truncates_long_evidence(self):
        long_line = [TranscriptLine(n=1, speaker=None, text="x" * 900)]
        out = validate_candidates(
            [_candidate(evidence="y" * 900, source_lines=[1])], long_line, get_settings()
        )
        assert len(out[0].evidence) <= 300


class TestOwnerValidation:
    def test_keeps_an_owner_who_appears_in_the_transcript(self):
        out = validate_candidates([_candidate(owner="Marcus Webb")], LINES, get_settings())
        assert out[0].owner == "Marcus Webb"

    @pytest.mark.parametrize("invented", ["Sarah Connor", "Dave", "Marcus Aurelius"])
    def test_nulls_an_owner_who_does_not(self, invented):
        """Hard Rule 7: never invent a name. This is the check that enforces it."""
        out = validate_candidates([_candidate(owner=invented)], LINES, get_settings())
        assert out[0].owner is None

    def test_blank_due_date_becomes_null(self):
        out = validate_candidates([_candidate(due_date="   ")], LINES, get_settings())
        assert out[0].due_date is None


class TestCapping:
    def test_caps_at_max_candidates(self):
        settings = get_settings()
        many = [_candidate(id=f"c{i}") for i in range(settings.max_candidates + 15)]
        out = validate_candidates(many, LINES, settings)
        assert len(out) == settings.max_candidates

    def test_prefers_candidates_with_owners_and_dates(self):
        settings = get_settings()
        plain = [_candidate(id=f"p{i}") for i in range(settings.max_candidates)]
        rich = _candidate(id="rich", owner="Marcus Webb", due_date="Thursday")
        out = validate_candidates([*plain, rich], settings=settings, lines=LINES)
        assert any(c.evidence and c.due_date == "Thursday" for c in out)

    def test_ids_are_renumbered_contiguously(self):
        out = validate_candidates(
            [_candidate(id="zz", source_lines=[1]), _candidate(id="qq", source_lines=[2])],
            LINES,
            get_settings(),
        )
        assert [c.id for c in out] == ["c1", "c2"]


class TestStrictSchema:
    def test_every_object_is_closed_and_fully_required(self):
        """Groq's strict mode rejects a schema that omits either."""
        payload = strict_schema(ExtractResponse)
        assert payload["json_schema"]["strict"] is True

        def walk(node):
            if isinstance(node, dict):
                if node.get("type") == "object" and "properties" in node:
                    assert node["additionalProperties"] is False
                    assert set(node["required"]) == set(node["properties"])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(payload["json_schema"]["schema"])


class TestExtractionPayloadShape:
    def test_the_model_is_never_asked_to_re_emit_the_transcript(self):
        """Regression: `lines` in the schema made strict mode require the model to
        reproduce the entire transcript, exhausting max_completion_tokens and
        returning 400 json_validate_failed. The server fills `lines` in itself."""
        schema = strict_schema(ExtractionPayload)["json_schema"]["schema"]
        assert "lines" not in schema["properties"]
        # `source_lines` is legitimate; a bare `lines` property anywhere is not.
        for definition in schema.get("$defs", {}).values():
            assert "lines" not in definition.get("properties", {})

    def test_the_schema_carries_no_prose_descriptions(self):
        """Docstrings become schema `description` fields, billed as input tokens."""
        assert "description" not in json.dumps(strict_schema(ExtractionPayload))

    def test_extract_response_still_carries_lines_to_the_client(self):
        assert "lines" in ExtractResponse.model_fields

    def test_drafts_carry_no_id(self):
        """Ids are assigned in code, so asking for them only spends output tokens."""
        from app.models import CandidateDraft

        assert "id" not in CandidateDraft.model_fields


class FakeProvider:
    """Replays a scripted sequence of outcomes."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[str] = []
        self.caps: list[int | None] = []

    async def complete_json(
        self, *, system, user, schema_model, stage, max_completion_tokens=None
    ):
        self.calls.append(user)
        self.caps.append(max_completion_tokens)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome, LLMUsage(model="fake", input_tokens=10, output_tokens=5)


def _ok() -> ExtractionPayload:
    return ExtractionPayload(meta=MeetingMeta(title="T"), discussion_points=[], candidates=[])


@pytest.fixture
def slept():
    recorded: list[float] = []

    async def fake_sleep(seconds):
        recorded.append(seconds)

    return recorded, fake_sleep


class TestRouterRateLimitPath:
    async def test_backs_off_and_retries_on_429(self, slept, monkeypatch):
        recorded, fake_sleep = slept
        fake = FakeProvider([RateLimited("429", status=429), _ok()])
        monkeypatch.setattr("app.llm.router.build_provider", lambda *a, **k: fake)

        router = LLMRouter(get_settings(), sleep=fake_sleep)
        result, usage = await router.complete_json(
            system="s", user="u", schema_model=ExtractionPayload, stage="extract"
        )
        assert result.meta.title == "T"
        assert recorded == [1.0]

    async def test_never_switches_model_on_429(self, slept, monkeypatch):
        """Both Groq models share one token bucket, so escalating would be pointless."""
        recorded, fake_sleep = slept
        models: list[str] = []

        def spy(settings, model=None):
            models.append(model)
            return fake

        fake = FakeProvider([RateLimited("429", status=429)] * 3)
        monkeypatch.setattr("app.llm.router.build_provider", spy)
        router = LLMRouter(get_settings(), sleep=fake_sleep)
        with pytest.raises(RateLimited):
            await router.complete_json(
                system="s", user="u", schema_model=ExtractionPayload, stage="extract"
            )
        assert set(models) == {get_settings().groq_model}, models

    async def test_honours_retry_after_over_the_backoff_schedule(self, slept, monkeypatch):
        recorded, fake_sleep = slept
        fake = FakeProvider([RateLimited("429", status=429, retry_after=7.5), _ok()])
        monkeypatch.setattr("app.llm.router.build_provider", lambda *a, **k: fake)
        await LLMRouter(get_settings(), sleep=fake_sleep).complete_json(
            system="s", user="u", schema_model=ExtractionPayload, stage="extract"
        )
        assert recorded == [7.5]


class TestRouterSchemaFailurePath:
    async def test_repairs_once_on_the_same_model(self, slept, monkeypatch):
        _, fake_sleep = slept
        fake = FakeProvider([JSONInvalid("bad"), _ok()])
        used: list[str] = []

        def spy(settings, model=None):
            used.append(model)
            return fake

        monkeypatch.setattr("app.llm.router.build_provider", spy)
        result, usage = await LLMRouter(get_settings(), sleep=fake_sleep).complete_json(
            system="s", user="u", schema_model=ExtractionPayload, stage="extract"
        )
        assert result.meta.title == "T"
        assert used == [get_settings().groq_model]
        assert "did not match the required JSON schema" in fake.calls[1]

    async def test_escalates_to_the_larger_model_after_repeated_failure(self, slept, monkeypatch):
        _, fake_sleep = slept
        fake = FakeProvider([JSONInvalid("bad"), JSONInvalid("bad"), _ok()])
        used: list[str] = []

        def spy(settings, model=None):
            used.append(model)
            return fake

        monkeypatch.setattr("app.llm.router.build_provider", spy)
        settings = get_settings()
        result, usage = await LLMRouter(settings, sleep=fake_sleep).complete_json(
            system="s", user="u", schema_model=ExtractionPayload, stage="extract"
        )
        assert used == [settings.groq_model, settings.groq_model_escalation]
        assert usage.escalated is True

    async def test_gives_up_cleanly_when_even_escalation_fails(self, slept, monkeypatch):
        _, fake_sleep = slept
        fake = FakeProvider([JSONInvalid("bad")] * 4)
        monkeypatch.setattr("app.llm.router.build_provider", lambda *a, **k: fake)
        with pytest.raises(JSONInvalid):
            await LLMRouter(get_settings(), sleep=fake_sleep).complete_json(
                system="s", user="u", schema_model=ExtractionPayload, stage="extract"
            )

    async def test_other_errors_propagate_without_retrying(self, slept, monkeypatch):
        _, fake_sleep = slept
        fake = FakeProvider([LLMError("500", status=500), _ok()])
        monkeypatch.setattr("app.llm.router.build_provider", lambda *a, **k: fake)
        with pytest.raises(LLMError):
            await LLMRouter(get_settings(), sleep=fake_sleep).complete_json(
                system="s", user="u", schema_model=ExtractionPayload, stage="extract"
            )
        assert len(fake.outcomes) == 1


class TestExtractEndpoint:
    """End-to-end through the mock provider — no network."""

    def test_requires_the_access_code(self, client):
        assert client.post("/api/extract", json={"text": "x" * 300}).status_code == 401

    def test_rejects_text_that_is_too_short(self, client, auth):
        r = client.post("/api/extract", headers=auth, json={"text": "too short"})
        assert r.status_code == 400

    def test_extracts_from_a_bundled_sample(self, client, auth):
        sample = client.get("/api/samples/contoso-escalation", headers=auth).json()
        r = client.post("/api/extract", headers=auth, json={"text": sample["text"]})
        assert r.status_code == 200
        body = r.json()
        assert body["meta"]["title"]
        assert body["candidates"], "mock provider should find candidates in this sample"
        assert body["lines"], "lines must be returned for source traceability"

    def test_every_candidate_cites_real_lines(self, client, auth):
        sample = client.get("/api/samples/northwind-sprint-review", headers=auth).json()
        body = client.post("/api/extract", headers=auth, json={"text": sample["text"]}).json()
        valid = {line["n"] for line in body["lines"]}
        for candidate in body["candidates"]:
            assert candidate["source_lines"], candidate
            assert set(candidate["source_lines"]).issubset(valid)

    def test_every_owner_appears_in_the_transcript(self, client, auth):
        sample = client.get("/api/samples/contoso-escalation", headers=auth).json()
        body = client.post("/api/extract", headers=auth, json={"text": sample["text"]}).json()
        haystack = sample["text"].lower()
        for candidate in body["candidates"]:
            if candidate["owner"]:
                assert candidate["owner"].lower() in haystack, candidate["owner"]

    def test_respects_max_candidates(self, client, auth):
        from app.config import get_settings

        sample = client.get("/api/samples/rough-standup-notes", headers=auth).json()
        body = client.post("/api/extract", headers=auth, json={"text": sample["text"]}).json()
        assert len(body["candidates"]) <= get_settings().max_candidates


class TestDynamicCompletionCap:
    """The cap is scaled from the prompt because Groq charges its TPM limit on
    `prompt + max_completion_tokens`, not on tokens consumed."""

    def test_scales_with_the_prompt(self):
        from app.llm.groq_client import completion_cap

        assert completion_cap("extract", 2060) == 4120  # 2060 * 2.0
        assert completion_cap("extract", 1500) == 3000  # 1500 * 2.0

    def test_clamps_to_floor_and_ceiling(self):
        from app.llm.groq_client import COMPLETION_CEILING, COMPLETION_FLOOR, completion_cap

        assert completion_cap("extract", 10) == COMPLETION_FLOOR["extract"]
        assert completion_cap("extract", 99_999) == COMPLETION_CEILING["extract"]

    def test_prompt_estimate_never_underestimates(self):
        """Worst measured density was 3.196 chars/token; the estimator uses 3.1."""
        from app.llm.groq_client import estimate_prompt_tokens

        for chars, actual in ((8820, 2502), (8779, 2520), (6223, 1948)):
            assert estimate_prompt_tokens("x" * chars, "") >= actual

    async def test_a_truncated_response_is_retried_at_the_ceiling(self, slept, monkeypatch):
        """Truncation is invisible under strict json_schema: the JSON still parses and
        items are silently lost. It must be retried, not accepted."""
        from app.llm.base import Truncated
        from app.llm.groq_client import COMPLETION_CEILING

        _, fake_sleep = slept
        fake = FakeProvider([Truncated("hit the cap"), _ok()])
        monkeypatch.setattr("app.llm.router.build_provider", lambda *a, **k: fake)
        result, _ = await LLMRouter(get_settings(), sleep=fake_sleep).complete_json(
            system="s", user="u", schema_model=ExtractionPayload, stage="extract"
        )
        assert result.meta.title == "T"
        assert fake.caps == [None, COMPLETION_CEILING["extract"]]

    async def test_truncation_at_the_ceiling_propagates(self, slept, monkeypatch):
        from app.llm.base import Truncated

        _, fake_sleep = slept
        fake = FakeProvider([Truncated("cap"), Truncated("cap")])
        monkeypatch.setattr("app.llm.router.build_provider", lambda *a, **k: fake)
        with pytest.raises(Truncated):
            await LLMRouter(get_settings(), sleep=fake_sleep).complete_json(
                system="s", user="u", schema_model=ExtractionPayload, stage="extract"
            )


class TestTruncationHasTwoFaces:
    """Groq signals a hit completion cap two different ways. Both must retry."""

    def test_400_json_validate_failed_from_truncation_is_detected(self):
        from app.llm.groq_client import _error_code, _mentions_truncation

        class FakeErr(Exception):
            body = {
                "error": {
                    "message": "Failed to generate JSON. See 'failed_generation'.",
                    "code": "json_validate_failed",
                    "failed_generation": (
                        "max completion tokens reached before generating a valid document"
                    ),
                }
            }
            response = None

        err = FakeErr()
        assert _error_code(err) == "json_validate_failed"
        assert _mentions_truncation(err) is True

    def test_a_genuine_schema_failure_is_not_read_as_truncation(self):
        from app.llm.groq_client import _mentions_truncation

        class FakeErr(Exception):
            body = {
                "error": {
                    "code": "json_validate_failed",
                    "failed_generation": '{"meta": {"title": 42}}',
                }
            }
            response = None

        assert _mentions_truncation(FakeErr()) is False


class TestUnboundedRetryAfter:
    """Groq once returned `retry-after: 612`, which the router honoured literally and
    stalled for ten minutes. On Vercel (`maxDuration` 60 s) that is a killed function
    and a bare timeout instead of an explanation."""

    async def test_a_huge_retry_after_is_surfaced_not_slept_through(self, slept, monkeypatch):
        recorded, fake_sleep = slept
        fake = FakeProvider([RateLimited("429", status=429, retry_after=612.0), _ok()])
        monkeypatch.setattr("app.llm.router.build_provider", lambda *a, **k: fake)
        with pytest.raises(RateLimited) as err:
            await LLMRouter(get_settings(), sleep=fake_sleep).complete_json(
                system="s", user="u", schema_model=ExtractionPayload, stage="extract"
            )
        assert err.value.retry_after == 612.0
        assert recorded == [], "must not have slept at all"

    async def test_a_reasonable_retry_after_is_still_honoured(self, slept, monkeypatch):
        recorded, fake_sleep = slept
        fake = FakeProvider([RateLimited("429", status=429, retry_after=17.0), _ok()])
        monkeypatch.setattr("app.llm.router.build_provider", lambda *a, **k: fake)
        await LLMRouter(get_settings(), sleep=fake_sleep).complete_json(
            system="s", user="u", schema_model=ExtractionPayload, stage="extract"
        )
        assert recorded == [17.0]


class TestDailyVsMinuteLimit:
    """Groq has a 200,000 tokens-per-day cap that appears in NO response header.
    Only the 429 body names it, which is how it exhausted silently during Phase 5."""

    def test_a_per_day_limit_is_recognised(self):
        from app.llm.groq_client import _limit_scope

        class Err(Exception):
            body = {
                "error": {
                    "message": (
                        "Rate limit reached for model `openai/gpt-oss-20b` on tokens "
                        "per day (TPD): Limit 200000, Used 199232, Requested 2877."
                    ),
                    "code": "rate_limit_exceeded",
                }
            }
            response = None

        assert _limit_scope(Err()) == "day"

    def test_a_per_minute_limit_is_not_mistaken_for_a_daily_one(self):
        from app.llm.groq_client import _limit_scope

        class Err(Exception):
            body = {
                "error": {
                    "message": (
                        "Rate limit reached on tokens per minute (TPM): "
                        "Limit 8000, Used 5645, Requested 5274."
                    ),
                    "code": "rate_limit_exceeded",
                }
            }
            response = None

        assert _limit_scope(Err()) == "minute"

    def test_the_two_scopes_produce_different_user_messages(self):
        from app.llm.base import RateLimited
        from app.routers.extract import _rate_limit_detail

        daily = _rate_limit_detail(RateLimited("x", retry_after=900.0, scope="day"))
        minute = _rate_limit_detail(RateLimited("x", retry_after=20.0, scope="minute"))
        assert "daily" in daily.lower() and "precomputed" in daily
        assert "refilling" in minute and "daily" not in minute.lower()


class TestSchemaMissBecomesRepairable:
    """A 400 `json_validate_failed` that is NOT truncation must be repairable.

    Observed: the model emitted `candidates` and `discussion_points` but omitted the
    required `meta`, so Groq rejected the whole response. That surfaced as a generic
    LLMError which the router re-raised immediately, killing an entire cache build
    instead of repairing and then escalating.
    """

    def test_a_malformed_document_maps_to_json_invalid(self):
        from app.llm.groq_client import _error_code, _mentions_truncation

        class Err(Exception):
            body = {
                "error": {
                    "message": (
                        "Generated JSON does not match the expected schema. "
                        "Error: jsonschema: '' does not validate with /required: "
                        "missing properties: 'meta'"
                    ),
                    "code": "json_validate_failed",
                    "failed_generation": '{"candidates":[]}',
                }
            }
            response = None

        err = Err()
        assert _error_code(err) == "json_validate_failed"
        # Not truncation -> must be treated as a repairable schema miss.
        assert _mentions_truncation(err) is False

    def test_field_order_puts_meta_first_and_discussion_points_last(self):
        """Ordering by cost, not importance. The model drops whichever required field
        it deprioritises, so the cheap one leads and the expendable one trails."""
        from app.llm.groq_client import strict_schema
        from app.models import ExtractionPayload

        order = list(strict_schema(ExtractionPayload)["json_schema"]["schema"]["properties"])
        assert order == ["meta", "candidates", "discussion_points"]
