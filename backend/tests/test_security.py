"""Gate 1: access code, rate limiting, size guard, CORS.

`require_access_code` is exercised through a throwaway app rather than a real
route, so these stay true as routers are added in later phases.
"""

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.config import get_settings
from app.security import guard_text_size, require_access_code, reset_rate_limiter


@pytest.fixture
def guarded() -> TestClient:
    reset_rate_limiter()
    get_settings.cache_clear()
    probe = FastAPI()

    @probe.get("/probe", dependencies=[Depends(require_access_code)])
    def _probe():
        return {"ok": True}

    return TestClient(probe)


def test_missing_access_code_is_rejected(guarded):
    assert guarded.get("/probe").status_code == 401


def test_wrong_access_code_is_rejected(guarded):
    r = guarded.get("/probe", headers={"X-Access-Code": "not-the-code"})
    assert r.status_code == 401


def test_correct_access_code_is_accepted(guarded):
    r = guarded.get("/probe", headers={"X-Access-Code": "test-code"})
    assert r.status_code == 200


def test_rate_limit_triggers_after_the_configured_number(guarded):
    """RATE_LIMIT_PER_MIN is 10 in tests, so the 11th call must be refused."""
    headers = {"X-Access-Code": "test-code"}
    for i in range(10):
        assert guarded.get("/probe", headers=headers).status_code == 200, f"call {i + 1}"
    r = guarded.get("/probe", headers=headers)
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_rate_limit_is_not_spent_by_unauthenticated_requests(guarded):
    """A 401 must not consume a legitimate client's budget."""
    for _ in range(20):
        assert guarded.get("/probe").status_code == 401
    assert guarded.get("/probe", headers={"X-Access-Code": "test-code"}).status_code == 200


def test_size_guard_rejects_oversized_text():
    settings = get_settings()
    too_long = "x" * (settings.max_input_chars + 1)
    with pytest.raises(HTTPException) as err:
        guard_text_size(too_long, settings)
    assert err.value.status_code == 413
    assert str(settings.max_input_chars) in err.value.detail.replace(",", "")


def test_size_guard_allows_text_at_the_limit():
    settings = get_settings()
    exact = "x" * settings.max_input_chars
    assert guard_text_size(exact, settings) == exact


def test_cors_allows_the_configured_origin(client):
    r = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_preflight_permits_the_access_code_header(client):
    r = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Access-Code",
        },
    )
    assert r.status_code == 200
    assert "x-access-code" in r.headers.get("access-control-allow-headers", "").lower()


def test_cors_rejects_an_unknown_origin(client):
    r = client.get("/api/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in r.headers
