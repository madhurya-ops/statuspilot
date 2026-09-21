# StatusPilot — Progress Log

One entry per phase. Kept per the build agreement in `execution.md`.

---

## Phase 0 — Setup

**Status:** in progress
**Started:** 2026-09-21

### Done
- `git init` in project root (repo was not previously a git repo).
- Created the full folder structure from Section 5 of `execution.md`.
- `.gitignore` covering `.env`, `node_modules`, `__pycache__`, `dist`, `.venv`,
  `.pytest_cache`, `.ruff_cache`, `.vercel`, `.DS_Store`. Verified that
  `backend/.env` is ignored and that both `.env.example` files and
  `.claude/skills/typesafe-ai/SKILL.md` are **not** ignored.
- Wrote `backend/.env.example` and `frontend/.env.example` verbatim from Section 5.

### Pending (blocked on user input / accounts)
- `backend/.env` with the real Groq + TypeSafe keys.
- Groq model IDs for `GROQ_MODEL` / `GROQ_MODEL_FALLBACK` (will read the live
  `GET /openai/v1/models` list rather than the docs page, so the IDs are current).
- Both API smoke tests.
- GitHub repo + Vercel projects.

### Notes / flags raised
- Local Python is **3.13.5**, the plan says 3.12. Not a problem locally; needs a
  decision for the Vercel Python runtime in Phase 1.
- `vercel` CLI is not installed. Vercel setup can be done via the dashboard
  (Git integration) instead; no CLI dependency is required by the plan.

### Gate 0
- [ ] Not yet reached.
