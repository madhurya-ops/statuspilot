import { Button, Screen } from "../components/Chrome";
import { Measure } from "../components/Measure";
import type { Action } from "../state/session";

/** The honest explanation. Every number here matches what the code actually does. */
export function HowItWorks({
  dispatch,
  onBack,
}: {
  dispatch: React.Dispatch<Action>;
  onBack?: () => void;
}) {
  return (
    <Screen
      onBack={onBack}
      backLabel="Back to reports"
      action={
        <Button full variant="secondary" onClick={() => dispatch({ type: "go", screen: "results" })}>
          Back to reports
        </Button>
      }
    >
      <h1 className="text-lg font-semibold">How it works</h1>

      <ol className="mt-4 space-y-3">
        {[
          ["Groq reads the transcript", "An LLM pulls out every candidate item — tasks, risks, issues, dependencies, decisions. It over-extracts on purpose."],
          ["Jev judges each one", "A separate model answers five typed questions per item and returns a probability for every option, not just a label."],
          ["You review what it's unsure about", "Code routes on those probabilities. Confident items are accepted; uncertain ones come to you."],
          ["Groq writes the prose", "Only the items you approved, and only the client-safe ones in the client report."],
        ].map(([title, body], i) => (
          <li key={title} className="flex gap-3">
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-wash text-xs font-bold text-indigo">
              {i + 1}
            </span>
            <div>
              <p className="text-sm font-semibold">{title}</p>
              <p className="mt-0.5 text-[0.8125rem] leading-relaxed text-ink-soft">{body}</p>
            </div>
          </li>
        ))}
      </ol>

      <Section title="What the confidence number means">
        <p>
          Jev spreads its belief across the options and returns a probability for each.
          Confidence measures how concentrated that spread is — not whether the answer
          is right.
        </p>
        <div className="mt-3 space-y-2">
          <Row label="80% and above" body="Accepted automatically." value={0.9} />
          <Row label="50–79%" body="Pre-accepted, flagged for a glance." value={0.65} />
          <Row label="Below 50%" body="Sent to your review queue." value={0.3} />
        </div>
      </Section>

      <Section title="Severity is a position, not a label">
        <p>
          Jev doesn't pick "High". It returns a weighted position across Low, Medium and
          High — an item might score <strong>1.74 out of 2</strong>, meaning mostly High
          with some Medium. We show the nearest band as the label and sort by the exact
          number underneath, so a 1.9 outranks a 1.6 even though both read "High".
        </p>
      </Section>

      <Section title="Owner and date: stated, inferred, or not specified">
        <p>
          A separate yes/no judgment asks whether the transcript actually names an owner.
          It returns a probability with no confidence attached, so we band the value
          itself: <strong>0.75 and above</strong> is "stated", <strong>0.35 and below</strong>{" "}
          is "not specified", and the middle is "inferred" — genuinely unsure, which is
          not the same as half-stated.
        </p>
      </Section>

      <Section title="How the overall status is decided">
        <p>Four judgments, combined by rules in code rather than by the model:</p>
        <ul className="mt-2 space-y-1.5 text-[0.8125rem]">
          <li>
            <strong>Red</strong> if schedule is off track, scope is uncontrolled,
            resourcing is blocked, or client sentiment scores below 0.5.
          </li>
          <li>
            <strong>Amber</strong> if any of those sits in its middle state.
          </li>
          <li>
            <strong>Green</strong> otherwise.
          </li>
        </ul>
        <p className="mt-2">
          The overall confidence is the lowest of the four. Below 50% we ask you to
          confirm it.
        </p>
      </Section>

      <Section title="The client-safe filter">
        <p>
          Every item is judged on whether it would cause harm or embarrassment for the
          client to read. If the model isn't confident that an item is safe, it is held
          back — the doubt always resolves towards internal, never towards the client.
        </p>
      </Section>

      <Section title="Why this matters">
        <ul className="space-y-1.5 text-[0.8125rem]">
          <li>The AI tells you when it isn't sure instead of guessing.</li>
          <li>Every item cites the transcript lines it came from.</li>
          <li>Tables are built from the data in code, so nothing can be invented.</li>
        </ul>
      </Section>
    </Screen>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-6 border-t border-line pt-4">
      <h2 className="text-sm font-semibold">{title}</h2>
      <div className="mt-1.5 text-[0.8125rem] leading-relaxed text-ink-soft [&_p]:mb-2">
        {children}
      </div>
    </section>
  );
}

function Row({ label, body, value }: { label: string; body: string; value: number }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-24 shrink-0">
        <Measure value={value} />
      </span>
      <span className="text-[0.8125rem]">
        <strong className="font-semibold text-ink">{label}</strong> — {body}
      </span>
    </div>
  );
}
