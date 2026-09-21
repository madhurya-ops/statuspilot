import type {
  BudgetStatus,
  ClassifyResponse,
  Documents,
  ExtractResponse,
  MeetingMeta,
  RagResult,
  SampleDetail,
  SampleSummary,
  ApprovedItem,
} from "../types";

const BASE = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const TIMEOUT_MS = 60_000;
const CODE_KEY = "statuspilot.accessCode";

export function getAccessCode(): string {
  try {
    return sessionStorage.getItem(CODE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setAccessCode(code: string): void {
  try {
    sessionStorage.setItem(CODE_KEY, code);
  } catch {
    /* private browsing — the code simply won't persist across reloads */
  }
}

export function clearAccessCode(): void {
  try {
    sessionStorage.removeItem(CODE_KEY);
  } catch {
    /* ignore */
  }
}

/** A failure the UI can act on, rather than a stack trace. */
export class ApiError extends Error {
  readonly status: number;
  /** Seconds to wait, when the server said so. */
  readonly retryAfter?: number;

  constructor(message: string, status: number, retryAfter?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryAfter = retryAfter;
  }

  get isAuth() {
    return this.status === 401;
  }
  get isRateLimit() {
    return this.status === 429;
  }
  /** A daily exhaustion, not a "wait a moment" — the two need different words. */
  get isDailyLimit() {
    return this.status === 429 && /daily/i.test(this.message);
  }
  get isTooLarge() {
    return this.status === 413;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        "X-Access-Code": getAccessCode(),
        ...(init.headers ?? {}),
      },
    });
  } catch (err) {
    clearTimeout(timer);
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("That took too long. Check your connection and try again.", 0);
    }
    throw new ApiError("Could not reach StatusPilot. Check your connection.", 0);
  }
  clearTimeout(timer);

  if (!response.ok) {
    let detail = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* keep the generic message */
    }
    const retry = Number(response.headers.get("Retry-After"));
    throw new ApiError(detail, response.status, Number.isFinite(retry) ? retry : undefined);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string; version: string; groq_model: string }>("/api/health"),

  samples: () => request<SampleSummary[]>("/api/samples"),
  sample: (id: string) => request<SampleDetail>(`/api/samples/${encodeURIComponent(id)}`),

  parse: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ text: string; chars: number; truncated: boolean }>("/api/parse", {
      method: "POST",
      body: form,
    });
  },

  extract: (text: string) =>
    request<ExtractResponse>("/api/extract", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  classify: (extracted: ExtractResponse, projectName?: string) =>
    request<ClassifyResponse>("/api/classify", {
      method: "POST",
      body: JSON.stringify({ extracted, project_name: projectName ?? null }),
    }),

  generate: (payload: {
    meta: MeetingMeta;
    discussion_points: string[];
    items: ApprovedItem[];
    rag: RagResult;
    project_name?: string | null;
    reporting_period?: string | null;
  }) =>
    request<Documents>("/api/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  /** Does this exact text match a bundled sample with a precomputed run? */
  cachedLookup: (text: string) =>
    request<{ cached: boolean; sample_id: string | null }>("/api/cached/lookup", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  cachedRun: (sampleId: string) =>
    request<{
      cached: true;
      sample_id: string;
      extract: ExtractResponse;
      classify: ClassifyResponse;
      documents: Documents;
    }>(`/api/cached/${encodeURIComponent(sampleId)}`),

  budget: (needed = 4000) => request<BudgetStatus>(`/api/budget?needed=${needed}`),

  /** Returns the file itself plus the server's filename, for a download or a share. */
  exportFile: async (
    fmt: "docx" | "xlsx" | "pdf",
    documents: Documents,
    projectName: string | null,
    rag: string,
  ): Promise<{ blob: Blob; filename: string }> => {
    const response = await fetch(`${BASE}/api/export/${fmt}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Access-Code": getAccessCode() },
      body: JSON.stringify({ documents, project_name: projectName, rag }),
    });
    if (!response.ok) {
      let detail = `That ${fmt.toUpperCase()} could not be produced.`;
      try {
        const body = await response.json();
        if (typeof body?.detail === "string") detail = body.detail;
      } catch {
        /* keep the generic message */
      }
      throw new ApiError(detail, response.status);
    }
    const disposition = response.headers.get("Content-Disposition") ?? "";
    const match = /filename="([^"]+)"/.exec(disposition);
    return {
      blob: await response.blob(),
      filename: match?.[1] ?? `StatusReport.${fmt}`,
    };
  },
};
