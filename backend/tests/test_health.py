"""Gate 1: health endpoint works and leaks nothing."""


def test_health_returns_ok_without_an_access_code(client):
    """Health is deliberately unauthenticated so a deploy is verifiable from a phone."""
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["llm_primary"] == "mock"
    assert body["decision_engine"] == "mock"
    assert body["groq_model"]


def test_health_exposes_no_secrets(client):
    """The response must name models, never keys or even their presence."""
    body = client.get("/api/health").json()
    assert set(body) == {"status", "version", "llm_primary", "decision_engine", "groq_model"}
    blob = str(body).lower()
    for forbidden in ("gsk_", "api_key", "apikey", "token", "secret", "typesafe_api"):
        assert forbidden not in blob
