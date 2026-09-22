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
| **Strict recall** | **67 %** | The planted item became **its own candidate**. This predicts how complete the RAID log and action-item **tables** are — each row needs its own candidate. |
| **Content coverage** | **86 %** | The planted item reached the output **at all**, either as its own candidate or merged into a neighbouring one. This predicts whether the status report **narrative** misses anything. |

The gap between them is granularity, not lost information: the model's main failure is
merging a problem with the task that fixes it, rather than dropping either. **Nine of
63 items (14 %) were genuinely absent.**

### Extraction is non-deterministic, and the design assumes it

Five runs over byte-identical input at `temperature=0` produced **12, 16, 20, 11 and 9**
candidates — the best draw finds **2.2×** what the worst does. The cause is not
temperature: `openai/gpt-oss-20b` is a reasoning model whose hidden trace varies between
calls, and GPU serving is not bit-deterministic in general.

The recall figures above are therefore **one draw from a distribution**, measured on the
cache the demo actually ships, not a property of the system. They are quoted with the
spread rather than without it.

This is also the clearest argument for the review queue. **A non-deterministic
extractor is exactly why low-confidence items go to a human instead of into a client
report.** The claim is not that the model is reliable — it is that the model's
uncertainty is measured and acted on.

What does **not** vary: no run has produced an item citing a line that does not exist,
or an owner absent from the transcript. That validation is deterministic code, and it
holds regardless of the draw.

### Cost per report

Measured from the `usage` figures Groq returns on each call:

| Stage | Consumed |
|---|---:|
| Extract (~5,000-character transcript) | ~5,000 |
| Generate | ~3,000 |
| **Full report** | **~8,000** |

Groq's free tier has **two** token limits, and the one that bites is invisible:

| Limit | Value | In a response header? |
|---|---|---|
| Tokens per minute | 8,000 | yes |
| **Tokens per day** | **200,000** | **no — only in the 429 body** |

A full report uses close to a whole minute's allowance, so extraction and generation
back to back meet a short wait, which the UI labels with its reason and a countdown
rather than showing a bare spinner. The daily cap allows roughly **25 full live
reports**; nothing in the `x-ratelimit-*` headers hints at it, and they read
completely healthy at 99.6 % of the daily budget consumed. StatusPilot tells the two
apart, because "wait 20 seconds" and "wait until tomorrow" are not the same message.

Both are why the three bundled samples serve **precomputed** results, labelled visibly
in the UI as a cached sample run, while pasted or uploaded text always goes live.

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
