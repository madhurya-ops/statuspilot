"""Candidates -> classified items + project RAG.

Runs the configured engine. If Jev fails for the **whole run**, falls back to Groq
automatically and reports `stats.engine = "llm"` so the UI can say so out loud.
"""

import logging

from app.config import Settings
from app.decide.base import DecisionEngine, DecisionError
from app.decide.jev import JevEngine
from app.decide.llm_fallback import LLMFallbackEngine
from app.decide.mock import MockEngine
from app.decide.questions import ITEM_QUESTIONS, SEVERITY_LEVELS
from app.decide.routing import (
    INTERNAL_ONLY,
    apply_audience_failsafe,
    band_noul,
    band_score,
    route,
)
from app.decide.state import build_item_state
from app.models import (
    Candidate,
    ClassifiedItem,
    ClassifyResponse,
    Decision,
    ExtractResponse,
    RunStats,
)
from app.pipeline import rag as rag_module

log = logging.getLogger(__name__)

DROP_KIND = "discussion_only"


def build_engine(settings: Settings) -> DecisionEngine:
    if settings.decision_engine == "mock":
        return MockEngine(settings)
    if settings.decision_engine == "llm":
        return LLMFallbackEngine(settings)
    return JevEngine(settings)


async def run_classification(
    *,
    extracted: ExtractResponse,
    settings: Settings,
    project_name: str | None = None,
    engine: DecisionEngine | None = None,
) -> ClassifyResponse:
    candidates = extracted.candidates[: settings.max_candidates]
    states = [
        build_item_state(candidate, extracted.lines, extracted.meta, project_name=project_name)
        for candidate in candidates
    ]

    engine = engine or build_engine(settings)
    try:
        answers, stats = await engine.judge(states, ITEM_QUESTIONS)
    except DecisionError as err:
        if engine.name != "jev" or settings.llm_primary == "mock":
            raise
        # Whole-run failure only. A single bad candidate does not trigger this.
        log.warning("jev failed for the whole run (%s); falling back to the LLM", err)
        engine = LLMFallbackEngine(settings)
        answers, stats = await engine.judge(states, ITEM_QUESTIONS)

    items: list[ClassifiedItem] = []
    dropped: list[ClassifiedItem] = []
    for candidate, answer in zip(candidates, answers, strict=True):
        if not answer:
            continue
        item = _assemble(candidate, answer, settings, engine.name)
        # A confidently-irrelevant item is dropped from the outputs but kept so the
        # PM can restore it. An *unconfident* discussion_only stays in the queue.
        if item.kind.label == DROP_KIND and item.routing == "auto":
            dropped.append(item)
        else:
            items.append(item)

    accepted = [
        {
            "id": item.candidate.id,
            "text": item.candidate.text,
            "kind": item.kind.label,
            "severity": item.severity.label,
        }
        for item in items
    ]
    rag, rag_stats = await rag_module.assess(
        items=accepted,
        summary=extracted.discussion_points,
        meta=extracted.meta,
        engine=engine,
        settings=settings,
        project_name=project_name,
    )

    combined = RunStats(
        engine=engine.name,
        requests=stats.requests + rag_stats.requests,
        latency_ms=stats.latency_ms + rag_stats.latency_ms,
        input_tokens=(stats.input_tokens or 0) + (rag_stats.input_tokens or 0),
        output_tokens=(stats.output_tokens or 0) + (rag_stats.output_tokens or 0),
    )
    log.info(
        "classify engine=%s items=%d dropped=%d review=%d rag=%s requests=%d ms=%d",
        engine.name,
        len(items),
        len(dropped),
        sum(1 for i in items if i.routing == "review"),
        rag.status,
        combined.requests,
        combined.latency_ms,
    )
    return ClassifyResponse(items=items, rag=rag, stats=combined, dropped=dropped)


def _assemble(
    candidate: Candidate,
    answer: dict[str, Decision],
    settings: Settings,
    engine_name: str,
) -> ClassifiedItem:
    kind = answer.get("item_kind") or Decision(label=DROP_KIND, confidence=0.0)

    severity = answer.get("severity") or Decision(label="", confidence=0.0, value=0.0)
    severity_value = severity.value if severity.value is not None else 0.0
    severity = Decision(
        label=band_score(severity_value, SEVERITY_LEVELS),
        confidence=severity.confidence,
        probabilities=severity.probabilities,
        value=severity_value,
    )

    audience = answer.get("audience") or Decision(label=INTERNAL_ONLY, confidence=0.0)
    audience = apply_audience_failsafe(audience, settings)

    owner_noul = (answer.get("owner_explicit") or Decision(label="", value=0.0)).value or 0.0
    due_noul = (answer.get("due_explicit") or Decision(label="", value=0.0)).value or 0.0

    return ClassifiedItem(
        candidate=candidate,
        kind=kind,
        severity=severity,
        audience=audience,
        severity_value=severity_value,
        owner_explicit=owner_noul,
        due_explicit=due_noul,
        owner_status=band_noul(owner_noul, settings),
        due_status=band_noul(due_noul, settings),
        routing=route(kind, audience, settings),
        engine=engine_name,  # type: ignore[arg-type]
    )
