# StatusPilot — Progress Log

One entry per phase. Kept per the build agreement in `execution.md`.

---

## Phase 0 — Setup

**Status:** complete — awaiting Gate 0 approval
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

### Findings that affect the plan — raised at Gate 0, not yet applied

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
- [ ] `GROQ_MODEL` / `GROQ_MODEL_FALLBACK` written to `backend/.env` — *awaiting
      the user's confirmation of the two proposed IDs*
- [x] Repo structure, `.gitignore`, `.env.example` files
- [x] `typesafe-ai` skill committed
- [x] GitHub repo created
- [x] Vercel — deferred to Phase 1 by agreement
