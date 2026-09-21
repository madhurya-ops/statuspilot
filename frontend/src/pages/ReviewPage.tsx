import { useMemo, useState } from "react";
import { Button, Screen } from "../components/Chrome";
import {
  Chip,
  ConfidenceBadge,
  Distribution,
  ItemSummary,
  OwnerLine,
  RagPill,
  SourceQuote,
} from "../components/Item";
import type { Action, SessionState } from "../state/session";
import type { ClassifiedItem, RagStatus } from "../types";

export function ReviewPage({
  state,
  dispatch,
  onBuild,
}: {
  state: SessionState;
  dispatch: React.Dispatch<Action>;
  onBuild: () => void;
}) {
  const queue = useMemo(
    () => (state.classified?.items ?? []).filter((i) => i.routing === "review"),
    [state.classified],
  );
  const handled = queue.filter((i) => state.decisions[i.candidate.id]).length;
  const rag = state.classified?.rag;
  const needsRagConfirm = rag ? rag.confidence < 0.5 : false;
  const ragDone = !needsRagConfirm || state.ragOverride !== null;
  const allHandled = handled === queue.length && ragDone;

  return (
    <Screen
      wide
      action={
        <div>
          <div className="flex gap-2">
            <Button full disabled={!allHandled} onClick={onBuild}>
              Build reports
            </Button>
            {!allHandled ? (
              <Button
                variant="secondary"
                onClick={() => {
                  dispatch({ type: "acceptRemaining" });
                  // "Accept all" means all of it. Leaving the status unconfirmed kept
                  // Build disabled at 9/9 with nothing explaining why.
                  if (needsRagConfirm && rag) dispatch({ type: "setRag", status: rag.status });
                }}
              >
                Accept all
              </Button>
            ) : null}
          </div>
          {/* A disabled button must say what it is waiting for. */}
          {!allHandled ? (
            <p className="mt-1.5 text-center text-[0.6875rem] text-ink-faint">
              {handled < queue.length
                ? `${queue.length - handled} item${queue.length - handled === 1 ? "" : "s"} still to review`
                : "Confirm the overall status below"}
            </p>
          ) : null}
        </div>
      }
    >
      <header className="flex items-baseline justify-between gap-3">
        <h1 className="text-lg font-semibold">
          {queue.length} item{queue.length === 1 ? "" : "s"} need your review
        </h1>
        <span className="shrink-0 text-sm tabular-nums text-ink-soft">
          {handled} / {queue.length}
        </span>
      </header>

      <p className="mt-1.5 text-[0.8125rem] leading-relaxed text-ink-soft">
        These are the ones Jev wasn't confident about. Everything else was accepted
        automatically.
      </p>

      <ul className="mt-4 space-y-3">
        {queue.map((item) => (
          <li key={item.candidate.id}>
            <ReviewCard
              item={item}
              lines={state.extracted?.lines ?? []}
              decision={state.decisions[item.candidate.id]?.status}
              onDecide={(status) =>
                dispatch({ type: "decide", id: item.candidate.id, decision: { status } })
              }
              onEdit={(edits) =>
                dispatch({
                  type: "decide",
                  id: item.candidate.id,
                  decision: { status: "accepted", edits },
                })
              }
            />
          </li>
        ))}
      </ul>

      {needsRagConfirm && rag ? (
        <RagConfirm
          status={state.ragOverride ?? rag.status}
          confidence={rag.confidence}
          reason={rag.reason}
          onChoose={(status) => dispatch({ type: "setRag", status })}
          chosen={state.ragOverride !== null}
        />
      ) : null}
    </Screen>
  );
}

function ReviewCard({
  item,
  lines,
  decision,
  onDecide,
  onEdit,
}: {
  item: ClassifiedItem;
  lines: SessionState["extracted"] extends null ? never : { n: number; speaker: string | null; text: string }[];
  decision?: "accepted" | "dropped";
  onDecide: (status: "accepted" | "dropped") => void;
  onEdit: (edits: Record<string, unknown>) => void;
}) {
  const [editing, setEditing] = useState(false);
  const settled = decision !== undefined;

  return (
    <div
      className={`rounded-xl border bg-paper p-3.5 transition-colors ${
        decision === "accepted"
          ? "border-rag-green/35"
          : decision === "dropped"
            ? "border-line opacity-55"
            : "border-line"
      }`}
    >
      <p className="text-[0.9375rem] font-medium leading-snug">{item.candidate.text}</p>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <ItemSummary item={item} />
        <ConfidenceBadge confidence={item.kind.confidence} />
      </div>

      <OwnerLine item={item} />
      <Distribution decision={item.kind} />
      <SourceQuote
        lines={lines}
        sourceLines={item.candidate.source_lines}
        evidence={item.candidate.evidence}
      />

      {editing ? (
        <EditPanel item={item} onSave={(edits) => { onEdit(edits); setEditing(false); }} onCancel={() => setEditing(false)} />
      ) : (
        <div className="mt-3 flex gap-2">
          <Button
            variant={decision === "accepted" ? "primary" : "secondary"}
            onClick={() => onDecide("accepted")}
          >
            {decision === "accepted" ? "Accepted" : "Accept"}
          </Button>
          <Button variant="secondary" onClick={() => setEditing(true)}>
            Change
          </Button>
          <Button variant="danger" onClick={() => onDecide("dropped")}>
            {decision === "dropped" ? "Dropped" : "Drop"}
          </Button>
        </div>
      )}

      {settled && !editing ? (
        <p className="mt-2 text-[0.6875rem] text-ink-faint">
          {decision === "accepted" ? "Included in your reports." : "Left out of your reports."}
        </p>
      ) : null}
    </div>
  );
}

const KINDS = ["action_item", "risk", "assumption", "issue", "dependency", "decision"];
const SEVERITIES = ["Low", "Medium", "High"];

function EditPanel({
  item,
  onSave,
  onCancel,
}: {
  item: ClassifiedItem;
  onSave: (edits: Record<string, unknown>) => void;
  onCancel: () => void;
}) {
  const [kind, setKind] = useState(item.kind.label);
  const [severity, setSeverity] = useState(item.severity.label);
  const [audience, setAudience] = useState(item.audience.label);
  const [owner, setOwner] = useState(item.candidate.owner ?? "");
  const [due, setDue] = useState(item.candidate.due_date ?? "");

  return (
    <div className="mt-3 rounded-lg border border-line bg-wash p-3">
      <Select label="Type" value={kind} options={KINDS} onChange={setKind} />
      <Select label="Severity" value={severity} options={SEVERITIES} onChange={setSeverity} />
      <Select
        label="Audience"
        value={audience}
        options={["client_safe", "internal_only"]}
        onChange={setAudience}
      />
      <Text label="Owner" value={owner} onChange={setOwner} placeholder="Not assigned" />
      <Text label="Due date" value={due} onChange={setDue} placeholder="No date" />
      <div className="mt-3 flex gap-2">
        <Button
          onClick={() =>
            onSave({
              kind,
              severity,
              audience,
              owner: owner.trim() || null,
              due_date: due.trim() || null,
              // An edited value is the PM's own statement, not a model inference.
              owner_status: owner.trim() ? "stated" : "not_specified",
              due_status: due.trim() ? "stated" : "not_specified",
            })
          }
        >
          Save changes
        </Button>
        <Button variant="quiet" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  const id = `${label}-${value}`;
  return (
    <div className="mb-2.5">
      <label htmlFor={id} className="block text-xs font-medium text-ink-soft">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 min-h-[2.5rem] w-full rounded-lg border border-line bg-paper px-2 text-sm"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option.replace(/_/g, " ")}
          </option>
        ))}
      </select>
    </div>
  );
}

function Text({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  const id = `${label}-input`;
  return (
    <div className="mb-2.5">
      <label htmlFor={id} className="block text-xs font-medium text-ink-soft">
        {label}
      </label>
      <input
        id={id}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 min-h-[2.5rem] w-full rounded-lg border border-line bg-paper px-2 text-sm"
      />
    </div>
  );
}

function RagConfirm({
  status,
  confidence,
  reason,
  onChoose,
  chosen,
}: {
  status: RagStatus;
  confidence: number;
  reason: string;
  onChoose: (status: RagStatus) => void;
  chosen: boolean;
}) {
  return (
    <div className="mt-4 rounded-xl border border-indigo/30 bg-indigo-wash p-3.5">
      <h2 className="text-sm font-semibold">Confirm the overall status</h2>
      <p className="mt-1 text-[0.8125rem] leading-relaxed text-ink-soft">
        Jev suggested <strong>{status}</strong> but wasn't confident ({Math.round(confidence * 100)}%
        sure). {reason}
      </p>
      <div className="mt-3 flex gap-2">
        {(["Red", "Amber", "Green"] as const).map((option) => (
          <button
            key={option}
            onClick={() => onChoose(option)}
            className={`flex-1 rounded-lg border px-2 py-2 text-sm font-semibold ${
              status === option && chosen ? "border-indigo bg-paper" : "border-line bg-paper/60"
            }`}
          >
            <RagPill status={option} />
          </button>
        ))}
      </div>
    </div>
  );
}
