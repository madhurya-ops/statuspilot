# Sample ground truth

**Written before the first live extraction run** (Phase 3, 2026-09-21), reconstructed
from the sample text itself — *not* from anything a model produced. This is the
scoring key for extraction recall, so it must not be revised to match model output.
If a run finds something real that is missing here, add it as a **separate
"unplanted but valid"** note rather than editing an existing row, so the original
key stays honest.

Line numbers refer to **normalised** lines (`normalize_text` → `to_lines`), which is
what the pipeline actually cites in `source_lines`.

Notation: **A** action item · **R** risk · **AS** assumption · **I** issue ·
**D** dependency · **DE** decision.

---

## 1. `northwind-sprint-review` — 51 lines

Expected overall RAG: **Amber** (stated outright at L48: amber, not green, because of
test data).

| # | Type | Item | Owner | Due | Lines |
|---|---|---|---|---|---|
| N1 | **A** | Fix the orphaned document reference defect (upload must be transactional) | Marcus Webb | Thursday | 19, 20 |
| N2 | **A** | Update the affordability declaration wording once Northwind legal provides it | Tom Fielding | 20 March | 25, 28 |
| N3 | **A** | Chase Northwind legal for the approved affordability wording | Jonas Kern | "this week" / by the 20th | 27 |
| N4 | **A** | Confirm the anonymised test data date with Northwind data governance | Jonas Kern | Monday 16 March | 39, 40 |
| N5 | **A** | Raise the infrastructure ticket to repoint the UAT environment to the new rules API | Marcus Webb | before 6 April | 44, 45 |
| N6 | **I** | Orphaned document reference: record looks complete but the document reference points at nothing. Agreed **high** severity despite low frequency (L21–22) | Marcus Webb | — | 16, 18, 21, 22 |
| N7 | **I** | Three cosmetic defects: spacing on applicant summary, truncated Welsh label, US date order on one report. **Low** severity | — | — | 15 |
| N8 | **I** | UAT environment still points at the old rules API endpoint; nothing will work until repointed | Infrastructure / Marcus Webb | — | 41, 42 |
| N9 | **R** | Anonymised test data may arrive late, costing the first week of UAT (UAT starts 6 April) | — | — | 34, 35 |
| N10 | **AS** | **The planted assumption.** The team has been assuming anonymised data is available by end of March; explicitly "not confirmed anywhere" (L36) | — | — | 36, 37 |
| N11 | **D** | **The planted dependency.** Northwind's data governance team must provide ~200 anonymised applicant records | Jonas Kern / Northwind | — | 31, 32, 38 |
| N12 | **D** | Northwind legal must supply the approved affordability declaration wording | Jonas Kern / Northwind legal | 20 March | 24, 25, 27 |
| N13 | **DE** | Drop the audit log export story from Sprint 14; carry it to Sprint 15 | — | — | 12, 13 |
| N14 | **DE** | Log the orphaned-document defect as **high** severity | — | — | 21, 22 |
| N15 | **DE** | Report the project as **Amber**, not Green, because of the test data | — | — | 48, 49 |
| N16 | **DE** | Escalate the test data dependency to the steering committee | — | — | 46, 47 |
| N17 | **R** | Rules API error responses are inconsistent (JSON and plain text); already wrapped, so contained | — | — | 9, 10 |

**Deliberately missing an owner:** N7, N9, N10, N13, N14, N15, N16, N17.
**Deliberately missing a date:** N6, N7, N8, N9, N10, N11 (the whole point — the date
is what Jonas must go and find), N13–N17.
**Owner stated but vague:** N8 ("Infrastructure, but I can raise the ticket", L44).

**Discussion-only, should NOT become items:** L5–L8 (agenda, sprint goal recap,
document upload already merged), L11, L14, L23 (demo already happened, feedback
good), L29, L33, L43, L46, L50, L51.

---

## 2. `contoso-escalation` — 53 lines

Expected overall RAG: **Red**. Go-live slipped a month, a blocking defect, an
overdue vendor, and explicit client dissatisfaction.

| # | Type | Item | Owner | Due | Lines |
|---|---|---|---|---|---|
| C1 | **A** | Escalate the document storage API delay with the vendor account director | Diane Okafor (client side) | this week | 25, 26 |
| C2 | **A** | Provide a written recovery note covering cause, recovery plan and what changes | Priya Nair | Monday 16 March | 31, 32 |
| C3 | **A** | Deliver the multi-policy transformation fix and a clean rehearsal | Raj Menon | 27 March | 33, 34 |
| C4 | **A** | Reissue the UAT plan for the 6 April window and reconfirm tester bookings | Elena Fischer | 20 March | 35, 36 |
| C5 | **A** | Take the slip to the Contoso executive committee | Diane Okafor | Tuesday | 30 |
| C6 | **A** | Record the rehearsal-cycle sizing error in lessons learned | Priya Nair | — | 48, 49 |
| C7 | **I** | Multi-policy claims migrate with policy links dropped — ~9% of the historical set, ~41,000 records, the most complex claims. **High** | Raj Menon | — | 9, 10, 12, 13 |
| C8 | **I** | UAT cannot start while the defect is open; 23 scripts ready and 11 Contoso testers idle, released from day roles. **High** | Elena Fischer | — | 16, 17, 18 |
| C9 | **I** | Vendor document storage API overdue since 28 February; third promised date is 27 March. **High** | Vendor / Diane Okafor | 27 March | 21, 22 |
| C10 | **I** | Go-live of 30 April is no longer achievable; a month's slip to 29 May | Priya Nair | — | 6, 28, 30 |
| C11 | **R** | **Planted, stated as a risk (L50–51).** If the fourth rehearsal is not clean, the May date goes too | — | — | 50, 51 |
| C12 | **R** | **Planted key-person risk (L52).** One architect deep on the transformation logic; if Raj is unavailable in the next three weeks there is a problem | — | — | 52, 53 |
| C13 | **R** | Client confidence is damaged — second slip, and the first was communicated a week late | — | — | 37, 38 |
| C14 | **AS** | The 29 May date **assumes** the transformation fix lands by 27 March and the fourth rehearsal is clean | — | — | 28 |
| C15 | **D** | Vendor must deliver the document storage API; it is a **Contoso** contract, so the team has no direct leverage | Diane Okafor / vendor | 27 March | 21, 23, 24 |
| C16 | **D** | Contoso must supply 11 testers for the rebooked 6 April UAT window | Elena Fischer / Contoso | 6 April | 17, 29, 35 |
| C17 | **DE** | Move go-live from 30 April to **29 May** | — | — | 28, 39 |
| C18 | **DE** | Move UAT to a four-week window starting 6 April | — | — | 29 |
| C19 | **DE** | Keep the client's late mapping sign-off **out** of the written note; the team owns the transformation logic | Priya Nair | — | 47 |

### The internal-only aside — the single most important classification in the demo

**L44** — *"Right, they have gone. Let us have two minutes internally."* marks the
point where the client leaves. **Everything from L44 to L53 is internal.**

| Line | Text | Why it must be `internal_only` |
|---|---|---|
| **L46** | *"Honestly their team never reviews anything on time. Half of those forty one thousand records would not be an issue if they had signed off the mapping document in January like they promised."* | **The planted blame remark.** A direct criticism of the client's own behaviour. Section 6's `audience` criteria name exactly this: "a remark about the client's own behaviour". Leaking it into a client-facing status report is the worst failure this product can have. |
| L48 | *"we sized the rehearsal cycle wrong. Five days was always optimistic."* | Internal admission of an estimation error. |
| L45 | *"That went better than I expected."* | Internal opinion; also discussion-only. |
| L52 | Key-person risk about Raj | A real risk (C12), but naming a staffing single point of failure is internal. |

C11 (rehearsal risk) is genuinely borderline: the *fact* that May depends on a clean
rehearsal is client-safe and is already stated on the call at L28. Only the internal
framing at L50 is not.

**Deliberately missing an owner:** C11, C13, C14, C17, C18.
**Deliberately missing a date:** C6, C7, C8, C10, C11, C12, C13, C19.

**Discussion-only:** L5, L7, L8, L11, L15, L19, L20, L23, L27, L40–L45.

---

## 3. `rough-standup-notes` — 43 lines

**No speaker prefixes at all** (0 of 43 lines), abbreviations (`w/`, `chk`, `KT`),
hedged language (`maybe`, `should probably`, `might`), and explicitly unassigned
actions. This sample exists to **produce low-confidence judgments**, so a high
extraction count here is not automatically a good result — Gate 4 requires **≥3**
items routed to review.

| # | Type | Item | Owner | Due | Lines |
|---|---|---|---|---|---|
| S1 | **A** | Tidy up the remaining deep-link edge cases from the nav refactor | dan | "thurs or fri", explicitly *not urgent* | 4, 5 |
| S2 | **A** | **Unassigned by design.** Ask the client whether the legacy export is still needed — note literally says "(not assigned)" | **none** (L20) | — | 19, 20 |
| S3 | **A** | Chase the billing sandbox credentials again | sasha | "this week" | 21, 22 |
| S4 | **A** | Confirm the client demo date with the account team | — | — | 13 |
| S5 | **A** | Fix the stale onboarding readme (still references the old build script) | sasha | **"when i get a sec"** — deliberately non-committal | 31, 32 |
| S6 | **A** | Investigate the reindex slowdown / perf — hedged as "maybe look at perf?", "at some point" | — | — | 7, 8 |
| S7 | **A** | Verify dan's claim that the coverage drop is deleted nav tests, not real regression — hedged "should probably" | — | — | 27, 28 |
| S8 | **A** | KT pending with infra — "chk". **Maximally vague**: no verb, no owner, no date | — | — | 9 |
| S9 | **A** | Timesheets due Friday | all / priya reminding | Friday | 33 |
| S10 | **I** | Reindex takes 40 min, was 12; cause unknown (analyzer? disk?) | — | — | 7, 8 |
| S11 | **I** | Staging box still on the old image, never repointed; **open since ~February** | infra | — | 10, 11 |
| S12 | **I** | Test coverage down to 61% from 78% | — | — | 26 |
| S13 | **I** | Production logging too noisy to search. Note explicitly says **"no owner, no date"** | **none** (L30) | **none** (L30) | 29, 30 |
| S14 | **I** | Accessibility audit never happened; was due in sprint 3 | — | — | 37 |
| S15 | **I** | Perf budget agreed but nobody is measuring it | — | — | 39 |
| S16 | **I** | Search cluster cost has risen; nobody has investigated | — | — | 43 |
| S17 | **R** | If billing sandbox creds do not land by ~20th, billing slips past the demo | — | ~20th | 23 |
| S18 | **R** | Demo date uncertain (26th or 27th); if the 26th, the search work is tight | — | 26th/27th | 13, 14 |
| S19 | **R** | **Bus-factor risk.** Release process ownership never written down; it has always been dan. Unclear what happens if dan is off | — | — | 40, 41 |
| S20 | **R** | Contract renewal running in parallel, might affect scope; noted as "not our problem directly" | — | — | 24, 25 |
| S21 | **R** | Design system still on v2 while v4 is out, with no migration plan | — | — | 38 |
| S22 | **AS** | Assumption that the 40-minute reindex "might actually be fine for prod" — explicitly needs real numbers | — | — | 42 |
| S23 | **AS** | Assumption that the coverage drop is not a real regression (dan's unverified claim) | — | — | 27, 28 |
| S24 | **D** | Billing integration blocked waiting on sandbox credentials from the other side; chased twice | sasha | — | 21, 22 |
| S25 | **D** | Demo date depends on the account team confirming | — | — | 13 |
| S26 | **DE** | Ship basic search for the demo, faceting afterwards | sasha | demo date | 15, 16 |
| S27 | **DE** | Leave the legacy export in place for now, since nobody knew whether it is needed | — | — | 17, 18 |

**Deliberately unassigned:** S2 (says "(not assigned)"), S13 (says "no owner, no
date"), S4, S6, S7, S10, S12, S14–S23, S25, S27.
**Deliberately vague / low-confidence by construction:** S5 ("when i get a sec"),
S6 ("maybe look at perf?", "at some point"), S7 ("should probably"), S8 ("KT pending
w/ infra - chk"), S18 (date genuinely unknown), S22 ("might actually be fine?").

**Discussion-only:** L1–L3 (header), L34 ("AOB: none"), L35, L36 (section label).

---

## Counts

| Sample | A | R | AS | I | D | DE | **Total** |
|---|---:|---:|---:|---:|---:|---:|---:|
| `northwind-sprint-review` | 5 | 2 | 1 | 3 | 2 | 4 | **17** |
| `contoso-escalation` | 6 | 3 | 1 | 4 | 2 | 3 | **19** |
| `rough-standup-notes` | 9 | 5 | 2 | 7 | 2 | 2 | **27** |

`MAX_CANDIDATES` is **40**, so no sample should be capped.

## How recall is scored

A planted item counts as **found** when an extracted candidate refers to the same
underlying thing, judged by overlap of `source_lines` and meaning — **not** by exact
wording, and **not** by whether the model's `kind_hint` matches the type column.
Typing is Jev's job in Phase 4, not the extractor's.

Extraction is instructed to **over-extract** (Section 8), so candidates beyond this
inventory are expected and are not errors. They are reported separately as
"unplanted", and only count against the run if they are hallucinations — an item
with no basis in the cited lines, or an owner or date that appears nowhere in the
transcript.
