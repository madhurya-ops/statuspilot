# StatusPilot

Meeting notes in. Client-ready status out.

StatusPilot turns a raw meeting transcript into four project documents in under a
minute: **Minutes of Meeting**, **action items**, a **RAID log**, and a
**weekly RAG status report**.

It is a hybrid pipeline. A Groq-hosted LLM extracts candidate items and writes the
narrative prose. **Jev**, TypeSafe's System One model, makes typed judgments with
calibrated probabilities on every candidate — is this an action item or just
discussion, which RAID category, how severe, is it safe to show the client. Code
then routes on those probabilities: confident items are accepted automatically,
uncertain ones go to a *"Needs your review"* queue.

The point of the design is that the AI says **"I'm not sure"** instead of guessing.

> Full build plan and phase gates: [`execution.md`](./execution.md).
> Progress log: [`docs/PROGRESS.md`](./docs/PROGRESS.md).

**Status:** in development (Phase 0). This README is expanded in Phase 10.

## Safety notes

- All sample transcripts are synthetic. No real client or personal data.
- API keys are server-side only, in `backend/.env` locally and Vercel
  Environment Variables in production. They are never committed and never
  reach the browser.
- Transcript content is never written to production logs.
