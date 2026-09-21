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
| **Strict recall** | **70 %** | The planted item became **its own candidate**. This predicts how complete the RAID log and action-item **tables** are — each row needs its own candidate. |
| **Content coverage** | **86 %** | The planted item reached the output **at all**, either as its own candidate or merged into a neighbouring one. This predicts whether the status report **narrative** misses anything. |

The gap between them is granularity, not lost information: the model's main failure is
merging a problem with the task that fixes it, rather than dropping either. **Nine of
63 items (14 %) were genuinely absent.** Nothing was hallucinated in any run — every
candidate cites real transcript lines, and no owner appears who is not in the
transcript.

### Cost per report

Groq's free tier charges its tokens-per-minute limit on **requested** tokens
(`prompt + max_completion_tokens`), not consumed ones — measured, not assumed:
one extraction with a 2,520-token prompt and a 4,500 cap dropped
`x-ratelimit-remaining-tokens` from 7,927 to **980**, although it consumed 5,415.

| Stage | Requested |
|---|---:|
| Extract | ~7,020 |
| Generate | ~4,500 |
| **Full report** | **~11,500** |

Against an **8,000 tokens/minute** ceiling, **one live report does not fit in a single
minute**. The bucket refills at ~133 tokens/second, so generation waits ~26 s after
extraction. That is why the three bundled samples serve **precomputed** results,
labelled visibly in the UI as a cached sample run, while pasted or uploaded text
always goes live.

Jev is not a cost constraint: ~870 input tokens per candidate and roughly **$0.0015**
for a 40-candidate run, against published limits of 250 k tokens/second and 1,200
requests/minute.

**Status:** in development (Phase 3 complete). This README is expanded in Phase 10.

## Safety notes

- All sample transcripts are synthetic. No real client or personal data.
- API keys are server-side only, in `backend/.env` locally and Vercel
  Environment Variables in production. They are never committed and never
  reach the browser.
- Transcript content is never written to production logs.
