"""Project-level RAG: one Jev request, combined in code.

The docs' **composite scoring** pattern — ask each dimension separately, then apply
weights and rules the code owns. Keeping the combination in code means the rule can
be shown to the PM on the "How it works" screen and changed without re-running
inference.
"""

from typing import Any

from app.config import Settings
from app.decide.base import DecisionEngine
from app.decide.questions import RAG_QUESTIONS
from app.decide.state import build_rag_state
from app.models import Decision, MeetingMeta, RagResult, RunStats

# A score below this means the model actually says "Negative / escalating".
# The original plan said `client_sentiment == level 0`, which is exact equality on a
# float and would essentially never fire. 0.5 is the band equivalent, consistent with
# the round-to-nearest banding used for severity.
SENTIMENT_RED_BELOW = 0.5

RED_LABELS = {"schedule": "off_track", "scope": "uncontrolled", "resourcing": "blocked"}
AMBER_LABELS = {"schedule": "at_risk", "scope": "changing", "resourcing": "stretched"}

REASONS = {
    "schedule": {"off_track": "a milestone has slipped", "at_risk": "a milestone is at risk"},
    "scope": {"uncontrolled": "scope is uncontrolled", "changing": "scope is changing"},
    "resourcing": {"blocked": "work is blocked on people", "stretched": "the team is stretched"},
}


def combine(dimensions: dict[str, Decision]) -> RagResult:
    """Apply the RAG rule. Pure function of the four answers — no model call."""
    reasons: list[str] = []
    status = "Green"

    for key, red_label in RED_LABELS.items():
        decision = dimensions.get(key)
        if decision is None:
            continue
        if decision.label == red_label:
            status = "Red"
            reasons.append(REASONS[key][red_label])
        elif decision.label == AMBER_LABELS[key] and status != "Red":
            status = "Amber"

    sentiment = dimensions.get("client_sentiment")
    if sentiment is not None and sentiment.value is not None:
        if sentiment.value < SENTIMENT_RED_BELOW:
            status = "Red"
            reasons.append("the client is dissatisfied or escalating")
        elif sentiment.value < 1.5 and status == "Green":
            status = "Amber"

    # Amber reasons are only collected once the status is known, so a dimension that
    # is merely "at_risk" does not add noise to a Red explanation.
    if status == "Amber" and not reasons:
        for key in RED_LABELS:
            decision = dimensions.get(key)
            if decision is not None and decision.label == AMBER_LABELS[key]:
                reasons.append(REASONS[key][AMBER_LABELS[key]])
        if not reasons and sentiment is not None and (sentiment.value or 2.0) < 1.5:
            reasons.append("client sentiment is mixed")

    confidences = [d.confidence for d in dimensions.values() if d.confidence is not None]
    confidence = min(confidences) if confidences else 0.0

    if status == "Green":
        reason = "No milestone, scope, resourcing or client-sentiment concern was raised."
    else:
        reason = f"{status} because " + ", and ".join(reasons) + "."

    return RagResult(
        status=status, confidence=confidence, dimensions=dimensions, reason=reason
    )


async def assess(
    *,
    items: list[dict[str, Any]],
    summary: list[str],
    meta: MeetingMeta,
    engine: DecisionEngine,
    settings: Settings,
    project_name: str | None = None,
) -> tuple[RagResult, RunStats]:
    state = build_rag_state(items, summary, meta, project_name=project_name)
    answers, stats = await engine.judge([state], RAG_QUESTIONS)
    dimensions = answers[0] if answers else {}
    return combine(dimensions), stats
