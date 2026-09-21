# Demo script

Full 3-minute talk track is written in Phase 10. This file already carries the two
things needed earlier: the **paste snippet** for the live moment, and the **ordering**
that keeps the token budget out of the way.

---

## Ordering — cached first, live last

The Groq free tier allows **8,000 tokens per minute**, and one full report *requests*
7,000–11,500. The three bundled samples are served from a committed cache and cost
**zero** tokens, so they can be tapped back to back. A live run costs the whole
budget.

Run the demo in this order:

| # | Step | Tokens | Why here |
|---|---|---|---|
| 1 | **Contoso sample** (cached) | 0 | The strongest story: Red status, a real slip, and the internal remark held back. Instant. |
| 2 | **Rough standup sample** (cached) | 0 | The review queue and the "no client-facing items" state. Instant. |
| 3 | **Northwind sample** (cached) | 0 | Optional, if there is time. Instant. |
| 4 | **Paste the snippet below** (live) | ~4,000 | *"Now watch it do yours."* The bucket has been refilling untouched throughout steps 1–3. |

**The cached runs are labelled as cached in the UI** — say so out loud. "These three
are precomputed so the demo can't be broken by a rate limit; this next one is live."
That reads as engineering judgment. Pretending they are live and getting caught does
not.

Keep the live paste **last**. If it is run first, the bucket is empty for everything
that follows.

---

## The live paste snippet

Short on purpose: **~1,200 characters**, so extraction requests roughly 2,600 tokens
instead of 7,000 and yields few enough items that generation is quick. This is the
fastest possible live run — seconds, not a minute.

Synthetic. Fictional company (Fabrikam), invented names.

```
Fabrikam Retail - Checkout Revamp
Weekly sync, 18 March 2026
Attendees: Lena Ortiz (PM), Sam Whitfield (Eng Lead), Ade Balogun (QA), Nora Kelly (Fabrikam)

Lena Ortiz: Quick one today. Sam, where are we on the payment provider swap?
Sam Whitfield: Sandbox is working end to end. I'll have the production keys wired up by Friday.
Ade Balogun: Testing is blocked until that lands. We have eleven scripts ready to run.
Lena Ortiz: Sam to wire up the production payment keys by Friday 20 March.
Nora Kelly: Our security team still needs to sign off on the provider. I've asked them twice.
Lena Ortiz: That's a dependency on Fabrikam security sign-off. Nora, can you chase it?
Nora Kelly: I'll push again this week.
Sam Whitfield: One risk. If sign-off slips past the 25th, we lose the March release window.
Lena Ortiz: Logging that. Ade, anything else?
Ade Balogun: The mobile checkout still drops the basket on session timeout. It's not new.
Lena Ortiz: Is that a blocker for release?
Ade Balogun: No, but it should be in the log.
Lena Ortiz: Agreed. Thanks everyone.
```

### What it should produce

A useful snippet is one you can check live without reading carefully:

- **Action item** — Sam, production payment keys, **due Friday 20 March** (owner and
  date both *stated*, so both should band **Stated**).
- **Action item** — Nora to chase security sign-off, "this week".
- **Dependency** — Fabrikam security sign-off. Client-side.
- **Risk** — sign-off slipping past the 25th costs the March release window.
- **Issue** — mobile checkout drops the basket on session timeout, low severity, not
  a release blocker.
- **Blocked testing** — eleven scripts waiting.

Points to make while it runs:
1. Tap a **source link** — every item cites the transcript lines it came from.
2. Nora is a **client-side** attendee, so the audience judgment has real work to do.
3. The stepper shows **"Judging with Jev"** and the count of judgments.
