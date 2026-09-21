# StatusPilot — Progress Log

One entry per phase. Kept per the build agreement in `execution.md`.

---

## Phase 0 — Setup

**Status:** complete except the API smoke tests (blocked on keys)
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

### Blocked

- **API smoke tests.** `backend/.env` still has empty `GROQ_API_KEY` and
  `TYPESAFE_API_KEY`. Nothing else in Phase 0 depends on them.
- Groq model IDs follow directly from the first smoke test.

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

- [ ] Groq smoke test returns 200 — *blocked on key*
- [ ] Jev smoke test returns 200, `model` echoed — *blocked on key*
- [x] Repo structure, `.gitignore`, `.env.example` files
- [x] `typesafe-ai` skill committed
- [x] GitHub repo created
- [x] Vercel — deferred to Phase 1 by agreement
