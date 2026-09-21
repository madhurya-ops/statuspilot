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
