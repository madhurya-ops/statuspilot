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

## Measured performance

Numbers from live runs, not estimates. Full method in
[`docs/extraction_recall.md`](./docs/extraction_recall.md); the scoring key in
[`docs/sample_ground_truth.md`](./docs/sample_ground_truth.md) was committed
**before** the first run so it could not be tuned to flatter the result.

### Extraction accuracy

Scored against 63 items deliberately planted across three synthetic transcripts.
Two numbers, because one would mislead:

| Metric | Score | What it means |
|---|---:|---|
| **Strict recall** | **63 %** | The planted item became **its own candidate**. This predicts how complete the RAID log and action-item **tables** are — each row needs its own candidate. |
| **Content coverage** | **84 %** | The planted item reached the output **at all**, either as its own candidate or merged into a neighbouring one. This predicts whether the status report **narrative** misses anything. |

The gap between them is granularity, not lost information: the model's main failure
is merging a problem with the task that fixes it, rather than dropping either.
**Ten of 63 items (16 %) were genuinely absent.** Nothing was hallucinated in any
run — every candidate cited real transcript lines, and no owner appeared who is not
in the transcript.

### Cost per report

| | Tokens |
|---|---:|
| Extraction, ~5,000-character transcript | ~4,300 (2,500 in / 2,300 out) |
| Full report (extract + generate) | **7–9 k** |

On Groq's free tier the binding limit is **8,000 tokens per minute**, shared across
models — so the app sustains roughly **one live report per minute**. That is why the
three bundled samples serve **precomputed** results, labelled visibly in the UI as a
cached sample run, while pasted or uploaded text always goes live.

**Status:** in development (Phase 3 complete). This README is expanded in Phase 10.

## Safety notes

- All sample transcripts are synthetic. No real client or personal data.
- API keys are server-side only, in `backend/.env` locally and Vercel
  Environment Variables in production. They are never committed and never
  reach the browser.
- Transcript content is never written to production logs.
