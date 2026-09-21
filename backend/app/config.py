"""All environment configuration for StatusPilot.

Every value in `backend/.env.example` is declared here. Nothing reads `os.environ`
directly, so the full configuration surface is visible in one file.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

VERSION = "0.1.0"

ReasoningEffort = Literal["low", "medium", "high"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # GROQ_MODEL etc. would otherwise collide with pydantic's own `model_` namespace.
        protected_namespaces=(),
    )

    # --- LLM (Groq only) ---
    llm_primary: Literal["groq", "mock"] = "groq"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    # Quality escalation on repeated JSON/validation failure ONLY. Never on 429:
    # both models share one token bucket, so swapping model for a rate limit buys nothing.
    groq_model_escalation: str = "openai/gpt-oss-120b"
    # gpt-oss are reasoning models; hidden reasoning tokens bill against the 8k TPM budget.
    groq_reasoning_effort_extract: ReasoningEffort = "low"
    groq_reasoning_effort_generate: ReasoningEffort = "low"

    # --- Judgments (Jev) ---
    decision_engine: Literal["jev", "llm", "mock"] = "jev"
    typesafe_api_key: str = ""
    typesafe_base_url: str = "https://api.typesafe.ai/v1"
    jev_model: str = "jev-latest"
    jev_concurrency: int = Field(default=5, ge=1, le=32)
    jev_timeout_s: float = Field(default=20.0, gt=0)

    # --- Routing thresholds (policy lives in code, values here) ---
    conf_auto: float = Field(default=0.80, ge=0.0, le=1.0)
    conf_review: float = Field(default=0.50, ge=0.0, le=1.0)
    noul_yes: float = Field(default=0.75, ge=0.0, le=1.0)
    noul_no: float = Field(default=0.35, ge=0.0, le=1.0)

    # --- App ---
    demo_access_code: str = ""
    allowed_origins: str = "http://localhost:5173"
    max_input_chars: int = Field(default=12_000, gt=0)
    max_upload_bytes: int = Field(default=1_000_000, gt=0)
    max_candidates: int = Field(default=40, gt=0)
    rate_limit_per_min: int = Field(default=10, gt=0)
    cached_samples: bool = True

    @field_validator("allowed_origins")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def origins(self) -> list[str]:
        """ALLOWED_ORIGINS as a list. Comma-separated in the environment."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    def require_thresholds_ordered(self) -> None:
        """Fail loudly on a threshold ordering that would silently break routing.

        `conf_review` must sit below `conf_auto`, otherwise the "suggested" band is
        empty and every item is either auto-accepted or sent to review. Likewise
        `noul_no` below `noul_yes`, otherwise the "inferred" band vanishes.
        """
        if self.conf_review > self.conf_auto:
            raise ValueError("CONF_REVIEW must be <= CONF_AUTO")
        if self.noul_no > self.noul_yes:
            raise ValueError("NOUL_NO must be <= NOUL_YES")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.require_thresholds_ordered()
    return settings
