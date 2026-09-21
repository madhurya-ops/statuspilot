# Extraction recall — Phase 3 live runs

Scored against [`sample_ground_truth.md`](./sample_ground_truth.md), which was
written and committed **before** the first live run.

Model `openai/gpt-oss-20b`, `reasoning_effort=low`, `temperature=0`,
`max_completion_tokens=3200`, strict `json_schema`. Runs paced 95 s apart.

---

## Token cost per extraction call (the real numbers)

| Sample | Input | Output | **Total** | Latency |
|---|---:|---:|---:|---:|
| `northwind-sprint-review` (4937 chars) | 2,502 | 2,252 | **4,754** | 3.2 s |
| `contoso-escalation` (4886 chars) | 2,520 | 2,256 | **4,776** | 5.6 s |
| `rough-standup-notes` (2381 chars) | 1,948 | 1,374 | **3,322** | 2.2 s |

**Extraction alone costs ~4,300 tokens on a ~5,000-character transcript.**

### What this means for the 8,000 tokens/minute ceiling

1. **A full report will not fit twice in one minute.** Extraction is ~4.3 k and
   generation (Phase 5) will add its own call. A single end-to-end run lands around
   **7–9 k tokens**, i.e. at or just over the entire per-minute budget. The
   **precomputed sample cache is not a nicety — it is what makes a live demo
   survivable.** Confirmed empirically: three paced runs succeeded, and an earlier
   unpaced attempt returned 429 mid-sequence.
2. **`MAX_INPUT_CHARS=12000` is correctly sized, and is close to the true ceiling.**
   12,000 chars ≈ 3,000 input tokens; plus the 3,200 reserved for completion that is
   6,200 of 8,000 for a single call, before generation. Raising it would break
   single-call extraction on this tier.
3. **`max_completion_tokens` is billed against TPM as *requested* tokens.** A 429
   body reads `Limit 8000, Used 5645, Requested 5274`. An early setting of 6,000
   meant a ~2,500-token prompt needed 8,500 against an 8,000 ceiling — a single
   request exceeding the budget by itself. This is the least obvious constraint on
   the free tier and is why the value is now 3,200.

---

## Recall against the planted inventory — two numbers, not one

Every planted item falls in exactly one bucket:

- **Captured** — it exists as its **own candidate**, with its own `source_lines`.
- **Merged** — its content **is in the output**, inside another candidate's `text` or
  `evidence`, but it has no candidate of its own. Granularity is lost; content is not.
- **Absent** — it is **nowhere** in the output. This is the only true miss.

| Sample | Planted | Captured | Merged | Absent | **Strict recall** | **Content coverage** |
|---|---:|---:|---:|---:|---:|---:|
| `northwind-sprint-review` | 17 | 11 | 3 | 3 | 65 % | **82 %** |
| `contoso-escalation` | 19 | 13 | 3 | 3 | 68 % | **84 %** |
| `rough-standup-notes` | 27 | 16 | 7 | 4 | 59 % | **85 %** |
| **Total** | **63** | **40** | **13** | **10** | **63 %** | **84 %** |

**Strict recall (63 %)** = captured as its own candidate. This is the number that
predicts how good the RAID log and action-item tables will look, because each row in
those tables comes from one candidate. A merged item does not get its own row.

**Content coverage (84 %)** = captured **or** merged, i.e. the share of planted
material that reaches the output at all and is therefore visible to Jev and to the
PM. This is the number that predicts whether the status report's *narrative* misses
anything.

Both belong in front of a PM. Quoting only 84 % would overstate how complete the
tables are; quoting only 63 % would understate how much of the meeting survives.

> A previous revision of this file reported 41 captured. A careful re-scoring against
> the bucket definitions gives **40**; C15 (the vendor dependency, whose "Contoso
> contract, no leverage" clause at L23–24 is uncited) is **merged**, not captured.

### Absent — the ten genuine misses

**Northwind (3):** N3 Jonas chasing legal (L24–27 uncited) · N7 the three cosmetic
defects (L15 uncited) · N17 inconsistent rules-API error responses (L9–10 uncited).

**Contoso (3):** C5 Diane taking the slip to the executive committee on Tuesday
(L30 uncited) · C13 damaged client confidence after a second slip (L37–38 uncited) ·
C19 the decision to keep the client's late sign-off out of the note — L47 is cited
but only L46's content is carried in `evidence`.

**Rough notes (4):** S8 "KT pending w/ infra - chk" (L9) · S11 the stale staging box,
open since February (L10–11) · S20 the parallel contract renewal (L24–25) · S22 the
"40-minute reindex might be fine for prod" assumption (L42).

**Nothing was hallucinated in any run.** Every candidate cited real line numbers and
no owner appeared that is absent from the transcript.

## Prompt iteration — and an honest note about the trade

The first live run scored **43/63 (68 %)** but had a **disqualifying flaw**: the
Contoso blame remark at **L46** was not extracted at all. Section 9 requires it to
classify `internal_only`, and Jev cannot classify a candidate that was never created.
The client-safe filter — one of the four things Section 12 says must never be cut —
would have had nothing to demonstrate.

The prompt was revised to (a) forbid merging a problem with its remedy, (b) set a
"15–30 candidates" expectation, and (c) explicitly require extracting opinion,
criticism and blame, stating that a later step judges tone.

**Result: L46 is now extracted**, with `evidence` preserving the remark verbatim —
which is what Section 6's `audience` question actually judges. But the overall score
moved **68 % → 63 % strict**, and the change was not uniform:

| Sample | Strict, before | Strict, after |
|---|---:|---:|
| `northwind-sprint-review` | 53 % | **65 %** |
| `contoso-escalation` | 74 % | 68 % |
| `rough-standup-notes` | **74 %** | 59 % |

### Was the rough-notes regression a truncation artifact? No.

Output tokens on that sample halved, 2,754 → 1,374, which is the signature of a
response cut off at the completion cap. It was not.

| Run | `max_completion_tokens` | Output tokens | Headroom |
|---|---:|---:|---:|
| Before the prompt change | 6,000 | 2,754 | 54 % unused |
| After the prompt change | 3,200 | 1,374 | **57 % unused** |

**A truncated response stops *at* the cap.** Both runs finished with more than half
their budget unspent, so neither could have had `finish_reason: "length"` — the model
stopped because it considered itself done. The cap was lowered between the runs, but
never reached in either, so it cannot explain the drop.

The regression is therefore **genuine prompt behaviour**: the anti-merging rules
("a problem AND the task that fixes it are separate candidates") are phrased for
meeting dialogue and do not transfer to bullet notes, where a single bullet often
*is* both. Accepted and documented rather than papered over.

> `finish_reason` was not recorded at the time; the conclusion above rests on the
> token arithmetic, which is decisive. The field is now captured on every call
> (`LLMUsage.finish_reason`), logged, and warned on when it equals `"length"`, so
> this question is answered directly rather than inferred next time.

Note also that the three buckets soften the picture: rough-notes **content coverage
is 85 %**, the highest of the three samples. The regression is concentrated in
granularity — items merging into neighbours — rather than in content being lost.

**Recommendation:** accept for now. The critical demo path is fixed, and
`rough-standup-notes` still yields 16 candidates, which is ample for the Gate 4
requirement of ≥3 review items — a requirement about *confidence*, not count. A
further prompt pass targeting bullet-style input is worthwhile if there is budget,
but each iteration costs ~14 k tokens and roughly five minutes of pacing.

---

## Other observations

- **The model softens `text` even when told not to.** L46 became "The mapping document
  was not signed off in January as promised" rather than the original's blunt
  phrasing. Harmless here, because `evidence` is verbatim and `audience` is judged on
  `item.evidence` — but worth knowing that `text` is editorialised.
- **`kind_hint` collapsed to `action_item` on the rough-notes run** (13 of 16).
  Informational only, and nothing downstream branches on it, but it means the hint
  carries little signal on messy input.
- **Owners are inferred on the rough notes.** "Priya to submit timesheets by Friday"
  is an inference — L33 reads `priya: reminder timesheets due friday`, which is Priya
  *reminding others*. The name passes the anti-hallucination check because it appears
  in the transcript. This is exactly what the `owner_explicit` Noul is for in Phase 4,
  and it should band as "Inferred" rather than "Stated".
- **Attendee extraction on rough notes** returned `me`, `dan`, `sasha`, `priya`,
  `infra guy` — faithful to an input that literally says "me, dan, sasha".
