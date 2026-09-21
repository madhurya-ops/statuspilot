# Jev design notes

Written properly in **Phase 4**, per the checklist in `execution.md` Section 11.
This stub exists only to carry forward the open items that Phase 0 uncovered, so
they are not lost between phases.

## To be written in Phase 4

- Which docs pages were read, and which cookbook / pattern is closest to ours
  (candidates from the index: **speculative fan-out**, **confidence-gated
  routing**, **composite scoring**, **intent routing**).
- What changed in Section 6 of `execution.md` as a result, and why.
- **How every Score float is banded** — stated plainly enough that the
  "How it works" screen (Section 10, Screen 5) can repeat it to a PM honestly.

## Carried over from Phase 0

Read from the live `https://docs.typesafe.ai/api.md` while writing the Phase 0
smoke test. These are **open items booked for Gate 4**, not decisions:

### Score answers carry no label

A Score answer is:

```json
{
  "type": "score",
  "score": 1.05,
  "legend": { "0": "Calm", "1": "Frustrated", "2": "Very angry" },
  "probabilities": { "0": 0.0, "1": 0.95, "2": 0.05 },
  "confidence": 0.92
}
```

`score` is a **probability-weighted float that can land between levels** — 1.05
above is "mostly Frustrated, a little Very angry". There is no
`"Low" | "Medium" | "High"` string anywhere in the response, so Section 7's
`Decision.label` cannot be populated directly from a Score. Code must band it.

Consequences to propose at Gate 4:

1. `ClassifiedItem` keeps **`severity_value: float`** (the raw score) alongside
   the banded label. The float orders action items by real priority; a
   three-way band cannot. Do not discard it.
2. Section 6's RAG rule — Red if `client_sentiment` **= level 0** — is exact
   equality on a float and will essentially never fire. It needs a threshold
   instead (something like `score < 0.5`), proposed together with the
   Section 7 edit.

### Confidence is not correctness

`confidence` on Choice and Score is derived from the concentration of the
probability distribution. Noul answers carry **no** confidence field at all —
only `noul`, a 0..1 probability — which is exactly why Section 6 bands Noul
values rather than thresholding a confidence on them.

### Other API facts worth holding on to

- Endpoint is `POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer`.
- `state` may be a string **or** a structured object/array — our named-JSON state
  is a supported shape, not a workaround.
- `instructions` may also be a string, object, or array, so data a question refers
  to can be nested and addressed with backticked paths.
- Choice allows up to **255** options; Score takes an **ordered array of 2–10**
  level descriptions.
- Question ids are **not** sent to the model — each question must be fully
  self-describing in `instructions` + `criteria`.
- Errors: `401` bad key, `422` malformed question (body names the field),
  `429` rate limited, `529` overloaded. Back off on 429/529.
