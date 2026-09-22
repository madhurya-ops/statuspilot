import { useReducer } from "react";
import type {
  ApprovedItem,
  ClassifiedItem,
  ClassifyResponse,
  Documents,
  ExtractResponse,
  SampleSummary,
} from "../types";

export type Screen = "input" | "processing" | "review" | "results" | "how";

export type StepId = "reading" | "extracting" | "judging" | "ready";
export interface Step {
  id: StepId;
  label: string;
  state: "pending" | "active" | "waiting" | "done";
  ms?: number;
  /** Set when the step is paused on the free-tier token budget. */
  waitReason?: string;
  waitSeconds?: number;
}

export const INITIAL_STEPS: Step[] = [
  { id: "reading", label: "Reading transcript", state: "pending" },
  { id: "extracting", label: "Extracting items", state: "pending" },
  { id: "judging", label: "Judging with Jev", state: "pending" },
  { id: "ready", label: "Ready for review", state: "pending" },
];

/** A reviewed item: the PM's verdict plus any edits. */
export interface ReviewDecision {
  status: "accepted" | "dropped";
  edits?: Partial<ApprovedItem>;
}

export interface SessionState {
  screen: Screen;
  text: string;
  projectName: string;
  reportingPeriod: string;
  samples: SampleSummary[];
  /** Set when this run is served from the committed cache, never hidden from the UI. */
  cached: boolean;
  steps: Step[];
  extracted: ExtractResponse | null;
  classified: ClassifyResponse | null;
  decisions: Record<string, ReviewDecision>;
  ragOverride: ClassifyResponse["rag"]["status"] | null;
  documents: Documents | null;
  error: string | null;
  /** Set when the last failure is worth retrying (rate limit, timeout, provider). */
  errorRetryable: boolean;
  busy: boolean;
}

export const initialState: SessionState = {
  screen: "input",
  text: "",
  projectName: "",
  reportingPeriod: "",
  samples: [],
  cached: false,
  steps: INITIAL_STEPS,
  extracted: null,
  classified: null,
  decisions: {},
  ragOverride: null,
  documents: null,
  error: null,
  errorRetryable: false,
  busy: false,
};

export type Action =
  | { type: "setText"; text: string }
  | { type: "setField"; field: "projectName" | "reportingPeriod"; value: string }
  | { type: "setSamples"; samples: SampleSummary[] }
  | { type: "startRun"; cached: boolean }
  | { type: "step"; id: StepId; state: Step["state"]; ms?: number; waitReason?: string; waitSeconds?: number }
  | { type: "extracted"; extracted: ExtractResponse }
  | { type: "classified"; classified: ClassifyResponse }
  | { type: "decide"; id: string; decision: ReviewDecision }
  | { type: "acceptRemaining" }
  | { type: "setRag"; status: ClassifyResponse["rag"]["status"] }
  | { type: "documents"; documents: Documents }
  | { type: "go"; screen: Screen }
  | { type: "error"; message: string | null; retryable?: boolean }
  | { type: "busy"; busy: boolean }
  | { type: "reset" };

export function reducer(state: SessionState, action: Action): SessionState {
  switch (action.type) {
    case "setText":
      return { ...state, text: action.text, error: null };
    case "setField":
      return { ...state, [action.field]: action.value };
    case "setSamples":
      return { ...state, samples: action.samples };
    case "startRun":
      return {
        ...state,
        screen: "processing",
        cached: action.cached,
        steps: INITIAL_STEPS.map((s) => ({ ...s })),
        extracted: null,
        classified: null,
        decisions: {},
        ragOverride: null,
        documents: null,
        error: null,
        busy: true,
      };
    case "step":
      return {
        ...state,
        steps: state.steps.map((s) =>
          s.id === action.id
            ? {
                ...s,
                state: action.state,
                ms: action.ms ?? s.ms,
                waitReason: action.waitReason,
                waitSeconds: action.waitSeconds,
              }
            : s,
        ),
      };
    case "extracted":
      return { ...state, extracted: action.extracted };
    case "classified":
      return { ...state, classified: action.classified };
    case "decide":
      return { ...state, decisions: { ...state.decisions, [action.id]: action.decision } };
    case "acceptRemaining": {
      const next = { ...state.decisions };
      for (const item of state.classified?.items ?? []) {
        if (!next[item.candidate.id]) next[item.candidate.id] = { status: "accepted" };
      }
      return { ...state, decisions: next };
    }
    case "setRag":
      return { ...state, ragOverride: action.status };
    case "documents":
      return { ...state, documents: action.documents, busy: false };
    case "go":
      return { ...state, screen: action.screen, error: null };
    case "error":
      return {
        ...state,
        error: action.message,
        errorRetryable: action.retryable ?? false,
        busy: false,
      };
    case "busy":
      return { ...state, busy: action.busy };
    case "reset":
      return { ...initialState, samples: state.samples };
    default:
      return state;
  }
}

export function useSession() {
  return useReducer(reducer, initialState);
}

/** Items the PM must look at, in transcript order. */
export function reviewQueue(classified: ClassifyResponse | null): ClassifiedItem[] {
  return (classified?.items ?? []).filter((i) => i.routing === "review");
}

/** Build the payload for /api/generate from the reviewed state. */
export function approvedItems(
  classified: ClassifyResponse | null,
  decisions: Record<string, ReviewDecision>,
): ApprovedItem[] {
  const out: ApprovedItem[] = [];
  for (const item of classified?.items ?? []) {
    const decision = decisions[item.candidate.id];
    // Anything not explicitly dropped is included: `auto` and `suggested` items are
    // pre-accepted by design, and only `review` items require a tap.
    if (decision?.status === "dropped") continue;
    const edits = decision?.edits ?? {};
    out.push({
      id: item.candidate.id,
      text: edits.text ?? item.candidate.text,
      kind: edits.kind ?? item.kind.label,
      severity: edits.severity ?? item.severity.label,
      severity_value: item.severity_value,
      audience: edits.audience ?? item.audience.label,
      owner: edits.owner !== undefined ? edits.owner : item.candidate.owner,
      owner_status: edits.owner_status ?? item.owner_status,
      due_date: edits.due_date !== undefined ? edits.due_date : item.candidate.due_date,
      due_status: edits.due_status ?? item.due_status,
      source_lines: item.candidate.source_lines,
      edited_by_user: Object.keys(edits).length > 0,
    });
  }
  return out;
}
