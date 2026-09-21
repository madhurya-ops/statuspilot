"""GET /api/budget — how much Groq token budget is left, and the resulting wait.

Exists so the UI can show *"Free-tier token budget refilling — 18s"* with a real
countdown instead of a bare spinner. A PM reading that sees cost-awareness; a PM
watching an unexplained spinner sees a slow app.
"""

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.llm.groq_client import budget_snapshot
from app.models import BudgetStatus
from app.security import require_access_code

router = APIRouter(tags=["meta"], dependencies=[Depends(require_access_code)])

# Groq's per-minute bucket refills continuously (`x-ratelimit-reset-tokens: 547ms`)
# rather than resetting on a window boundary.
DEFAULT_LIMIT = 8000
REFILL_PER_SECOND = DEFAULT_LIMIT / 60


@router.get("/api/budget", response_model=BudgetStatus)
def budget(
    needed: int = 4000,
    settings: Settings = Depends(get_settings),
) -> BudgetStatus:
    snapshot = budget_snapshot()
    limit = int(snapshot.get("limit", DEFAULT_LIMIT))
    refill = limit / 60
    known = "remaining" in snapshot

    if not known:
        # Nothing observed yet this process. Assume a full bucket rather than
        # inventing a wait the user would sit through for no reason.
        return BudgetStatus(
            limit_tokens=limit,
            remaining_tokens=limit,
            refill_per_second=refill,
            wait_seconds=0.0,
            needed_tokens=needed,
            known=False,
        )

    import time

    elapsed = max(0.0, time.time() - snapshot.get("at", 0.0))
    remaining = min(float(limit), snapshot["remaining"] + elapsed * refill)
    shortfall = max(0.0, needed - remaining)
    return BudgetStatus(
        limit_tokens=limit,
        remaining_tokens=int(remaining),
        refill_per_second=refill,
        wait_seconds=round(shortfall / refill, 1),
        needed_tokens=needed,
        known=True,
    )
