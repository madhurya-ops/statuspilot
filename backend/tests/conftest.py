"""Shared fixtures.

Hard Rule 8: tests never call real APIs. Every test here runs against the FastAPI
app in-process with mock providers and a known access code.
"""

import os

import pytest

# Set before app.config is imported so pydantic-settings picks these up rather
# than the developer's real backend/.env.
os.environ.update(
    {
        "LLM_PRIMARY": "mock",
        "DECISION_ENGINE": "mock",
        "GROQ_API_KEY": "",
        "TYPESAFE_API_KEY": "",
        "DEMO_ACCESS_CODE": "test-code",
        "ALLOWED_ORIGINS": "http://localhost:5173,https://statuspilot-web.vercel.app",
        "RATE_LIMIT_PER_MIN": "10",
    }
)

from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.security import reset_rate_limiter  # noqa: E402

ACCESS_CODE = "test-code"


@pytest.fixture
def client() -> TestClient:
    get_settings.cache_clear()
    reset_rate_limiter()
    return TestClient(app)


@pytest.fixture
def auth() -> dict[str, str]:
    return {"X-Access-Code": ACCESS_CODE}
