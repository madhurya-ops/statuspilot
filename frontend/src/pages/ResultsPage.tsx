import { useState } from "react";
import { Button, CachedTag, Screen } from "../components/Chrome";
import { Chip, RagPill, SourceQuote } from "../components/Item";
import { ExportSheet } from "../components/ExportSheet";
import { Markdown } from "../components/Markdown";
import type { Action, SessionState } from "../state/session";
import type { ApprovedItem } from "../types";

type Tab = "status" | "mom" | "actions" | "raid";

const TABS: { id: Tab; label: string }[] = [
  { id: "status", label: "Status report" },
  { id: "mom", label: "Minutes" },
  { id: "actions", label: "Action items" },
  { id: "raid", label: "RAID log" },
];

export function ResultsPage({
  state,
  dispatch,
  onBack,
}: {
  state: SessionState;
  dispatch: React.Dispatch<Action>;
  onBack?: () => void;
}) {
  const [tab, setTab] = useState<Tab>("status");
  const [showInternal, setShowInternal] = useState(false);
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState(false);
  const docs = state.documents;
  const rag = state.ragOverride ?? state.classified?.rag.status ?? "Amber";

  if (!docs) return null;

  const visible = (items: ApprovedItem[]) =>
    showInternal ? items : items.filter((i) => i.audience === "client_safe");

  async function copyReport() {
    try {
      await navigator.clipboard.writeText(docs!.status_report_markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      dispatch({ type: "error", message: "Couldn't copy. Select the text and copy it manually." });
    }
  }

  return (
    <Screen
      wide
      onBack={onBack}
      backLabel="Back to review"
      action={
        <div className="flex gap-2">
          <Button grow onClick={copyReport}>
            {copied ? "Copied" : "Copy report"}
          </Button>
          <Button variant="secondary" onClick={() => setExporting(true)}>
            Export
          </Button>
        </div>
      }
    >
      <header className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <RagPill status={rag} confidence={state.classified?.rag.confidence} />
        <div className="flex items-center gap-2">
          {docs.cached ? <CachedTag /> : null}
          <button
            onClick={() => dispatch({ type: "go", screen: "how" })}
            className="text-xs font-semibold text-indigo"
          >
            How it works
          </button>
          <button
            onClick={() => dispatch({ type: "reset" })}
            className="text-xs font-semibold text-ink-soft"
          >
            Start over
          </button>
        </div>
      </header>

      {state.classified?.rag.reason ? (
        <p className="mt-2 text-[0.8125rem] leading-relaxed text-ink-soft">
          {state.classified.rag.reason}
        </p>
      ) : null}

      <div
        role="tablist"
        className="mt-4 flex gap-1 overflow-x-auto border-b border-line pb-px"
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`shrink-0 border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              tab === t.id
                ? "border-indigo text-ink"
                : "border-transparent text-ink-soft hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab !== "status" && tab !== "mom" ? (
        <label className="mt-3 flex items-center gap-2 text-xs text-ink-soft">
          <input
            type="checkbox"
            checked={showInternal}
            onChange={(e) => setShowInternal(e.target.checked)}
            className="h-4 w-4"
          />
          Show internal-only items
        </label>
      ) : null}

      <div className="mt-4">
        {tab === "status" ? (
          <>
            {docs.leak_stripped ? (
              <p className="mb-3 rounded-lg bg-rag-amber-wash px-3 py-2 text-xs leading-relaxed text-rag-amber">
                A sentence echoing an internal-only item was removed from this report.
                Check it reads cleanly before sending.
              </p>
            ) : null}
            <Markdown source={docs.status_report_markdown} />
          </>
        ) : null}

        {tab === "mom" ? <Markdown source={docs.mom_markdown} /> : null}

        {tab === "actions" ? (
          <ItemTable items={visible(docs.action_items)} lines={state.extracted?.lines ?? []} />
        ) : null}

        {tab === "raid" ? (
          <div className="space-y-4">
            {Object.entries(docs.raid_log).map(([section, items]) => (
              <section key={section}>
                <h2 className="text-sm font-semibold">
                  {section}{" "}
                  <span className="font-normal tabular-nums text-ink-faint">
                    {visible(items).length}
                  </span>
                </h2>
                <div className="mt-2">
                  <ItemTable items={visible(items)} lines={state.extracted?.lines ?? []} />
                </div>
              </section>
            ))}
          </div>
        ) : null}
      </div>

      {exporting ? (
        <ExportSheet
          documents={docs}
          projectName={state.projectName || null}
          rag={rag}
          onClose={() => setExporting(false)}
          onError={(message) => {
            setExporting(false);
            dispatch({ type: "error", message });
          }}
        />
      ) : null}
    </Screen>
  );
}

const SEVERITY_TONE: Record<string, string> = {
  High: "bg-rag-red-wash text-rag-red",
  Medium: "bg-rag-amber-wash text-rag-amber",
  Low: "bg-wash text-ink-soft",
};

/** Cards on a phone, a table on a laptop — the same data, laid out for the device. */
function ItemTable({
  items,
  lines,
}: {
  items: ApprovedItem[];
  lines: { n: number; speaker: string | null; text: string }[];
}) {
  if (!items.length) {
    return (
      <p className="rounded-lg border border-dashed border-line px-3 py-4 text-center text-sm text-ink-soft">
        Nothing here. Try the internal-only toggle.
      </p>
    );
  }
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.id} className="rounded-xl border border-line bg-paper p-3">
          <div className="flex items-start justify-between gap-3">
            <p className="text-[0.9375rem] font-medium leading-snug">{item.text}</p>
            <Chip tone={SEVERITY_TONE[item.severity] ?? ""}>{item.severity}</Chip>
          </div>
          <p className="mt-1.5 text-xs text-ink-soft">
            {item.owner ?? "Not assigned"}
            <Tag status={item.owner_status} />
            {" · "}
            {item.due_date ?? "No date"}
            <Tag status={item.due_status} />
            {item.audience !== "client_safe" ? (
              <>
                {" · "}
                <span className="text-ink-faint">internal only</span>
              </>
            ) : null}
          </p>
          <SourceQuote lines={lines} sourceLines={item.source_lines} evidence={item.text} />
        </li>
      ))}
    </ul>
  );
}

function Tag({ status }: { status: ApprovedItem["owner_status"] }) {
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
