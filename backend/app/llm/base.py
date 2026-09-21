"""The contract every LLM provider satisfies."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.models import LLMUsage

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """A provider failed in a way the caller should surface, not retry blindly."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


class RateLimited(LLMError):
    """429. Back off on the *same* model — never escalate; the token bucket is shared.

    `scope` distinguishes the two limits, which need completely different responses:
      * "minute" — the 8,000 tokens/minute bucket. Wait seconds and retry.
      * "day"    — the **200,000 tokens/day** cap. Retrying is pointless for hours,
                   and the user must be told that plainly rather than watching a
                   spinner. This limit appears in **no response header**; it is only
                   visible in the 429 body, which is why it can exhaust silently.
    """

    def __init__(self, message: str, *, status=None, retry_after=None, scope="minute"):
        super().__init__(message, status=status, retry_after=retry_after)
        self.scope = scope


class JSONInvalid(LLMError):
    """The model returned something that does not satisfy the schema."""


class Transient(LLMError):
    """A timeout or 5xx: worth one more attempt, on the same model."""


class Truncated(LLMError):
    """The response hit `max_completion_tokens`.

    Needs its own type because under strict `json_schema` a truncated response still
    *parses* — the constrained decoder closes the JSON — so it looks like success
    while silently dropping items. Retried once at the ceiling cap.
    """


class LLMProvider(Protocol):
    """Returns a validated pydantic model, never raw text.

    Implementations must not log prompt or transcript content (Hard Rule 5).
    """

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_model: type[T],
        stage: str,
        max_completion_tokens: int | None = None,
    ) -> tuple[T, LLMUsage]: ...
