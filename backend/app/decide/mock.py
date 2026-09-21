"""Deterministic decision engine for tests and offline demos.

Derives its answers from the state so tests assert on real relationships, and
deliberately produces **low-confidence items** so the review queue is exercised.
"""

import hashlib
from typing import Any

from app.decide.questions import ITEM_KIND_OPTIONS
from app.models import Decision, RunStats

# Markers of genuine uncertainty in the source text. The mock lowers its confidence
# on these so the review queue is exercised offline, which is the whole reason the
# `rough-standup-notes` sample exists.
VAGUE = (
    "maybe", "should probably", "should ", "at some point", "when i get a sec",
    "chk", "?", "not sure", "unclear", "nobody", "never", "~", "might", "i think",
    "pending", "stale", "tbd", "some point",
)


def _seed(text: str) -> float:
    digest = hashlib.sha256(text.encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


class MockEngine:
    name = "mock"

    def __init__(self, settings=None):
        self._settings = settings

    async def judge(
        self,
        states: list[dict[str, Any]],
        questions: dict[str, dict[str, Any]],
    ) -> tuple[list[dict[str, Decision]], RunStats]:
        answers = [self._one(state, questions) for state in states]
        return answers, RunStats(
            engine=self.name,
            requests=len(states),
            latency_ms=1,
            input_tokens=0,
            output_tokens=0,
        )

    def _one(
        self, state: dict[str, Any], questions: dict[str, dict[str, Any]]
    ) -> dict[str, Decision]:
        item = state.get("item", {}) if isinstance(state, dict) else {}
        evidence = str(item.get("evidence", "") or state)
        lowered = evidence.lower()
        vague = any(marker in lowered for marker in VAGUE)
        seed = _seed(evidence)

        out: dict[str, Decision] = {}
        for key, spec in questions.items():
            kind = spec["type"]
            if kind == "choice":
                options = list(spec["criteria"].keys())
                label = self._choice_label(key, lowered, options, seed)
                # Vague evidence gets deliberately low confidence so the review
                # queue always has something to show in offline mode.
                confidence = 0.35 + seed * 0.1 if vague else 0.82 + seed * 0.17
                probs = {option: (1 - confidence) / (len(options) - 1) for option in options}
                probs[label] = confidence
                out[key] = Decision(label=label, confidence=confidence, probabilities=probs)
            elif kind == "score":
                levels = spec["criteria"]
                value = round(seed * (len(levels) - 1), 2)
                probs = {str(i): 1.0 / len(levels) for i in range(len(levels))}
                out[key] = Decision(
                    label="", confidence=0.45 if vague else 0.8, probabilities=probs, value=value
                )
            else:  # noul
                stated = (key == "owner_explicit" and item.get("stated_owner")) or (
                    key == "due_explicit" and item.get("stated_due")
                )
                if stated:
                    value = 0.9
                elif vague:
                    value = 0.5  # genuinely unsure -> "inferred"
                else:
                    value = 0.1
                out[key] = Decision(label="", confidence=None, probabilities=None, value=value)
        return out

    def _choice_label(self, key: str, lowered: str, options: list[str], seed: float) -> str:
        if key == "audience":
            blame = ("honestly", "never reviews", "their team", "blame", "optimistic")
            return "internal_only" if any(w in lowered for w in blame) else "client_safe"
        if key == "item_kind":
            for marker, label in (
                ("risk", "risk"),
                ("assum", "assumption"),
                ("waiting on", "dependency"),
                ("decision", "decision"),
                ("will ", "action_item"),
                ("i'll", "action_item"),
            ):
                if marker in lowered and label in options:
                    return label
            return ITEM_KIND_OPTIONS[int(seed * len(ITEM_KIND_OPTIONS)) % len(ITEM_KIND_OPTIONS)]
        return options[int(seed * len(options)) % len(options)]
