"""Routing policy: thresholds, Score banding, Noul banding, audience fail-safe.

All of it lives in code so wording and weights can change without re-running any
inference. Nothing here calls a model.
"""

import math
from typing import Literal

from app.config import Settings
from app.models import Decision

OwnerStatus = Literal["stated", "inferred", "not_specified"]
Routing = Literal["auto", "suggested", "review"]

INTERNAL_ONLY = "internal_only"
CLIENT_SAFE = "client_safe"


def band_score(score: float, levels: list[str]) -> str:
    """Turn a Score float into its nearest level's label.

    A Score is a probability-weighted *position* and lands between levels — a real
    measured answer was 1.74 on a 0-2 scale, meaning "mostly High, partly Medium".
    Round to nearest, so band i covers [i - 0.5, i + 0.5). Symmetric, so no band is
    quietly wider than another.

    The label is the text before the first colon of the level description, so the
    rubric and the label can never drift apart.
    """
    # math.floor(x + 0.5), not round(): Python's round() is banker's rounding, so
    # round(0.5) == 0 and 0.5 would band Low instead of Medium, while round(1.5) == 2.
    # That would make the boundaries inconsistent in a way no rubric could explain.
    index = max(0, min(len(levels) - 1, math.floor(score + 0.5)))
    return levels[index].split(":", 1)[0].strip()


def band_noul(value: float, settings: Settings) -> OwnerStatus:
    """Band a Noul probability into stated / inferred / not_specified.

    Noul answers carry **no confidence field** — only a probability — so the value
    itself is banded. The middle band means "the model is genuinely unsure whether
    this was stated", which is not the same as "half stated".
    """
    if value >= settings.noul_yes:
        return "stated"
    if value <= settings.noul_no:
        return "not_specified"
    return "inferred"


def apply_audience_failsafe(audience: Decision, settings: Settings) -> Decision:
    """Force `internal_only` unless the model is confidently sure it is client-safe.

    Asymmetric on purpose: wrongly marking an item internal costs a line in a status
    report, while wrongly marking it client-safe leaks blame or staffing detail to the
    client. Only one direction gets the benefit of the doubt.

    Gates on the **probability**, not the confidence. `audience` has two options, and
    for k = 2 confidence is `2 * p_max - 1` — so thresholding confidence at 0.80 was
    really demanding `p >= 0.90`. Measured on the Northwind sample, that flipped 12 of
    16 items to internal although Jev judged every one client-safe, producing a client
    report that withheld the project's own RAG decision. The probability is also the
    honest thing to explain: "shown to the client only if Jev is at least 85% sure it
    is safe."
    """
    if audience.label != CLIENT_SAFE:
        return audience
    probabilities = audience.probabilities or {}
    p_safe = probabilities.get(CLIENT_SAFE)
    if p_safe is None:
        # No distribution to judge; fall back to confidence and stay cautious.
        p_safe = audience.confidence if audience.confidence is not None else 0.0
    if p_safe >= settings.conf_audience_safe:
        return audience
    return Decision(
        label=INTERNAL_ONLY,
        confidence=audience.confidence,
        probabilities=audience.probabilities,
        value=audience.value,
    )


def route(kind: Decision, audience: Decision, settings: Settings) -> Routing:
    """auto / suggested / review, from the confidence on kind and audience."""
    scores = [
        kind.confidence if kind.confidence is not None else 0.0,
        audience.confidence if audience.confidence is not None else 0.0,
    ]
    if min(scores) < settings.conf_review:
        return "review"
    if min(scores) >= settings.conf_auto:
        return "auto"
    return "suggested"
