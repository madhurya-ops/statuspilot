# Jev design notes

Written in Phase 4 after reading the live docs, as Section 2A requires.

## Docs read (2026-09-21)

| Page | What it settled |
|---|---|
| `api.md` | Request/response shapes for all three primitives; error codes |
| `concepts/state.md` | State may be a string, object or array; **an object with named fields is the recommended default** |
| `primitives/score.md` | Levels are positions `0..n-1`; `score` can land **between** levels; `legend` maps level→description |
| `primitives/noul.md` | Noul returns a bare probability; optional `criteria.true` / `.false` |
| `confidence.md` | Confidence is distribution concentration, and the three-band pattern |
| `patterns/fan-out.md` | Ask every question in one request; they run in parallel; speculative questions are cheap |
| `patterns/confidence-routing.md` | **Thresholds scale with risk** — different actions gate at different levels |
| `models.md` | Rate limits, context budget, pricing |

**Section 6 of `execution.md` survives contact with the docs.** The named-JSON state,
the one-request-per-candidate fan-out with all five questions, the no-match
`discussion_only` outcome, and three-band confidence routing are all exactly what the
docs recommend. The closest pattern is **speculative fan-out** combined with
**confidence-gated routing**; `pipeline/rag.py` is **composite scoring**.

Two things the docs sharpened:

1. **Thresholds should scale with risk, not be uniform.** The confidence-routing page
   gates a read-only action at 0.6 and a destructive one at 0.85 *in the same system*.
   That is the doctrinal basis for Section 6's **audience fail-safe**: `audience` is
   the high-stakes question, because being wrong leaks an internal remark to a client,
   so it gets a stricter gate than `item_kind`.
2. **Confidence is not correctness.** It measures how concentrated the probability
   distribution is. Low confidence on a Choice usually means no option is a clear
   winner — which is information, not failure.

## Rate limits — measured, because there are no headers

**TypeSafe returns no `x-ratelimit-*` headers.** A successful response carries only
`date`, `server`, `content-type`, `x-typesafe-request-id` and
`x-envoy-upstream-service-time`. The ceiling cannot be read from a response the way
Groq's can, so it was taken from `models.md` and then verified by measurement.

**Published for `jev-1.13.0`:** 250,000 tokens/second · **1,200 requests/minute** ·
64k context per request (32k for `state` plus the longest question) ·
**$42 per Btok input, output free**.

> The docs carry an explicit warning that these limits **change without notice** while
> capacity is being expanded. Treat the numbers below as a snapshot, not a contract.

### Measured fan-out — 20 candidates, 5 questions each

| Concurrency | Wall time | p50 latency | 429s |
|---:|---:|---:|---:|
| 1 | 9,168 ms | 393 ms | 0 |
| 5 | 3,657 ms | 438 ms | 0 |
| **10** | **2,289 ms** | 1,200 ms | **0** |
| 20 | 1,505 ms | 1,366 ms | 0 |

**`JEV_CONCURRENCY` is set to 10**, not the placeholder 5:

- It is **1.6x faster** than 5 (2.3 s vs 3.7 s for 20 candidates) and the returns
  past 10 are small in absolute terms — 20 saves a further 0.8 s.
- At 10 in flight with ~1.2 s latency the sustained rate is ~8 requests/second,
  comfortably under the published 20/second (1,200/minute).
- The headroom matters *because* the limits move without notice. A 429 mid-fan-out in
  front of a PM is the exact failure this is meant to avoid, and 0.8 s of extra speed
  is not worth spending that margin.

**Cost per run:** 869 input tokens per candidate. A 40-candidate run is ~35k input
tokens ≈ **$0.0015**. Output tokens are free. Jev is not a meaningful cost; Groq's
free-tier token ceiling is the binding constraint.

## How Score values are banded

A Score answer is **not** a label. `jev-1.13.0` returns:

```json
{"type": "score", "score": 1.74, "confidence": 0.62,
 "legend": {"0": "Low...", "1": "Medium...", "2": "High..."},
 "probabilities": {"0": 0.0, "1": 0.26, "2": 0.74}}
```

`score` is a **probability-weighted position** across the levels and lands between
them. The example above is a real measured answer for the Contoso transformation-fix
item: 1.74 means "mostly High, partly Medium".

**Banding rule (used everywhere a Score becomes a label):** round to the nearest
level, i.e. band *i* covers `[i - 0.5, i + 0.5)`.

| `score` | Band |
|---|---|
| `< 0.5` | Low |
| `0.5 – 1.49` | Medium |
| `>= 1.5` | High |

**The raw float is kept** as `severity_value` alongside the banded label. It is a
strictly better sort key: two items can both be "High" while one is 1.52 and the
other 2.0, and the action-item list should not present those as equal priority.

**What the "How it works" screen should say, in plain words:**

> Jev doesn't pick "High" — it spreads its belief across Low, Medium and High and
> returns the weighted position. This item scored **1.74 out of 2**, meaning mostly
> High with some Medium. We show the nearest band as the label, and sort by the exact
> number underneath, so a 1.9 outranks a 1.6 even though both read "High".

Confidence is reported separately and means something different: **1.74 with
confidence 0.62** says the model leans High but the distribution is not sharply
concentrated — which is exactly the kind of item worth a human glance.

## Noul banding

Noul answers carry **no confidence field at all** — only a probability. That is why
Section 6 bands the value itself rather than thresholding a confidence:

| `noul` | Meaning shown to the PM |
|---|---|
| `>= NOUL_YES` (0.65) | **Stated** |
| `NOUL_NO` – `NOUL_YES` (0.35–0.65) | **Inferred** — the model is genuinely unsure |
| `<= NOUL_NO` (0.35) | **Not specified** |

The middle band is "genuinely unsure whether it was stated", **not** "half stated".
Measured example: `owner_explicit = 0.73` for *"I will own the transformation fix"*
with `stated_owner: "Raj Menon"` → **Stated**, correctly.
