"""Every Jev question spec, as data.

Question ids are **not sent to the model** (confirmed in the live API docs), so each
question must be completely self-describing in `instructions` + `criteria`. Wording
lives here, in one place, so tuning never means touching request code.

All five item questions go in a single request per candidate: they are independent,
Jev evaluates them in parallel, and the speculative ones (severity and audience on
something that turns out to be `discussion_only`) cost almost nothing. This is the
docs' **speculative fan-out** pattern.
"""

from typing import Any

# Order matters only for display; Jev evaluates them in parallel.
ITEM_KIND_OPTIONS = [
    "action_item",
    "risk",
    "assumption",
    "issue",
    "dependency",
    "decision",
    "discussion_only",
]

SEVERITY_LEVELS = [
    "Low: cosmetic or minor; no effect on dates, cost, or quality",
    "Medium: could delay or degrade part of the delivery if unaddressed",
    "High: threatens a milestone, go-live, budget, or the client relationship",
]

AUDIENCE_OPTIONS = ["client_safe", "internal_only"]

ITEM_QUESTIONS: dict[str, dict[str, Any]] = {
    "item_kind": {
        "type": "choice",
        "instructions": (
            "Based on `item.evidence` and `surrounding_context`, what kind of "
            "project item is this?"
        ),
        "criteria": {
            "action_item": (
                "A concrete task a named or implied person committed to doing."
            ),
            "risk": (
                "Something that might go wrong in the future and is not yet happening."
            ),
            "assumption": (
                "Something the team is treating as true without having confirmed it."
            ),
            "issue": (
                "A problem that is already happening and affects work now."
            ),
            "dependency": (
                "Something the project is waiting on from another team, vendor, "
                "or the client."
            ),
            "decision": "A choice that was agreed during the meeting.",
            # The no-match outcome. Without it the model is forced to mislabel
            # ordinary conversation as one of the real categories.
            "discussion_only": (
                "General discussion, opinion, or status narration with no "
                "commitment, risk, or decision."
            ),
        },
    },
    "severity": {
        "type": "score",
        "instructions": "How much impact does this item have on project delivery?",
        "criteria": SEVERITY_LEVELS,
    },
    # The instructions deliberately ask about HARM, not about report-worthiness.
    # An earlier wording ("Should this item appear in a status report sent to the
    # client?") asked whether the item was worth reporting, while the criteria
    # described whether it was safe to report. Jev split the difference on ordinary
    # technical facts, which for a two-option Choice compresses confidence badly
    # (confidence = 2*p_max - 1), and the audience fail-safe then forced almost every
    # item to internal_only. The question now matches its own criteria.
    "audience": {
        "type": "choice",
        "instructions": (
            "A status report will be sent to the client. Would it cause harm or "
            "embarrassment for the client to read this item as written?"
        ),
        "criteria": {
            "client_safe": (
                "Factual and professional. Ordinary project information -- tasks, "
                "owners, dates, defects, risks, dependencies, decisions, slipped "
                "milestones and bad news stated plainly -- is client_safe. Bad news "
                "is not by itself unsafe; clients are told about problems routinely."
            ),
            "internal_only": (
                "Reading it would damage trust or cause embarrassment. It criticises "
                "or blames the client or their staff, reveals internal opinion or "
                "disagreement, exposes commercial, pricing or staffing matters, or "
                "admits an internal failing in words the team would not say to the "
                "client's face."
            ),
        },
    },
    "owner_explicit": {
        "type": "noul",
        "instructions": (
            "`item.evidence` explicitly names the person responsible for this item."
        ),
        "criteria": {
            "true": (
                "A specific person is named as responsible, or says they will do it "
                "themselves."
            ),
            "false": (
                "No person is named as responsible, or responsibility is only "
                "guessed at from who happened to be speaking."
            ),
        },
    },
    "due_explicit": {
        "type": "noul",
        "instructions": (
            "`item.evidence` explicitly states a deadline or due date for this item."
        ),
        "criteria": {
            "true": "A date, day, or explicit deadline is stated for this item.",
            "false": (
                "No deadline is stated, or the timing is vague such as 'soon', "
                "'at some point', or 'when I get a sec'."
            ),
        },
    },
}

RAG_DIMENSIONS = ["schedule", "scope", "resourcing", "client_sentiment"]

RAG_QUESTIONS: dict[str, dict[str, Any]] = {
    "schedule": {
        "type": "choice",
        "instructions": (
            "Based on `items` and `summary`, how is this project tracking against "
            "its schedule?"
        ),
        "criteria": {
            "on_track": "Dates are being met; no milestone is currently threatened.",
            "at_risk": (
                "A milestone could slip if something is not addressed, but nothing "
                "has slipped yet."
            ),
            "off_track": (
                "A milestone, go-live, or delivery date has already slipped or is "
                "certain to."
            ),
        },
    },
    "scope": {
        "type": "choice",
        "instructions": "How is the scope of this project behaving?",
        "criteria": {
            "stable": "Scope is settled; no new work is appearing.",
            "changing": (
                "Scope is moving, but the changes are being discussed and managed."
            ),
            "uncontrolled": (
                "Work is being added or changed without agreement, or nobody can "
                "say what is in scope."
            ),
        },
    },
    "resourcing": {
        "type": "choice",
        "instructions": "How is this project resourced for the work in front of it?",
        "criteria": {
            "adequate": "The team can cover the work.",
            "stretched": (
                "The team is covering the work but with no slack, or depends on one "
                "person for something critical."
            ),
            "blocked": (
                "Work cannot proceed because people or skills are missing."
            ),
        },
    },
    "client_sentiment": {
        "type": "score",
        "instructions": "How does the client feel about this project right now?",
        "criteria": [
            "Negative / escalating: the client is dissatisfied, frustrated, or "
            "escalating internally.",
            "Neutral / mixed: the client is engaged and businesslike, with concerns "
            "but no dissatisfaction.",
            "Positive / satisfied: the client is pleased with progress.",
        ],
    },
}
