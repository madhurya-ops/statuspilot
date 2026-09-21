import { useState } from "react";
import type { ClassifiedItem, RagStatus, TranscriptLine } from "../types";
import { ConfidenceBadge, Distribution } from "./Measure";

const SEVERITY_TONE: Record<string, string> = {
  High: "bg-rag-red-wash text-rag-red",
  Medium: "bg-rag-amber-wash text-rag-amber",
  Low: "bg-wash text-ink-soft",
};

const RAG_TONE: Record<RagStatus, string> = {
  Red: "bg-rag-red-wash text-rag-red border-rag-red/25",
  Amber: "bg-rag-amber-wash text-rag-amber border-rag-amber/25",
  Green: "bg-rag-green-wash text-rag-green border-rag-green/25",
};

export function Chip({ children, tone = "" }: { children: React.ReactNode; tone?: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[0.6875rem] font-semibold ${tone || "bg-wash text-ink-soft"}`}
    >
      {children}
    </span>
  );
}

export function RagPill({ status, confidence }: { status: RagStatus; confidence?: number }) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-lg border px-2.5 py-1 text-sm font-semibold ${RAG_TONE[status]}`}
    >
      {/* A dot as well as colour: never signal by colour alone. */}
      <span className="h-2 w-2 rounded-full bg-current" aria-hidden="true" />
      {status}
      {confidence !== undefined ? (
        <span className="font-normal tabular-nums opacity-75">
          {Math.round(confidence * 100)}% sure
        </span>
      ) : null}
    </span>
  );
}

/** The cited transcript lines, expandable. Source traceability is a "never cut". */
export function SourceQuote({
  lines,
  sourceLines,
  evidence,
}: {
  lines: TranscriptLine[];
  sourceLines: number[];
  evidence: string;
}) {
  const [open, setOpen] = useState(false);
  const cited = lines.filter((line) => sourceLines.includes(line.n));

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="text-xs font-semibold text-indigo"
      >
        {open ? "Hide source" : `Source · ${sourceLines.map((n) => `L${n}`).join(", ")}`}
      </button>
      {open ? (
        <div className="mt-2 rounded-lg border border-line bg-wash p-2.5">
          {cited.length ? (
            <ul className="space-y-1">
              {cited.map((line) => (
                <li key={line.n} className="flex gap-2 text-[0.8125rem] leading-relaxed">
                  <span className="shrink-0 tabular-nums text-ink-faint">L{line.n}</span>
                  <span>
                    {line.speaker ? (
                      <span className="font-medium">{line.speaker}: </span>
                    ) : null}
                    {line.text}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[0.8125rem] text-ink-soft">{evidence}</p>
          )}
        </div>
      ) : null}
    </div>
  );
}

export function ItemSummary({ item }: { item: ClassifiedItem }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Chip>{item.kind.label.replace(/_/g, " ")}</Chip>
      <Chip tone={SEVERITY_TONE[item.severity.label] ?? ""}>
        {item.severity.label}
        <span className="ml-1 font-normal tabular-nums opacity-70">
          {item.severity_value.toFixed(2)}
        </span>
      </Chip>
      <Chip
        tone={
          item.audience.label === "client_safe"
            ? "bg-rag-green-wash text-rag-green"
            : "bg-wash text-ink-soft"
        }
      >
        {item.audience.label === "client_safe" ? "Client" : "Internal"}
      </Chip>
    </div>
  );
}

export function OwnerLine({ item }: { item: ClassifiedItem }) {
  const owner = item.candidate.owner;
  const due = item.candidate.due_date;
  return (
    <p className="mt-2 text-xs text-ink-soft">
      <span className="font-medium">{owner ?? "No owner"}</span>
      <StatusTag status={item.owner_status} />
      {" · "}
      <span className="font-medium">{due ?? "No date"}</span>
      <StatusTag status={item.due_status} />
    </p>
  );
}

/** Stated / Inferred / Not specified — the Noul banding, made legible. */
function StatusTag({ status }: { status: ClassifiedItem["owner_status"] }) {
  const label =
    status === "stated" ? "stated" : status === "inferred" ? "inferred" : "not specified";
  const tone =
    status === "stated"
      ? "text-rag-green"
      : status === "inferred"
        ? "text-rag-amber"
        : "text-ink-faint";
  return <span className={`ml-1 text-[0.6875rem] ${tone}`}>({label})</span>;
}

export { ConfidenceBadge, Distribution };
