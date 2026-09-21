import type { Decision } from "../types";

/** Confidence bands. Colour is never the only signal — the number is always shown. */
export function confidenceBand(confidence: number): "high" | "medium" | "low" {
  if (confidence >= 0.8) return "high";
  if (confidence >= 0.5) return "medium";
  return "low";
}

const BAND_FILL: Record<string, string> = {
  high: "var(--color-rag-green)",
  medium: "var(--color-rag-amber)",
  low: "var(--color-rag-red)",
};

/**
 * The signature device: where belief actually sits.
 *
 * A bare "62% sure" says less than seeing the mass. This is reused for confidence,
 * for the kind distribution and for RAG, so the same visual question — how spread out
 * is this? — is always asked the same way.
 */
export function Measure({ value, band }: { value: number; band?: "high" | "medium" | "low" }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const fill = BAND_FILL[band ?? confidenceBand(value)];
  return (
    <div className="measure" aria-hidden="true">
      <span style={{ width: `${pct}%`, background: fill }} />
    </div>
  );
}

export function ConfidenceBadge({
  confidence,
  label = "sure",
}: {
  confidence: number | null;
  label?: string;
}) {
  if (confidence === null) return null;
  const band = confidenceBand(confidence);
  const pct = Math.round(confidence * 100);
  const tone =
    band === "high"
      ? "text-rag-green"
      : band === "medium"
        ? "text-rag-amber"
        : "text-rag-red";
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`text-xs font-semibold tabular-nums ${tone}`}>
        {pct}% {label}
      </span>
      <span className="w-10">
        <Measure value={confidence} band={band} />
      </span>
    </span>
  );
}

/** The top few options with their probability mass, for a Choice decision. */
export function Distribution({ decision, max = 3 }: { decision: Decision; max?: number }) {
  const probs = decision.probabilities;
  if (!probs) return null;
  const rows = Object.entries(probs)
    .sort((a, b) => b[1] - a[1])
    .slice(0, max)
    .filter(([, p]) => p > 0.005);
  if (rows.length < 2) return null;
  return (
    <ul className="mt-2 space-y-1.5">
      {rows.map(([option, p]) => (
        <li key={option} className="flex items-center gap-2">
          <span className="w-28 shrink-0 truncate text-xs text-ink-soft">
            {option.replace(/_/g, " ")}
          </span>
          <span className="flex-1">
            <Measure
              value={p}
              band={option === decision.label ? "high" : "medium"}
            />
          </span>
          <span className="w-9 shrink-0 text-right text-xs tabular-nums text-ink-faint">
            {Math.round(p * 100)}%
          </span>
        </li>
      ))}
    </ul>
  );
}
