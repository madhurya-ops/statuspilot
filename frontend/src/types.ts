// Mirrors backend/app/models.py (Section 7 of execution.md).

export type OwnerStatus = "stated" | "inferred" | "not_specified";
export type Routing = "auto" | "suggested" | "review";
export type Engine = "jev" | "llm" | "mock";
export type RagStatus = "Red" | "Amber" | "Green";

export interface TranscriptLine {
  n: number;
  speaker: string | null;
  text: string;
}

export interface Candidate {
  id: string;
  text: string;
  kind_hint: string;
  owner: string | null;
  due_date: string | null;
  source_lines: number[];
  evidence: string;
}

export interface Decision {
  label: string;
  /** null for Noul answers: Jev returns no confidence for that type. */
  confidence: number | null;
  probabilities: Record<string, number> | null;
  /** Raw Score float; null for choice and noul. */
  value: number | null;
}

export interface ClassifiedItem {
  candidate: Candidate;
  kind: Decision;
  severity: Decision;
  audience: Decision;
  /** Raw Score float — the sort key. Two items can both band "High" at 1.52 and 2.0. */
  severity_value: number;
  owner_explicit: number;
  due_explicit: number;
  owner_status: OwnerStatus;
  due_status: OwnerStatus;
  routing: Routing;
  engine: Engine;
}

export interface RagResult {
  status: RagStatus;
  confidence: number;
  dimensions: Record<string, Decision>;
  reason: string;
}

export interface MeetingMeta {
  title: string;
  date: string | null;
  attendees: string[];
  agenda: string[];
}

export interface ExtractResponse {
  meta: MeetingMeta;
  discussion_points: string[];
  candidates: Candidate[];
  lines: TranscriptLine[];
}

export interface RunStats {
  engine: string;
  requests: number;
  latency_ms: number;
  input_tokens: number | null;
  output_tokens: number | null;
}

export interface ClassifyResponse {
  items: ClassifiedItem[];
  rag: RagResult;
  stats: RunStats;
  dropped: ClassifiedItem[];
}

export interface ApprovedItem {
  id: string;
  text: string;
  kind: string;
  severity: string;
  severity_value: number;
  audience: string;
  owner: string | null;
  owner_status: OwnerStatus;
  due_date: string | null;
  due_status: OwnerStatus;
  source_lines: number[];
  edited_by_user: boolean;
}

export interface Documents {
  mom_markdown: string;
  status_report_markdown: string;
  action_items: ApprovedItem[];
  raid_log: Record<string, ApprovedItem[]>;
  /** True when nothing is client-facing. The UI must explain, never show a blank. */
  status_report_empty: boolean;
  cached: boolean;
  leak_stripped: boolean;
}

export interface SampleSummary {
  id: string;
  title: string;
  description: string;
  chars: number;
}

export interface SampleDetail extends SampleSummary {
  text: string;
}

export interface BudgetStatus {
  limit_tokens: number;
  remaining_tokens: number;
  refill_per_second: number;
  wait_seconds: number;
  needed_tokens: number;
  known: boolean;
}
