# StatusPilot — Progress Log

One entry per phase. Kept per the build agreement in `execution.md`.

---

## Phase 0 — Setup

**Status:** ✅ complete — Gate 0 approved 2026-09-21
**Date:** 2026-09-21

### Done

- `git init` in the project root (it was not previously a git repo); branch `main`.
- Created the full folder structure from Section 5 of `execution.md`.
- `.gitignore` covering `.env`, `node_modules`, `__pycache__`, `dist`, `.venv`,
  `.pytest_cache`, `.ruff_cache`, `.vercel`, `.DS_Store`. Verified with
  `git check-ignore` that `backend/.env` **is** ignored and that both
  `.env.example` files and `.claude/skills/typesafe-ai/SKILL.md` are **not**.
- Wrote `backend/.env.example` and `frontend/.env.example` verbatim from Section 5.
- Wrote `backend/.env` (mode 600, git-ignored) with empty key values for the user
  to fill in, so no key material passes through the assistant transcript.
- Committed the `typesafe-ai` skill, as Section 2A requires.
- Created the **private** GitHub repo `madhurya-ops/statuspilot` and pushed `main`.
- Read the live TypeSafe `api.md`; recorded findings in `docs/jev_design_notes.md`.
- Wrote the smoke-test script (in the session scratchpad, not the repo). It reads
  `backend/.env` and prints **status codes, latencies and model IDs only**.

### Smoke tests — both pass

| Test | Result |
|---|---|
| Groq `GET /openai/v1/models` | **200**, 482 ms, 13 models |
| Groq `POST /chat/completions` | **200**, ~0.5-1.3 s, valid JSON |
| TypeSafe `POST /v1/systemone` | **200**, 1445 ms, `model` echoed `jev-1.13.0`, `noul` 0.97, usage 295 in / 21 out |

A first attempt at the Groq call returned `403 error code: 1010`. That is a
Cloudflare edge block on the `Python-urllib/3.x` user agent, **not** an auth
failure — the identical request through `curl` returned 200. Recorded because the
same trap will appear in Phase 3 if any code path ends up using `urllib`; the
backend uses the `openai` SDK (httpx under the hood), which sends its own UA.

### Findings that affect the plan — raised at Gate 0, **approved and applied**

1. **No Llama 3.3 70B on this account.** Section 2's example model class is stale.
   The available instruct models are `openai/gpt-oss-120b`, `openai/gpt-oss-20b`,
   `openai/gpt-oss-safeguard-20b` and `qwen/qwen3.8-27b` (all 131 k context),
   plus `groq/compound{,-mini}`, Whisper, Prompt-Guard and `allam-2-7b`.
2. **Rate limits are token-bound, not request-bound.** Live headers report
   `x-ratelimit-limit-requests: 1000` but `x-ratelimit-limit-tokens: 8000` **per
   minute**, and both models report the same remaining count, i.e. one shared
   bucket. Section 2's "~2 Groq calls per report, comfortably inside the limit"
   reasons about requests; the binding constraint is **tokens per minute**.
3. **`MAX_INPUT_CHARS=60000` is unusable on this tier.** 60 k chars is roughly
   15 k tokens — nearly twice the 8 k per-minute token budget, so a max-size
   transcript cannot complete a single extraction call.
4. **The gpt-oss models are reasoning models**; completion tokens include hidden
   reasoning tokens. Groq's `reasoning_effort` parameter controls this, measured
   on an identical prompt: `low` 96 output tokens, `medium` 240, `high` 403 — a
   4x swing straight off the token budget.

### Decisions made with the user

| Decision | Outcome |
|---|---|
| Key handling | User fills `backend/.env` directly; keys never enter the transcript. |
| GitHub repo | Created private. |
| Groq model IDs | Read from live `GET /openai/v1/models`, not the client-rendered docs page. Two IDs proposed for approval, not chosen silently. |
| Python version | **Pin 3.13** everywhere. Vercel supports 3.12/3.13/3.14 and local is 3.13.5, so 3.13 satisfies both. Set via `pyproject.toml` `requires-python`, **not** `vercel.json`. |
| Vercel projects | Deferred from Phase 0 to Phase 1, dashboard Git integration, no CLI. |

### Plan changes made to `execution.md`

1. **Section 4** — backend header changed from "Python 3.12" to "Python 3.13",
   with a note explaining Vercel's supported versions and where the version is set.
2. **Section 11, Phase 0** — Vercel checkbox struck through and marked deferred.
3. **Section 11, Phase 1** — added an explicit "create the Vercel projects" step,
   and corrected the `vercel.json` line: the Python version is **not** configured
   there.
4. **Section 2A** — added four open items booked for Gate 4 (Score has no label;
   keep `severity_value: float`; the `client_sentiment` = level 0 rule needs a
   threshold; document the banding).

### Gate 0

- [x] Groq smoke test returns 200
- [x] Jev smoke test returns 200, `model` echoed as `jev-1.13.0`
- [x] `GROQ_MODEL=openai/gpt-oss-20b` / `GROQ_MODEL_ESCALATION=openai/gpt-oss-120b`
      written to `backend/.env` and `.env.example`
- [x] Repo structure, `.gitignore`, `.env.example` files
- [x] `typesafe-ai` skill committed
- [x] GitHub repo created
- [x] Vercel — deferred to Phase 1 by agreement

### Section 2 rewrite applied after Gate 0 approval

The user chose **speed over capability**: `gpt-oss-20b` primary, `gpt-oss-120b` as
escalation — the reverse of the assistant's proposal. Rationale: this is a showcase,
and 20b at ~1000 tok/s makes the demo feel instant, which matters more to a PM
audience than extraction subtlety.

The user also carried a finding to its conclusion that the assistant had not:
**both models share one token bucket, so swapping model on a 429 buys nothing.**
The fallback-on-429 design is therefore removed outright, and the second model is
reserved for quality escalation only.

| Change | Where |
|---|---|
| `GROQ_MODEL_FALLBACK` renamed `GROQ_MODEL_ESCALATION`; used **only** on repeated JSON/validation failure | §2, §5, §8, Phase 3 |
| 429 handling: back off 1s/2s/4s on the same model, "Busy — retrying" in the UI, **never** swap models | §2, Phase 3 |
| Dead "JSON mode + schema in prompt otherwise" branch deleted; `json_schema` strict everywhere | §2, Phase 3 |
| `MAX_INPUT_CHARS` 60000 → **12000** | §5 |
| `GROQ_REASONING_EFFORT_EXTRACT` / `_GENERATE`, both `low` | §5 |
| Sample transcripts capped at ~5000 chars | §9 |
| Character counter shows remaining budget, not a bare number | §10, Screen 1 |
| **Precomputed sample runs** as a demo safety net, with `CACHED_SAMPLES` toggle and a visible "cached" badge; pasted/uploaded text always live | Phase 9, §12 |
| "Run each sample 3 times" paced ≥60 s apart or run through the cache | Phase 9 |
| Log TypeSafe's rate-limit headers **before** settling `JEV_CONCURRENCY` | Phase 4 |

---

## Phase 1 — Backend skeleton

**Status:** ✅ complete — Gate 1 passed 2026-09-21
**Date:** 2026-09-21

### Built

| File | What it does |
|---|---|
| `backend/pyproject.toml` | Pinned deps, `requires-python = ">=3.13,<3.14"`, ruff + pytest config |
| `backend/app/config.py` | pydantic-settings covering **every** env var in Section 5 |
| `backend/app/main.py` | FastAPI app, CORS from `ALLOWED_ORIGINS`, router wiring |
| `backend/app/routers/health.py` | `GET /api/health` |
| `backend/app/security.py` | Access code, per-IP rate limiter, 413 size guard |
| `backend/vercel.json` | `maxDuration` 60 s on `app/main.py`, tests excluded from the bundle |

### Verification

- `ruff check .` → clean.
- `pytest` → **12 passed**.
- Started `uvicorn` and hit `/api/health` over **real HTTP**, not only TestClient:
  `{"status":"ok","version":"0.1.0","llm_primary":"groq","decision_engine":"jev","groq_model":"openai/gpt-oss-20b"}`
- CORS verified live: `access-control-allow-origin: http://localhost:5173` present
  for the configured origin, **absent** for an unknown origin.
- Server log grepped for `gsk_` / `sk-` / `Bearer` → 0 matches.

### Decisions worth recording

1. **`pyproject.toml` is the single source of truth for dependencies.** Section 5
   listed `requirements.txt` + `requirements-dev.txt`. Vercel accepts
   `pyproject.toml`, `requirements.txt` or a Pipfile but **documents no precedence
   when several are present**, and `pyproject.toml` is needed anyway for
   `requires-python`. Two lists that can drift, with an undefined winner, is a worse
   trade than one file. Section 5, Phase 1 and Section 13 updated.
2. **`app/main.py` is a supported Vercel FastAPI entrypoint**, so no
   `tool.vercel.entrypoint` override is needed and the Section 5 layout stands.
3. **A blank `DEMO_ACCESS_CODE` returns 503, not 200.** Running wide open would
   expose the Groq and TypeSafe keys to anyone with the URL, so it is treated as a
   misconfiguration rather than as "no auth required".
4. **A 401 does not consume rate-limit budget.** The code check runs before the
   limiter, so unauthenticated traffic cannot lock out a legitimate client. Covered
   by a test.
5. **`config.py` fails loudly on inverted thresholds.** `CONF_REVIEW > CONF_AUTO`
   would silently empty the "suggested" band and quietly change product behaviour, so
   it raises at startup instead.

### Notes for later phases

- Vercel's Python runtime sets the working directory to the **project root**, not the
  module's directory. `backend/app/samples/` must therefore be loaded via a path
  built from `__file__`, not a relative `open()`. Matters in **Phase 2**.
- Starlette 1.6 / FastAPI 0.141 wrap included routers in a lazily-resolved
  `_IncludedRouter`, so `app.routes` does not list child paths until resolution.
  Not a bug — but route-introspection assertions in later tests should go through
  `TestClient`, not `app.routes`.
- `HTTP_413_REQUEST_ENTITY_TOO_LARGE` is deprecated in this Starlette version;
  using `HTTP_413_CONTENT_TOO_LARGE`.

### Gate 1

- [x] `ruff check` passes
- [x] `pytest` passes (12 tests)
- [x] Health endpoint verified over real HTTP locally
- [x] **Live health URL works from the phone**
      → https://backend-zeta-orcin-78.vercel.app/api/health (200, 0.73 s cold)

**Post-deploy observations**

- The Vercel project is named `backend`, not `statuspilot-api`. Harmless, but the
  plan's project names are indicative only. This host is what `VITE_API_BASE_URL`
  must point at in Phase 6, and its origin must be added to `ALLOWED_ORIGINS`.
- `/api/parse` and `/api/samples` correctly 404 (not yet built).
- **`/docs` and `/openapi.json` are publicly reachable** — the FastAPI default. No
  secrets are exposed and every real endpoint stays behind the access code, but a
  public interactive API console on a demo URL invites poking. Offered to the user
  as a Phase 9 hardening item (`docs_url=None` in production).
- The user approved keeping `pyproject.toml` as the single dependency source.

---

## Phase 2 — Ingestion & samples

**Status:** ✅ complete — awaiting Gate 2 approval
**Date:** 2026-09-21

### Built

| File | What it does |
|---|---|
| `app/models.py` | `TranscriptLine`, `SampleSummary`, `SampleDetail`, `ParseResponse` |
| `app/ingest/lines.py` | Whitespace normalisation, line-boundary truncation, `Name:` speaker detection |
| `app/ingest/parse.py` | `.txt` (utf-8 → latin-1), `.docx` (incl. tables), `.vtt` / `.srt` |
| `app/ingest/samples.py` | `__file__`-relative sample loader |
| `app/routers/samples.py` | `GET /api/samples`, `GET /api/samples/{id}` |
| `app/routers/parse.py` | `POST /api/parse`, `GET /api/parse/formats` |
| `app/samples/*.txt` + `index.json` | The three synthetic transcripts |

### Sample sizes (cap ~5000 chars)

| Sample | Chars | Lines | Lines with a speaker |
|---|---:|---:|---:|
| `northwind-sprint-review` | **4937** | 51 | 47 |
| `contoso-escalation` | **4886** | 53 | 49 |
| `rough-standup-notes` | **2381** | 43 | **0** |

`rough-standup-notes` having **no** detected speakers is deliberate, not a parser
failure: they are freeform bullets with no `Name:` prefixes. That is precisely what
should drive low-confidence `owner_explicit` judgments and populate the review queue
in Phase 4.

### Verification

- `ruff check` clean; **60 tests pass**.
- Verified over real HTTP, not only TestClient: 401 without a code, all three samples
  listed and fetched, `.srt` upload merged into `Priya Nair: I will take it, by
  Thursday.`, `.pdf` upload rejected 400.
- Server log inspected: it records `ext=srt bytes=118 chars=40 truncated=False` and no
  transcript text. The only hits for sample words were uvicorn's access log printing
  the sample **id** in the URL path, which is a public identifier.

### Bug found and fixed during testing

`split_speaker` matched **"This sentence: has a colon..."** as speaker `"This
sentence"`. A false speaker becomes a false **owner** downstream, which Hard Rule 7
forbids outright. Fixed by requiring every word of the speaker to be capitalised, on
top of the existing stop-word list. Covered by a parametrised regression test that
includes `"One thing: we need sign-off"`.

### Design notes

- **Truncation lands on a line boundary.** A mid-sentence cut would be quoted back
  verbatim as `evidence` by the extraction step, producing a citation to half a
  sentence.
- **Consecutive same-speaker caption cues are merged.** Caption formats split one
  spoken sentence across cues; without merging, a single commitment arrives as three
  fragments and neither the LLM nor Jev sees a whole item.
- **The local `DEMO_ACCESS_CODE` was changed by the user** from the placeholder. Test
  suite uses its own value via `conftest.py`, so the two never interact.

### Gate 2

- [x] All samples load via `/api/samples/{id}`
- [x] Parser tests pass
- [x] `ruff check` and `pytest` pass (60)
- [x] Verified over real HTTP locally

---

## Phase 3 — Groq layer & extraction

**Status:** ✅ complete — awaiting Gate 3 approval
**Date:** 2026-09-21

### Built

| File | What it does |
|---|---|
| `app/llm/base.py` | `LLMProvider` protocol, `LLMError` / `RateLimited` / `JSONInvalid` |
| `app/llm/groq_client.py` | Groq via the `openai` SDK, strict `json_schema`, per-stage `reasoning_effort`, completion budget, error-code surfacing |
| `app/llm/mock.py` | Deterministic offline provider derived from the transcript |
| `app/llm/router.py` | The two separate failure paths |
| `app/llm/prompts.py` | Extraction prompt with untrusted-input framing |
| `app/pipeline/extract.py` | Every Section 8 post-validation rule |
| `app/routers/extract.py` | `POST /api/extract` |
| `docs/sample_ground_truth.md` | 63 planted items, **committed before the first live run** |
| `docs/extraction_recall.md` | Scored results and token costs |

### Verification

- `ruff` clean; **93 tests pass**; no test touches the network.
- Three live Groq runs, paced 95 s apart. No 429, no escalation, single attempt each.

### Three bugs found and fixed

1. **The extraction schema included `lines`.** Section 8 says "validated against
   `ExtractResponse` **minus `lines`**" and the first implementation ignored that.
   Strict mode therefore required the model to re-emit the entire transcript as
   output, exhausting `max_completion_tokens` and returning
   400 `json_validate_failed` on two of three samples. Split out `ExtractionPayload`
   / `CandidateDraft`; the server fills `lines` itself. Regression test added.
2. **`max_completion_tokens` is billed against TPM as *requested* tokens.** The 429
   body is explicit: `Limit 8000, Used 5645, Requested 5274`. Reserving 6,000 for a
   2,500-token prompt needs 8,500 against an 8,000 ceiling — one request exceeding
   the whole budget. Reduced to 3,200.
3. **The router could never escalate.** A guard skipped the escalation model whenever
   `LLM_PRIMARY=mock`, which is the configuration every test runs under, so the
   escalation path was both dead in tests and untestable. Guard removed.

Also removed pydantic docstrings from the request schema: a class docstring is
emitted as a JSON-schema `description` and billed as input tokens on every call.

### Honest note on the prompt iteration

The first run scored 68 % but **failed to extract the Contoso L46 blame remark**,
which Section 9 requires to classify `internal_only`. The revised prompt fixes that —
but overall recall moved **68 % → 65 %**, because `rough-standup-notes` regressed from
74 % to 59 % while `northwind` improved from 53 % to 65 %. Recorded as a trade, not a
win. Details in `docs/extraction_recall.md`.

### Gate 3

- [x] Extraction works live on all three samples
- [x] 93 tests pass, `ruff` clean
- [x] Ground truth committed before the live run
- [x] Recall and per-sample token cost reported

---

## Phase 4 — Jev judgments, routing & RAG

**Status:** ✅ complete — awaiting Gate 4 approval
**Date:** 2026-09-21

### Built

`decide/` — `base.py` (engine protocol), `questions.py` (all specs as data),
`state.py` (named-JSON state per candidate), `jev.py` (async httpx, semaphore,
retries, answer parsing), `routing.py` (banding, thresholds, audience fail-safe),
`llm_fallback.py` (Groq with the published confidence formula), `mock.py`.
`pipeline/rag.py` (composite scoring), `pipeline/classify.py` (whole-run fallback),
`routers/classify.py`.

### Live results

| Sample | Items | Judgments | Jev latency | RAG | Routing |
|---|---:|---:|---:|---|---|
| northwind | 14 | 75 | 3.5 s | Amber (0.89) | 7 auto · 7 suggested · 0 review |
| contoso | 24 | 125 | 4.0 s | **Red (0.92)** | 4 auto · 10 suggested · 10 review |
| rough-standup | 17 | 90 | 5.5 s | Amber (0.54) | 4 suggested · **13 review** |

### Four bugs found and fixed

1. **The client status report would have been empty.** First live run produced 0, 1
   and 0 client-safe items. The `audience` question's instructions asked about
   report-*worthiness* while its criteria described *harm*; on a two-option Choice
   (`confidence = 2·p_max − 1`) that ambiguity collapses confidence, and the fail-safe
   then forced almost everything internal. Rewording per Section 2A's "tune wording,
   not thresholds" rule took median `p_max` from 0.66 to 0.96.
2. **Truncation silently lost candidates.** Under strict `json_schema` a response that
   hits the completion cap still *parses* — the constrained decoder closes the JSON —
   so there is no error, just fewer items. `rough-standup-notes` returned 11 candidates
   truncated and 22 once the cap was raised to 4,500.
3. **`finish_reason` was dropped by the router** when it rebuilt `LLMUsage`, which is
   why bug 2 was invisible. Now propagated, logged and warned on.
4. **`band_score` used banker's rounding.** Python's `round(0.5) == 0`, so 0.5 banded
   Low while 1.5 banded High. Replaced with `math.floor(x + 0.5)`.

Also: the mock decision engine and mock extractor were rewritten for bullet-note
input. Their signal lists were meeting-shaped, so `rough-standup-notes` produced only
7 candidates and 1 review item offline — the review queue was effectively untested.

### Threshold change

`NOUL_YES` 0.65 → **0.75**. `priya: reminder timesheets due friday` scored 0.67 and
banded "Stated", though Priya is reminding others rather than owning the task. Across
all three samples the change moves exactly two items and improves both; every
genuinely-stated owner scores ≥ 0.80.

### Gate 4

- [x] Live classification works on all three samples
- [x] Contoso → Red; internal aside → `internal_only` (0.79)
- [x] `rough-standup-notes` yields 13 review items (≥ 3)
- [x] 159 tests pass, `ruff` clean
- [x] `docs/jev_design_notes.md` written

---

## Phase 5 — Document generation, leak post-check, empty state, sample cache

**Status:** ✅ complete — awaiting Gate 5 approval
**Date:** 2026-09-21

### Built

| File | What it does |
|---|---|
| `app/pipeline/generate.py` | Tables built in code; leak detection, regenerate, strip; empty/skeleton report handling |
| `app/pipeline/cache.py` | Fingerprint on normalised text, schema-validated load, save |
| `app/routers/generate.py` | `POST /api/generate`, `GET /api/cached/{id}`, `POST /api/cached/lookup` |
| `app/routers/budget.py` | `GET /api/budget` — remaining tokens and the real wait, for an honest countdown |
| `scripts/build_sample_cache.py` | Deliberate, paced cache build. Refuses to run against mock engines. |

### The dynamic completion cap

Groq bills its TPM limit on `prompt + max_completion_tokens`, so a fixed cap pays for
tokens it never uses. The cap is now scaled from an estimated prompt size
(`chars / 3.1`, conservative against the worst measured density of 3.196).

**Ratio 1.4 was wrong and the first build proved it.** `rough-standup-notes` needs
~1.85x its prompt in completion tokens — bullet notes pack far more items per prompt
token than meeting dialogue — so it truncated, retried at the ceiling, and cost
~11.6k requested tokens instead of ~6.2k. **A truncation retry is far more expensive
than over-reserving**, so the extract ratio is 2.0.

| Stage | Ratio | Floor | Ceiling |
|---|---:|---:|---:|
| extract | 2.0 | 2,000 | 4,500 |
| generate | 1.6 | 2,000 | 3,500 |

### Four bugs found and fixed

1. **Truncation has two faces.** When the constrained decoder closes the JSON, Groq
   returns 200 with `finish_reason: "length"`. When it cannot, it returns **400
   `json_validate_failed`** whose body reads *"max completion tokens reached before
   generating a valid document"*. Only the first was handled, so the second surfaced
   as a dead error with no retry.
2. **The leak detector produced false positives, and its stripper deleted real
   content.** It emptied an entire "Next steps" section of the Northwind report. The
   cause was matching on shared project vocabulary: an internal note about
   *"anonymised data available by end of March"* overlapped a perfectly proper client
   sentence about anonymised test data. Fixed by **excluding any term that also
   appears in a client-safe item** — a word the report is supposed to use cannot be
   evidence of a leak — plus a 4-term minimum and a 75 % overlap requirement.
3. **A near-empty report is worse than an empty one.** `rough-standup-notes` cleared
   one client-safe item and produced five bare headings, which reads as a broken app.
   The empty-state explanation now triggers on *no substantive body*, not only on
   zero client-safe items, and names how many items were withheld.
4. **Timeouts were not retried.** The OpenAI SDK raises `APITimeoutError`, which the
   client did not catch, so it escaped the router unretried and killed a cache build.
   Added a `Transient` class covering timeouts, connection errors and 5xx.

### Gate 5

- [x] Tables built in code from approved items, sorted on the raw severity float
- [x] Leak post-check: regenerate once, then strip, with `leak_stripped` reported
- [x] Explicit empty state for the status report
- [x] Precomputed sample cache with `cached: true` and a `CACHED_SAMPLES` switch
- [x] Pasted text always goes live (cache keyed on the sample text fingerprint)
- [x] 194 tests pass, `ruff` clean

### Gate 5 — BLOCKED on the Groq daily token cap (2026-09-21)

Everything in Phase 5 is built, tested (201 passing) and pushed. Two items could not
be completed:

- the precomputed sample cache could not be built;
- the generated Contoso and Northwind prose could not be shown.

Both need Groq calls, and **the account is at 199,232 of a 200,000 tokens-per-day
cap.**

**The cap is invisible in headers.** At the moment of exhaustion,
`x-ratelimit-remaining-requests` read 998/1000 and `x-ratelimit-remaining-tokens`
read 8000/8000. Only the 429 body names it:

```
Rate limit reached ... on tokens per day (TPD):
Limit 200000, Used 199232, Requested 2877. Please try again in 15m11.088s.
```

| | |
|---|---|
| Refill | 2.31 tokens/second |
| One full report (~11,500 requested) | **83 minutes** |
| Three-sample cache build (~35,000) | **~4 hours** |
| Full live reports per day | **~17** |

Consumed across Phase 3–5 development: extraction prompt iterations, four
classification runs, and three cache-build attempts — two of which stalled on an
unbounded `retry-after` and were killed, wasting their spend. Cumulative daily usage
was not being tracked, only per-minute headroom.

**Agreed plan:** pause Groq work; rebuild the cache first thing when the window
resets, then show the prose and take Gate 5. Build Phase 6 against the mock providers
meanwhile, which costs nothing.

**Fixed as a result:**
- `RateLimited.scope` distinguishes `"minute"` from `"day"`, and the API returns a
  different message for each — a daily exhaustion says so and points at the cached
  samples rather than offering a pointless retry.
- The router refuses to sleep longer than 30 s inside a request. Groq asked for 612 s
  and then 931 s; honouring that literally stalled two builds, and on Vercel
  (`maxDuration` 60 s) it would kill the function mid-sleep.

---

## Phase 6 — Frontend foundation

**Status:** in progress — built against the mock providers while Groq's daily budget is
exhausted (agreed with the user; costs zero tokens)
**Date:** 2026-09-21

### Built

| File | What it does |
|---|---|
| `src/types.ts` | Mirrors `backend/app/models.py`, including `severity_value` and the null-confidence convention for Noul |
| `src/api/client.ts` | Typed calls, `X-Access-Code`, 60 s timeout, error normalisation |
| `src/state/session.ts` | `useReducer` for the whole flow, plus `approvedItems()` |
| `src/state/run.ts` | Cache-first run orchestration and the budget countdown |
| `src/pages/AccessGate.tsx` | One field, one button |
| `src/pages/InputPage.tsx` | Sample chips, paste box, upload, budget-aware counter |
| `src/pages/ProcessingPage.tsx` | Stepper with per-step timings and a labelled wait |
| `src/components/Measure.tsx` | The confidence measure, badge and distribution |
| `src/components/Chrome.tsx` | Screen shell, buttons, banner, toast, cached tag |

### Design direction

- **Two typefaces doing different jobs.** IBM Plex Sans for the application; **Newsreader
  for generated documents**, so the status report and minutes read as documents a PM
  would send rather than as app screens. That distinction *is* the product.
- **The signature device is a measure** — a thin gauge showing where belief actually
  sits — reused for confidence, kind distribution and RAG. A bare "62 % sure" says less
  than seeing the probability mass, and the mass is the pitch.
- Palette: `ink #232433`, `wash #F5F5F8`, `indigo #4F46E5` (the brief's accent), plus
  true RAG colours. Deliberately not the cream/terracotta or near-black/acid defaults.
- Copy does work: the character counter explains the limit
  ("about 1,300 tokens") rather than enforcing it silently, and a budget wait names its
  reason with a countdown instead of showing a spinner.

### Deviations from the plan

1. **React 19, not 18.** `npm create vite` scaffolds 19 now; 18 would be a deliberate
   downgrade and nothing in Section 10 needs a React 18 API.
2. **Tailwind v4**, which configures via `@import "tailwindcss"` and an `@theme` block
   in CSS. There is no `tailwind.config.js`; Section 5's layout is updated.

### Blocked

`npm install` is crawling — the registry is serving at roughly **23 KB/s** (352 KB of a
7 MB tarball in 15 s), so `node_modules` is still empty and the project cannot be
typechecked, built, or screenshotted yet. This is a network condition, not a broken
install.

---

# TOKEN BUDGET — Day 2 (build day *and* demo day, one 200,000 budget, no reset between)

**Agreed with the user 2026-09-21. Binding. Report consumption against this at every
gate.** Groq's tokens-per-day cap does not appear in any response header, so the only
reliable reading is the `Used` figure in a 429 body:

```
... on tokens per day (TPD): Limit 200000, Used 199232, Requested 2877.
```

| Line | Allocation | Rule |
|---|---:|---|
| **1. Cache rebuild** | **~35,000** | **First spend of the day, before anything else.** |
| **2. Live verification, Phases 7–9** | **cap 40,000** | Mocks prove anything mocks can prove. Real tokens only where the live path genuinely differs from the mock path. |
| **3. Demo reserve** | **60,000 — UNTOUCHABLE** | **Do not spend below this line without asking first.** |
| 4. Contingency | ~65,000 | A failed cache build, or a regression needing a re-run. |

**Stop-and-ask trigger:** if a planned spend would take the remaining balance below
**60,000**, stop and ask before spending it.

**What a spend costs, measured:**

| Action | Requested tokens |
|---|---:|
| One extraction (~5,000-char transcript) | ~6,000–7,000 |
| One generation (12–24 items) | ~3,100–4,100 |
| **One full live report** | **~10,000–11,500** |
| Full cache rebuild (3 samples) | ~35,000 |
| Live demo paste (~1,070-char snippet) | **~4,000** |

At ~10,000 per live report, the 60,000 reserve covers **six** live runs on demo day —
enough for the paste moment plus five retries. The three bundled samples cost **zero**
because they are served from the committed cache.

**Cheapest thing that proves the most:** the bundled samples. They exercise the whole
pipeline end to end at no token cost once cached, which is why the cache is line 1.

---

## Phases 7 & 8 — Review queue, results, exports

**Status:** built and verified against mocks. **Zero Groq tokens spent.**
**Date:** 2026-09-21

### Phase 7

`Markdown.tsx` (small renderer for the subset the documents use; no raw HTML, so model
output cannot inject markup) · `Item.tsx` (RagPill, SourceQuote, severity chip showing
the raw float beside the band, stated/inferred tags) · `ReviewPage` (Accept / Change /
Drop, probability distribution per item, progress, RAG confirmation below 50 %,
Accept all) · `ResultsPage` (four tabs, internal-only toggle, copy, leak warning) ·
`HowItWorks`.

**Bug found by clicking, not reading:** "Accept all" left the RAG unconfirmed, so
**Build reports stayed disabled at 9/9** with nothing on screen explaining why. Accept
all now also accepts the suggested status, and a disabled Build button states what it
is waiting for.

### Phase 8

`docx_export.py` · `xlsx_export.py` · `pdf_export.py` · `POST /api/export/{fmt}` ·
`ExportSheet.tsx`. All three verified over the wire from the browser:

| Format | Bytes | Filename |
|---|---:|---|
| docx | 37,011 | `StatusReport_Contoso-Insurance_2026-09-21.docx` |
| xlsx | 8,109 | `StatusReport_Contoso-Insurance_2026-09-21.xlsx` |
| pdf | 1,337 | `StatusReport_Contoso-Insurance_2026-09-21.pdf` |

**Two things worth noting:**

1. **fpdf2 raised "Not enough horizontal space to render a single character."**
   `multi_cell(0, …)` measures width from the *current* x, so a cursor left mid-page by
   the RAG colour block eventually left no usable width. Every full-width line now
   resets to the left margin. Covered by a test using long text and twelve items.
2. **The export filename is built from user input and lands in a response header.**
   It is reduced to `[A-Za-z0-9-]`, so `../../etc/passwd` becomes `etc-passwd`.
   Parametrised test included.

The XLSX carries the **raw severity float** in its own column, so a PM can sort by real
priority rather than by a band that ties 1.52 with 2.0.

### Layout fixes (from the user's review)

- Desktop rendered hard against the left edge — the shell now centres, with a wider
  column for review and results.
- The sticky action bar floated mid-page with a seam down its side: `sticky bottom-0`
  only sticks once a page scrolls, and the bar sat inside the centred column so its
  background stopped at the column edge. Now full-bleed with constrained contents,
  inside a `min-h-dvh` flex shell. Verified by screenshot at **375, 768 and 1440**.

### Tests

**220 backend tests pass**, `ruff` clean, `tsc` clean, `vite build` clean.

---

## Gate 6 — PASSED (2026-09-22)

Live: **https://statuspilot-topaz.vercel.app** → **https://backend-zeta-orcin-78.vercel.app**.
Full flow confirmed on the user's phone. **Zero Groq tokens spent on this work.**

> Vercel assigned the hostname `statuspilot-topaz`, not `statuspilot-web` as the
> project is named. Docs and the backend CORS test now use the real origin.

### Three defects from the phone walkthrough

**1. The access gate stored the code before validating it.**
`setAccessCode()` ran first, then the validation call. When that call failed for *any*
reason — CORS, network, server down — the UI said "not recognised" while the rejected
code sat in `sessionStorage`, so a refresh logged straight in past a gate that had just
refused. `validateAccessCode()` now checks with an explicit header and stores nothing;
the caller persists only on success, and a failure clears any prior value.
**Five tests** cover it, including the transport-failure case that caused the bug and
`sessionStorage` being unavailable.

**2. The action bars broke at 375 px.** Labels wrapped to two lines, buttons touched
the screen edge, and three button weights competed in one row.
- `Button` is now `shrink-0 whitespace-nowrap`; a wrapped label turns a 44 px target
  into a ragged block.
- A new `grow` variant fills the remaining space. `full` is `w-full`, which had pushed
  "Export" clean off the right edge.
- **Review:** one primary ("Build reports"); "Accept all remaining" moved beside the
  progress counter it acts on.
- **Results:** "Copy report" + "Export"; **"Start over" moved to the header** — it is
  not an export action and did not belong beside two that are.
- Measured at 375 px: buttons span 16→274 and 282→359 of 375. 16 px gutters, no
  overflow, no wrapping.

**3. The raw severity float leaked into the UI.** Review cards read "High 1.98", which
looks like a debug value. The band alone is shown; the float remains in
`ClassifiedItem`, drives ordering in code, and has its own column in the XLSX — which
is what it was for.

### New dev dependency

**`vitest`, `jsdom`, `@testing-library/react`, `@testing-library/dom`** — added to write
the access-gate tests the user asked for. Dev-only, not in the shipped bundle, and not
in Section 4's approved list. Easy to remove if unwanted.

### Token budget — Day 2

| | Tokens |
|---|---:|
| Allocation | 200,000 |
| Spent so far today | **0** |
| Remaining | **200,000** |
| Reserve (untouchable) | 60,000 |

Yesterday's ~7,100 overspend came out of yesterday's window and does not carry over.
