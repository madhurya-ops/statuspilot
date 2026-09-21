"""Phase 5: table building, the leak post-check, the empty state, the cache."""


from app.models import (
    ApprovedItem,
    GenerateRequest,
    MeetingMeta,
    RagResult,
)
from app.pipeline.generate import (
    build_action_items,
    build_raid_log,
    detect_leak,
    run_generation,
    strip_leaked_sentences,
)


def _item(id_="c1", kind="action_item", audience="client_safe", severity_value=1.0, **kw):
    base = dict(
        id=id_,
        text=kw.pop("text", "Fix the gateway"),
        kind=kind,
        severity=kw.pop("severity", "Medium"),
        severity_value=severity_value,
        audience=audience,
        owner=kw.pop("owner", "Marcus Webb"),
        due_date=kw.pop("due_date", "Thursday"),
        source_lines=kw.pop("source_lines", [1]),
    )
    base.update(kw)
    return ApprovedItem(**base)


class TestTablesAreBuiltInCode:
    def test_action_items_only(self):
        items = [_item("c1"), _item("c2", kind="risk"), _item("c3", kind="issue")]
        assert [i.id for i in build_action_items(items)] == ["c1"]

    def test_sorted_by_the_raw_float_not_the_band(self):
        """Two items can both band High at 1.52 and 2.0; the band cannot order them."""
        items = [
            _item("c1", severity_value=1.52, severity="High"),
            _item("c2", severity_value=2.0, severity="High"),
            _item("c3", severity_value=1.6, severity="High"),
        ]
        assert [i.id for i in build_action_items(items)] == ["c2", "c3", "c1"]

    def test_raid_log_has_all_four_sections_even_when_empty(self):
        log = build_raid_log([_item(kind="risk")])
        assert set(log) == {"Risks", "Assumptions", "Issues", "Dependencies"}
        assert len(log["Risks"]) == 1
        assert log["Assumptions"] == []

    def test_action_items_are_not_in_the_raid_log(self):
        log = build_raid_log([_item(kind="action_item")])
        assert all(not entries for entries in log.values())


class TestLeakDetection:
    def test_detects_an_echoed_internal_item(self):
        internal = [
            _item(text="Their counterparts habitually neglect scheduled signoff reviews")
        ]
        report = (
            "## Summary\nCounterparts habitually neglect the scheduled signoff "
            "reviews, delaying everything."
        )
        assert detect_leak(report, internal) is not None

    def test_ignores_an_unrelated_report(self):
        internal = [
            _item(text="Their counterparts habitually neglect scheduled signoff reviews")
        ]
        report = "## Summary\nMigration testing continues and the new date is 29 May."
        assert detect_leak(report, internal) is None

    def test_vocabulary_shared_with_a_client_item_is_not_evidence_of_a_leak(self):
        """A word the report is *supposed* to use cannot prove a leak. Without this,
        an internal note about 'anonymised data by end of March' matched a proper
        client sentence about anonymised test data, and the stripper deleted a whole
        section of legitimate content."""
        internal = [_item(text="Assumption: anonymised applicant data available by end of March")]
        client = [_item(text="Anonymised applicant data is expected from governance in March")]
        report = "## Summary\nAnonymised applicant data is expected from governance in March."
        assert detect_leak(report, internal, client) is None

    def test_a_short_internal_item_is_too_generic_to_match(self):
        internal = [_item(text="Amber status")]
        assert detect_leak("The project is Amber this week and status is stable.", internal) is None

    def test_no_internal_items_means_no_leak(self):
        assert detect_leak("anything at all", []) is None

    def test_stripping_removes_the_offending_sentence(self):
        item = _item(text="rehearsal cycle sizing was wrong and optimistic")
        report = (
            "Progress continues. The rehearsal cycle sizing was wrong and "
            "optimistic. Next steps follow."
        )
        out = strip_leaked_sentences(report, item)
        assert "Progress continues." in out
        assert "optimistic" not in out


class FakeWriter:
    """Returns scripted documents without touching a network."""

    def __init__(self, reports):
        self.reports = list(reports)
        self.prompts: list[str] = []

    async def complete_json(self, *, system, user, schema_model, stage, max_completion_tokens=None):
        from app.models import LLMUsage

        self.prompts.append(user)
        report = self.reports.pop(0)
        return (
            schema_model(mom_markdown="## Attendees\nPriya", status_report_markdown=report),
            LLMUsage(model="fake", input_tokens=10, output_tokens=5),
        )


def _request(items):
    return GenerateRequest(
        meta=MeetingMeta(title="Contoso", attendees=["Priya Nair", "Diane Okafor (Contoso)"]),
        discussion_points=["migration"],
        items=items,
        rag=RagResult(status="Red", confidence=0.9, reason="Red because a milestone has slipped."),
    )


class TestGeneration:
    async def test_only_client_safe_items_reach_the_status_report_prompt(self, monkeypatch):
        from app.config import get_settings

        writer = FakeWriter(["## Overall status: Red\nAll fine."])
        items = [
            _item("c1", text="Migration defect blocks UAT", audience="client_safe"),
            _item("c2", text="Their team never reviews anything on time", audience="internal_only"),
        ]
        await run_generation(payload=_request(items), provider=writer, settings=get_settings())
        prompt = writer.prompts[0]
        client_line = next(ln for ln in prompt.split("\n") if "Migration defect" in ln)
        internal_line = next(ln for ln in prompt.split("\n") if "never reviews" in ln)
        assert client_line.startswith("- [client]")
        assert internal_line.startswith("- [internal]")

    async def test_each_item_appears_exactly_once_in_the_prompt(self):
        """An earlier version sent the client subset and then the full list, paying
        for every client-safe item twice in the prompt that gates the demo's pacing."""
        from app.config import get_settings

        writer = FakeWriter(["## Summary\n" + "Migration testing continues. " * 12])
        items = [
            _item("c1", text="Migration defect blocks UAT", audience="client_safe"),
            _item("c2", text="Vendor API is late", audience="client_safe"),
            _item("c3", text="Internal sizing was wrong", audience="internal_only"),
        ]
        await run_generation(payload=_request(items), provider=writer, settings=get_settings())
        prompt = writer.prompts[0]
        for text in ("Migration defect blocks UAT", "Vendor API is late"):
            assert prompt.count(text) == 1, f"{text!r} appears {prompt.count(text)} times"

    async def test_the_prompt_omits_fields_that_do_not_help_writing(self):
        from app.config import get_settings

        writer = FakeWriter(["## Summary\n" + "Migration testing continues. " * 12])
        item = _item("c1", audience="client_safe", source_lines=[41, 42, 43])
        await run_generation(payload=_request([item]), provider=writer, settings=get_settings())
        prompt = writer.prompts[0]
        assert "41" not in prompt and "source_lines" not in prompt

    async def test_regenerates_once_when_the_report_leaks(self, monkeypatch):
        from app.config import get_settings

        leaky = (
            "## Summary\nTheir counterparts habitually neglect scheduled reviews, "
            "repeatedly postponing signoff commitments without warning anyone.\n"
            "## Progress\nMigration rehearsal completed and defects triaged across "
            "the affected records, with remediation underway this fortnight."
        )
        clean = (
            "## Summary\nMigration testing continues against the agreed plan.\n"
            "## Progress\nRehearsal completed and defects triaged across the "
            "affected records, with remediation underway during this fortnight."
        )
        writer = FakeWriter([leaky, clean])
        items = [
            _item("c1", text="Migration defect blocks UAT", audience="client_safe"),
            _item(
                "c2",
                text=(
                    "Their counterparts habitually neglect scheduled reviews, "
                    "repeatedly postponing signoff commitments"
                ),
                audience="internal_only",
            ),
        ]
        docs, _ = await run_generation(
            payload=_request(items), provider=writer, settings=get_settings()
        )
        assert len(writer.prompts) == 2
        assert "internal only and must not" in writer.prompts[1]
        assert "habitually neglect" not in docs.status_report_markdown
        assert docs.leak_stripped is False

    async def test_strips_when_it_still_leaks_after_the_retry(self):
        from app.config import get_settings

        leaky = (
            "## Summary\nTheir counterparts habitually neglect scheduled reviews, "
            "repeatedly postponing signoff commitments without warning anyone.\n"
            "## Progress\nMigration rehearsal completed and defects triaged across "
            "the affected records, with remediation underway this fortnight."
        )
        writer = FakeWriter([leaky, leaky])
        items = [
            _item("c1", text="Migration defect blocks UAT", audience="client_safe"),
            _item(
                "c2",
                text=(
                    "Their counterparts habitually neglect scheduled reviews, "
                    "repeatedly postponing signoff commitments"
                ),
                audience="internal_only",
            ),
        ]
        docs, _ = await run_generation(
            payload=_request(items), provider=writer, settings=get_settings()
        )
        assert docs.leak_stripped is True
        assert "habitually neglect" not in docs.status_report_markdown


class TestEmptyStatusReport:
    async def test_no_client_safe_items_produces_an_explanation_not_a_blank(self):
        """Real path: rough-standup-notes yields 0 client-safe items of 17."""
        from app.config import get_settings

        writer = FakeWriter(["should not be used"])
        items = [_item("c1", audience="internal_only"), _item("c2", audience="internal_only")]
        docs, _ = await run_generation(
            payload=_request(items), provider=writer, settings=get_settings()
        )
        assert docs.status_report_empty is True
        assert "No client-facing items" in docs.status_report_markdown
        assert "internal" in docs.status_report_markdown.lower()
        assert len(docs.status_report_markdown.strip()) > 100

    async def test_the_empty_report_still_states_the_rag_and_reason(self):
        from app.config import get_settings

        writer = FakeWriter(["unused"])
        docs, _ = await run_generation(
            payload=_request([_item(audience="internal_only")]),
            provider=writer,
            settings=get_settings(),
        )
        assert "Red" in docs.status_report_markdown
        assert "milestone has slipped" in docs.status_report_markdown

    async def test_tables_are_still_built_when_the_report_is_empty(self):
        """The PM still needs the RAID log and action items internally."""
        from app.config import get_settings

        writer = FakeWriter(["unused"])
        items = [
            _item("c1", audience="internal_only"),
            _item("c2", kind="risk", audience="internal_only"),
        ]
        docs, _ = await run_generation(
            payload=_request(items), provider=writer, settings=get_settings()
        )
        assert len(docs.action_items) == 1
        assert len(docs.raid_log["Risks"]) == 1


class TestCache:
    def test_fingerprint_ignores_whitespace_differences(self):
        from app.pipeline.cache import fingerprint

        assert fingerprint("A: one\n\n\nB: two") == fingerprint("A:  one\nB:   two  ")

    def test_a_bundled_sample_is_recognised_by_its_text(self, client, auth):
        from app.pipeline.cache import lookup_id

        sample = client.get("/api/samples/contoso-escalation", headers=auth).json()
        assert lookup_id(sample["text"]) == "contoso-escalation"

    def test_arbitrary_text_is_not_recognised(self):
        from app.pipeline.cache import lookup_id

        assert lookup_id("Some meeting the user pasted in themselves.") is None

    def test_lookup_endpoint_reports_no_cache_for_pasted_text(self, client, auth):
        r = client.post("/api/cached/lookup", headers=auth, json={"text": "pasted text"})
        assert r.status_code == 200
        assert r.json()["cached"] is False

    def test_cached_endpoint_404s_when_nothing_is_built(self, client, auth):
        r = client.get("/api/cached/does-not-exist", headers=auth)
        assert r.status_code == 404


class TestGenerateEndpoint:
    def test_requires_the_access_code(self, client):
        assert client.post("/api/generate", json={}).status_code in (401, 422)

    def test_rejects_an_empty_item_list(self, client, auth):
        payload = {
            "meta": {"title": "T"},
            "items": [],
            "rag": {"status": "Green", "confidence": 0.9, "reason": "fine"},
        }
        assert client.post("/api/generate", headers=auth, json=payload).status_code == 400


class TestBudgetEndpoint:
    def test_reports_a_full_bucket_when_nothing_has_been_observed(self, client, auth):
        r = client.get("/api/budget", headers=auth)
        assert r.status_code == 200
        body = r.json()
        assert body["wait_seconds"] == 0.0
        assert body["limit_tokens"] > 0

    def test_requires_the_access_code(self, client):
        assert client.get("/api/budget").status_code == 401


class TestSkeletonReport:
    """A report of empty headings is worse than an honest explanation: it reads as a
    broken app. Observed on `rough-standup-notes`, which cleared one client-safe item
    and produced five bare headings."""

    async def test_a_skeleton_report_is_replaced_by_the_explanation(self):
        from app.config import get_settings

        skeleton = (
            "## Overall status: Red\n\n## Summary\n\n## Progress this period\n\n"
            "## Next steps\n\n## Risks and issues\n\n## Support needed from the client\n"
        )
        writer = FakeWriter([skeleton])
        items = [
            _item("c1", audience="client_safe"),
            _item("c2", audience="internal_only"),
            _item("c3", audience="internal_only"),
        ]
        docs, _ = await run_generation(
            payload=_request(items), provider=writer, settings=get_settings()
        )
        assert docs.status_report_empty is True
        assert "No client-facing items" in docs.status_report_markdown
        assert "2 of 3" in docs.status_report_markdown

    async def test_a_substantive_report_is_kept(self):
        from app.config import get_settings

        real = (
            "## Overall status: Red\nThe go-live date has moved.\n\n## Summary\n"
            "Migration testing continues against the agreed plan and the revised "
            "go-live date of 29 May, with rehearsal cycles now running weekly.\n\n"
            "## Next steps\n- Complete the transformation fix by 27 March."
        )
        writer = FakeWriter([real])
        docs, _ = await run_generation(
            payload=_request([_item("c1", audience="client_safe")]),
            provider=writer,
            settings=get_settings(),
        )
        assert docs.status_report_empty is False
        assert "Migration testing continues" in docs.status_report_markdown

    def test_substantive_body_ignores_headings_and_bullets(self):
        from app.pipeline.generate import substantive_body

        assert substantive_body("## A\n\n## B\n\n- \n") == ""
        assert "real content" in substantive_body("## A\n- real content here\n")
