# StatusPilot — verified fact sheet

Every figure below was read from the **committed demo cache** (`7b215b1`) or measured
directly. Nothing here is estimated. Last verified **22 Sept 2026**.

Use this to update your own playbook. If a claim is not on this list, I have not
verified it.

---

## THE NUMBERS

- **Strict recall: 67%** — the planted item became its own candidate (42 of 63).
- **Content coverage: 86%** — the item reached the output at all, captured or merged
  (54 of 63).
- **Genuinely absent: 9 of 63 (14%).**
- Per sample — northwind 59%/76%, contoso 79%/89%, rough-standup 63%/89%.
- Scored against `docs/sample_ground_truth.md`, which was written and committed
  **before any live run**, so it could not be tuned to flatter the result.
- **Superseded figures: 70%/86% and 65%/84%.** Do not quote these.

- **Cost per report: ~8,000 tokens consumed** (extract ~5,000 + generate ~3,000).
- Groq free tier: **8,000 tokens/minute** and **200,000 tokens/day**. The daily cap
  appears in **no response header** — only in a 429 body.
- The daily budget sustains roughly **25 full live reports**.
- **The three bundled samples cost zero** — they are served from the committed cache.
- Jev cost: ~870 input tokens per candidate, ~**$0.003** for a full three-sample run.
  Output tokens are free. Jev is not the constraint; Groq's daily cap is.

- **Jev latency: 2.4–5.5 seconds** for 55–125 judgments (5 questions per candidate,
  run in parallel, concurrency 10).
- Jev published limits: 250,000 tokens/second, 1,200 requests/minute.

---

## EXTRACTION IS NON-DETERMINISTIC — SAY THIS OUT LOUD

- Five runs, **byte-identical input**, `temperature=0`: **12, 16, 20, 11, 9** candidates.
- min 9 · max 20 · mean 13.6 · stdev 4.4. **The best draw finds 2.2× the worst.**
- Temperature is **already 0**. No `top_p` override, no `seed`.
- Causes: (a) `openai/gpt-oss-20b` is a reasoning model whose hidden trace varies
  between calls; (b) GPU serving is not bit-deterministic at temperature 0 in general,
  because batching changes floating-point reduction order.
- **Lowering temperature is not available as a fix — it is already at the floor.**
  Groq's API accepts a `seed` parameter; whether it tightens the spread is **untested**.
  Do not claim it would.
- **This is the strongest argument for the review queue.** A non-deterministic
  extractor is exactly why low-confidence items go to a human rather than into a client
  report. The claim is not "the model is reliable" — it is "the model's uncertainty is
  measured and acted on".
- **What does not vary:** no run has ever produced an item citing a line that does not
  exist, or an owner absent from the transcript. That validation is deterministic code.

---

## DEMO BEATS — CURRENT STATUS

**1. Contoso comes out Red — WORKS.**
RAG Red at 0.86 confidence. Reason line: *"The go-live date of 30 April is no longer
achievable, and the client is dissatisfied."* 22 items, 13 client-safe, 9 internal,
7 need review.

**2. The internal remark is held back — WORKS, and stronger than written.**
L46 (*"Honestly their team never reviews anything on time…"*) is extracted with
verbatim evidence and classified `internal_only` at **p(client_safe) = 0.00**.
That is **maximal confidence, not a marginal call** — worth saying out loud. Verified
absent from the client status report; the phrases "never review", "mapping document"
and "signed off in January" appear nowhere in it.

**3. The review queue on rough notes — WORKS.**
17 items, **12 routed to review**. RAG confidence 0.74.

**4. rough-standup client report — CHANGED. Reword.**
It is **1 of 17 cleared for the client**, not zero. The report reads: *"Progress: Dan
will tidy up the nav refactor. Next steps: No further client-directed actions are
required at this time. Risks and issues: None identified for the client."*
Honest and not broken, but it is no longer the blanket empty-state. The empty-state
code path still exists and is tested; this sample no longer triggers it.

**5. The "Inferred" owner tag — WORKS, but point at a different item.**
The timesheets item now scores 0.78 and bands **Stated**, not Inferred.
**Use instead: Northwind, "Jonas to chase legal for approved wording this week, by the
twentieth"** — owner `0.59 → Inferred`, due `0.90 → Stated`, **both bands on one card**.
That is a better demonstration than the original.
Across all three samples: 12 stated, 3 inferred, 35 not specified.

**6. Exports open on a phone — NOT YET VERIFIED ON A PHONE.**
All three formats generate and download over the wire (docx 37,011 bytes, xlsx 8,109,
pdf 1,337) with correct filenames, verified in a desktop browser. Opening them on a
handset is a Phase 9 item and is **not yet done**.

---

## WHAT A PM MIGHT ASK

**"Is my data sent anywhere?"** Transcript text goes to Groq (extraction and writing)
and TypeSafe (judgments). Nothing is stored server-side — the app is stateless and the
browser holds session state. Transcript content is never written to logs; logs carry
sizes, timings, counts and error types only.

**"Is this real client data?"** No. All three samples are synthetic, with fictional
companies (Northwind Bank, Contoso Insurance, Fabrikam). The UI carries a standing
banner: *"Demo uses synthetic data. Don't paste confidential client information."*

**"Can it invent a task or a person?"** Structurally, no. Action-item and RAID tables
are built **in code** from the classified items, never parsed out of the model's prose.
Every candidate must cite real transcript line numbers or it is dropped, and an owner
whose name does not appear in the transcript is nulled. The status report prose is
model-written, so it is the one place a phrasing error could appear — which is why
every item is traceable to its source lines.

**"What happens when it is unsure?"** Items with kind or audience confidence below 50%
go to the review queue. Between 50–80% they are pre-accepted and flagged. Above 80% they
are automatic. The PM can accept, edit or drop any item.

**"How does it decide Red/Amber/Green?"** Four separate Jev judgments — schedule, scope,
resourcing, client sentiment — combined by **rules in code**, not by the model. Red if
schedule is off-track, scope uncontrolled, resourcing blocked, or client sentiment
scores below 0.5. Amber if any sits in its middle state. The overall confidence is the
**lowest** of the four; below 50% the PM is asked to confirm.

**"What stops an internal comment reaching the client?"** Each item gets a yes/no-style
judgment on whether the client reading it would cause harm. It is only shown to the
client if **p(client_safe) ≥ 0.85**. The doubt always resolves toward internal.

**"Why two AI models?"** The LLM is good at reading messy text and writing prose but
gives no calibrated measure of its own certainty. Jev returns a probability distribution
over typed options, which code can threshold. The LLM extracts and writes; Jev judges;
code decides.

**"What does it cost to run?"** On free tiers, nothing — roughly 25 reports per day.
Jev is about $0.003 per three-sample run.

**"What are the limits?"** Transcripts up to 12,000 characters. English only (Jev's
accuracy is lower in other languages). No integrations — paste or upload `.txt`,
`.docx`, `.vtt`, `.srt`. Thresholds are tuned on three synthetic transcripts and would
need retuning on real data.

---

## THINGS NOT TO CLAIM

- Do not say the output is deterministic. It is not, and the spread is 2.2×.
- Do not quote 70%/86% or 65%/84%. Superseded.
- Do not say a report costs ~11,500 tokens. That was a retracted measurement.
- Do not say the daily limit is visible in the API headers. It is not.
- Do not say exports have been checked on a phone until that is done.
- Do not say rough-standup produces an empty client report. It produces one item.
