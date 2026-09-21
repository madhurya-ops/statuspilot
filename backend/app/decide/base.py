"""The contract every decision engine satisfies."""

from typing import Any, Protocol

from app.models import Decision, RunStats


class DecisionError(Exception):
    """The engine failed for the whole run; the caller should fall back."""


class DecisionEngine(Protocol):
    name: str

    async def judge(
        self,
        states: list[dict[str, Any]],
        questions: dict[str, dict[str, Any]],
    ) -> tuple[list[dict[str, Decision]], RunStats]:
        """Answer `questions` about each state. Returns one answer map per state."""
        ...
