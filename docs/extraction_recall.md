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

## Recall against the planted inventory

| Sample | Planted | Found | Recall | Candidates returned |
|---|---:|---:|---:|---:|
| `northwind-sprint-review` | 17 | **11** | 65 % | 13 |
| `contoso-escalation` | 19 | **14** | 74 % | 20 |
| `rough-standup-notes` | 27 | **16** | 59 % | 16 |
| **Total** | **63** | **41** | **65 %** | 49 |

### What was missed

**Northwind (6):** N3 Jonas chasing legal (folded into N2) · N6 the orphaned-document
*issue* as distinct from the action that fixes it · N7 the three cosmetic defects ·
N9 the risk that late data costs the first UAT week · N12 the dependency on Northwind
legal · N17 inconsistent rules-API error responses.

**Contoso (5):** C5 Diane taking the slip to the executive committee on Tuesday ·
C13 damaged client confidence after a second slip · C14 the assumption underpinning
the 29 May date · C16 the dependency on Contoso supplying 11 testers · C19 the
decision to keep the client's late sign-off out of the written note.

**Rough notes (11):** S8 "KT pending w/ infra - chk" · S10/S12/S18/S23/S24/S25 folded
into the action that addresses them · S11 the stale staging box · S20 contract
renewal · S22 the "might be fine for prod" assumption · S27 leaving the legacy export
in place.

**The dominant failure mode is merging, not hallucinating.** Most misses are a
problem and its remedy collapsed into one candidate, or a dependency absorbed into
the task that chases it. Nothing was invented: every candidate in all three runs cited
real line numbers, and no owner appeared that is absent from the transcript.

---

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
moved **68 % → 65 %**, and the change was not uniform:

| Sample | Before | After |
|---|---:|---:|
| `northwind-sprint-review` | 53 % | **65 %** |
| `contoso-escalation` | 74 % | 74 % |
| `rough-standup-notes` | **74 %** | 59 % |

The structured meetings improved; the messy notes **regressed**, and output tokens on
that sample fell from 2,754 to 1,374 — it simply did less work. The anti-merging
rules appear to be written for meeting-shaped input and do not transfer to bullet
notes. This is a real trade, not a win, and it is recorded as such.

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
