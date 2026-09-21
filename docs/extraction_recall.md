# Extraction recall — Phase 3 live runs

Scored against [`sample_ground_truth.md`](./sample_ground_truth.md), which was
written and committed **before** the first live run.

Model `openai/gpt-oss-20b`, `reasoning_effort=low`, `temperature=0`,
`max_completion_tokens=3200`, strict `json_schema`. Runs paced 95 s apart.

---

## Token budget — measured, and the news is bad

### Consumed vs requested — a claim that did not survive retesting

> **RETRACTED 2026-09-22.** This section previously asserted that Groq bills its
> token limit on **requested** tokens (`prompt + max_completion_tokens`) rather than
> consumed ones. **That does not reproduce and should not be relied on.**

The original evidence was a single reading: `x-ratelimit-remaining-tokens` fell
7,927 → 980 across one extraction that consumed 5,415, and `8000 − 980 = 7020 =
2520 + 4500` exactly. An exact arithmetic match from one sample is a coincidence far
more often than it is a law, and it was not retested.

Retested directly:

| Probe | `max_completion_tokens` | Outcome | Consumed |
|---|---:|---|---:|
| A | 9,000 (above the 8,000/min ceiling) | **accepted** | 103 |
| B | 60,000 | **accepted** | 144 |

If the cap were reserved against the bucket, both would have been refused instantly.
Neither was, and neither moved `remaining-tokens` meaningfully. The original reading
was most likely confounded by other usage inside the same minute.

**What to rely on instead: actual consumption**, from the `usage` object on each
response. That is measurable per call and needs no inference.

### What a full report actually costs

Measured consumption, not reservation:

| Stage | Prompt | Completion | **Consumed** |
|---|---:|---:|---:|
| Extract (~5,000-char transcript) | ~2,500 | ~2,300–2,900 | **~4,800–5,400** |
| Generate (12–24 items) | ~1,400–2,500 | ~1,000–2,000 | **~2,500–4,000** |
| **Full report** | | | **~8,000** |

### The per-minute limit still bites; the per-day one is the real ceiling

At ~8,000 consumed per report against an **8,000 tokens/minute** bucket refilling at
~133/second, a report uses close to a full minute's allowance. Extraction and
generation back to back will still meet a short wait, which the UI labels honestly.

The **200,000 tokens/day** cap is the harder limit and remains invisible in headers —
it appears only in a 429 body. At ~8,000 consumed per report that is roughly **25 full
live reports per day**, not the ~17 previously stated here on the retracted
requested-tokens basis.

### Per-sample extraction cost

| Sample | Prompt | Completion | Consumed | **Requested** |
|---|---:|---:|---:|---:|
| `northwind-sprint-review` (4,937 chars) | 2,502 | ~2,300 | ~4,800 | **7,002** |
| `contoso-escalation` (4,886 chars) | 2,520 | 2,895 | 5,415 | **7,020** |
| `rough-standup-notes` (2,381 chars) | 1,948 | 1,593 | 3,541 | **6,448** |

Jev, by contrast, is not a constraint: ~870 input tokens per candidate, 250 k
tokens/second and 1,200 requests/minute published, and ~$0.0015 for a 40-candidate
run.

## Recall against the planted inventory — two numbers, not one

**Re-measured 2026-09-21 against the current pipeline**, after the Phase 4 truncation
fix. The earlier figures were taken on **silently truncated output** — under strict
`json_schema` a response that hits the completion cap still parses, so
`rough-standup-notes` was scored on 11 candidates when the same input actually yields
22. Those numbers are superseded.

Every planted item falls in exactly one bucket:

- **Captured** — it exists as its **own candidate**, with its own `source_lines`.
- **Merged** — its content **is in the output**, inside another candidate's `text` or
  `evidence`, but it has no candidate of its own. Granularity is lost; content is not.
- **Absent** — it is **nowhere** in the output. This is the only true miss.

| Sample | Planted | Captured | Merged | Absent | **Strict recall** | **Content coverage** |
|---|---:|---:|---:|---:|---:|---:|
| `northwind-sprint-review` | 17 | 12 | 1 | 4 | **71 %** | 76 % |
| `contoso-escalation` | 19 | 15 | 2 | 2 | **79 %** | **89 %** |
| `rough-standup-notes` | 27 | 17 | 7 | 3 | **63 %** | **89 %** |
| **Total** | **63** | **44** | **10** | **9** | **70 %** | **86 %** |

**Strict recall (70 %)** = the planted item became its **own candidate**. This predicts
how complete the RAID log and action-item **tables** are, because each row needs one
candidate. A merged item gets no row of its own.

**Content coverage (86 %)** = the item reached the output **at all**, captured or
merged — the share of planted material visible to Jev and to the PM. This predicts
whether the status report **narrative** misses anything.

Both belong in front of a PM. 86 % alone would overstate how complete the tables are;
70 % alone would understate how much of the meeting survives.

### Movement since the truncated measurement

| | Strict | Coverage |
|---|---:|---:|
| Measured on truncated output | 63 % | 84 % |
| **Current** | **70 %** | **86 %** |

Per sample, strict recall: northwind 65 % → **71 %**, contoso 68 % → **79 %**,
rough-standup 59 % → **63 %**. The rough-notes sample gained the least in strict terms
but its coverage is now 89 %, joint-highest — its misses are concentrated in merging,
not in loss.

### Absent — the nine genuine misses

**Northwind (4):** N3 Jonas chasing legal (L24–27 uncited) · N7 the three cosmetic
defects (L15) · N14 the decision to log the defect as *high* severity (L21–22) ·
N17 inconsistent rules-API error responses (L9–10).

**Contoso (2):** C5 Diane taking the slip to the executive committee on Tuesday (L30) ·
C19 the decision to keep the client's late sign-off out of the written note — L46 is
captured but L47, where that decision is made, is not.

**Rough notes (3):** S8 "KT pending w/ infra - chk" (L9) · S17 the explicit
*"risk: if creds don't land by ~20th, billing slips past demo"* (L23) ·
S20 the parallel contract renewal (L24–25).

> **One regression worth naming.** S17 was captured in an earlier run and is absent
> now. It is an explicitly labelled risk in the source text, so losing it is a worse
> miss than the merges. Recorded rather than smoothed over.

**Nothing was hallucinated in any run.** Every candidate cites real line numbers, and
no owner appears who is not in the transcript.

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

---

## The dynamic completion cap

Scaling `max_completion_tokens` from the prompt was introduced to cut "reserved but
unused" tokens. **Since the reservation claim is retracted, that was not the benefit it
appeared to be.**

The mechanism is kept anyway, because it earns its place for a different reason: a cap
that is too small silently truncates. Under strict `json_schema` a truncated response
still *parses* — the constrained decoder closes the JSON — so items are lost with no
error. `rough-standup-notes` returned 11 candidates truncated and 22 once the cap was
raised.

The ratio is 2.0 for extraction because measured completion/prompt ratios span
0.65–1.85: bullet notes pack far more items per prompt token than meeting dialogue.
A truncation retry costs a whole extra call, so erring generous is the cheaper mistake.
