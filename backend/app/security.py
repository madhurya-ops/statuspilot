"""Access control, rate limiting, and request-size guards.

None of this is a real auth system — the app is a stateless demo behind a shared
access code (Hard Rule 11). It exists so a public Vercel URL cannot be used as a
free LLM proxy, not to protect user data.
"""

import time
from collections import defaultdict, deque

from fastapi import Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings

ACCESS_CODE_HEADER = "X-Access-Code"

# IP -> timestamps of recent requests.
#
# Best-effort only. On Vercel each function instance has its own memory and
# instances come and go, so this limits a burst from one client against one warm
# instance and nothing more. It is a guard rail, not a guarantee. A real limit
# would need shared state, which Hard Rule 11 rules out for this build.
_HITS: dict[str, deque[float]] = defaultdict(deque)


def reset_rate_limiter() -> None:
    """Clear all counters. Used by tests to isolate cases."""
    _HITS.clear()


def _client_ip(request: Request) -> str:
    # Vercel terminates TLS upstream, so the socket peer is a proxy. The first
    # entry of X-Forwarded-For is the original client.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_access_code(
    request: Request,
    x_access_code: str | None = Header(default=None, alias=ACCESS_CODE_HEADER),
    settings: Settings = Depends(get_settings),
) -> None:
    """Reject requests without the shared demo access code, then rate-limit them.

    Ordering matters: the rate limit is applied *after* the code check so that
    unauthenticated traffic cannot exhaust a legitimate client's budget.
    """
    if not settings.demo_access_code:
        # Refuse to run wide open. A blank code in production would expose the
        # Groq and TypeSafe keys to anyone with the URL.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server is not configured with an access code.",
        )

    if x_access_code != settings.demo_access_code:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing access code.",
        )

    _enforce_rate_limit(_client_ip(request), settings.rate_limit_per_min)


def _enforce_rate_limit(ip: str, per_min: int) -> None:
    now = time.monotonic()
    hits = _HITS[ip]
    while hits and now - hits[0] >= 60.0:
        hits.popleft()
    if len(hits) >= per_min:
        retry_after = max(1, int(60.0 - (now - hits[0])))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a moment.",
            headers={"Retry-After": str(retry_after)},
        )
    hits.append(now)


def guard_text_size(text: str, settings: Settings) -> str:
    """Reject transcript text above MAX_INPUT_CHARS.

    413 rather than 400: the input is well-formed, just too large. The message
    carries both numbers so the UI can explain the limit instead of just refusing.
    """
    if len(text) > settings.max_input_chars:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"Transcript is {len(text):,} characters; the limit is "
                f"{settings.max_input_chars:,}."
            ),
        )
    return text
