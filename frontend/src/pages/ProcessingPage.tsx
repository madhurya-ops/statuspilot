import { CachedTag, Screen } from "../components/Chrome";
import type { SessionState, Step } from "../state/session";

export function ProcessingPage({ state }: { state: SessionState }) {
  const stats = state.classified?.stats;
  const judgments = stats ? stats.requests * 5 : 0;
  const review = state.classified?.items.filter((i) => i.routing === "review").length ?? 0;
  const auto = state.classified?.items.filter((i) => i.routing !== "review").length ?? 0;

  return (
    <Screen>
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Building your reports</h1>
        {state.cached ? <CachedTag /> : null}
      </div>

      <ol className="mt-6 space-y-1">
        {state.steps.map((step) => (
          <StepRow key={step.id} step={step} />
        ))}
      </ol>

      {stats ? (
        <p className="mt-6 font-doc text-lg leading-snug">
          <strong className="font-semibold tabular-nums">{judgments}</strong> judgments by
          Jev in <strong className="font-semibold tabular-nums">
            {(stats.latency_ms / 1000).toFixed(1)}s
          </strong>
          {" · "}
          <span className="tabular-nums">{auto}</span> accepted
          {review > 0 ? (
            <>
              {" · "}
              <span className="tabular-nums">{review}</span> need your review
            </>
          ) : null}
        </p>
      ) : null}

      {state.cached ? (
        <p className="mt-3 text-xs leading-relaxed text-ink-faint">
          This sample is precomputed, so it costs no tokens and can't be broken by a
          rate limit. Paste your own text to run it live.
        </p>
      ) : null}
    </Screen>
  );
}

function StepRow({ step }: { step: Step }) {
  const done = step.state === "done";
  const active = step.state === "active";
  const waiting = step.state === "waiting";

  return (
    <li className="flex items-start gap-3 py-2.5">
      <Marker state={step.state} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <span
            className={`text-sm ${done || active || waiting ? "font-medium text-ink" : "text-ink-faint"}`}
          >
            {step.label}
          </span>
          {done && step.ms !== undefined ? (
            <span className="shrink-0 text-xs tabular-nums text-ink-faint">
              {(step.ms / 1000).toFixed(1)}s
            </span>
          ) : null}
        </div>

        {/* A wait is a talking point if it is labelled. A bare spinner reads as a slow
            app; naming the free-tier budget reads as cost-awareness. */}
        {waiting && step.waitReason ? (
          <p className="mt-1 text-xs leading-relaxed text-rag-amber">
            {step.waitReason}
            {step.waitSeconds !== undefined ? (
              <> — <span className="tabular-nums">{step.waitSeconds}s</span></>
            ) : null}
          </p>
        ) : null}
      </div>
    </li>
  );
}

function Marker({ state }: { state: Step["state"] }) {
  const base = "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[0.625rem] font-bold";
  if (state === "done") {
    return (
      <span className={`${base} bg-rag-green-wash text-rag-green`} aria-label="Done">
        ✓
      </span>
    );
  }
  if (state === "active") {
    return (
      <span className={`${base} bg-indigo-wash text-indigo`} aria-label="In progress">
        <span className="h-2 w-2 animate-pulse rounded-full bg-indigo" />
      </span>
    );
  }
  if (state === "waiting") {
    return (
      <span className={`${base} bg-rag-amber-wash text-rag-amber`} aria-label="Waiting">
        ⏸
      </span>
    );
  }
  return <span className={`${base} bg-wash text-ink-faint`} aria-hidden="true">·</span>;
}
