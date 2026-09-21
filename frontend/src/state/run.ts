import { api, ApiError } from "../api/client";
import { approvedItems, type Action, type SessionState } from "./session";

/** A full run: cached samples return instantly; everything else goes live. */
export async function runPipeline(
  text: string,
  dispatch: React.Dispatch<Action>,
  projectName?: string,
): Promise<void> {
  const cached = await checkCache(text);
  dispatch({ type: "startRun", cached: cached !== null });

  try {
    if (cached !== null) {
      await runCached(cached, dispatch);
      return;
    }
    await runLive(text, dispatch, projectName);
  } catch (err) {
    const message =
      err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
    dispatch({ type: "error", message });
    dispatch({ type: "go", screen: "input" });
  }
}

async function checkCache(text: string): Promise<string | null> {
  try {
    const result = await api.cachedLookup(text);
    return result.cached ? result.sample_id : null;
  } catch {
    // A cache miss must never block a live run.
    return null;
  }
}

async function runCached(sampleId: string, dispatch: React.Dispatch<Action>) {
  const started = performance.now();
  const run = await api.cachedRun(sampleId);
  const ms = Math.round(performance.now() - started);

  for (const id of ["reading", "extracting", "judging"] as const) {
    dispatch({ type: "step", id, state: "done", ms: Math.round(ms / 3) });
  }
  dispatch({ type: "extracted", extracted: run.extract });
  dispatch({ type: "classified", classified: run.classify });
  dispatch({ type: "documents", documents: run.documents });
  dispatch({ type: "step", id: "ready", state: "done" });
  dispatch({ type: "go", screen: nextScreen(run.classify.items) });
}

async function runLive(
  text: string,
  dispatch: React.Dispatch<Action>,
  projectName?: string,
) {
  dispatch({ type: "step", id: "reading", state: "done", ms: 0 });

  dispatch({ type: "step", id: "extracting", state: "active" });
  let started = performance.now();
  const extracted = await api.extract(text);
  dispatch({
    type: "step",
    id: "extracting",
    state: "done",
    ms: Math.round(performance.now() - started),
  });
  dispatch({ type: "extracted", extracted });

  dispatch({ type: "step", id: "judging", state: "active" });
  started = performance.now();
  const classified = await api.classify(extracted, projectName);
  dispatch({
    type: "step",
    id: "judging",
    state: "done",
    ms: Math.round(performance.now() - started),
  });
  dispatch({ type: "classified", classified });

  dispatch({ type: "step", id: "ready", state: "done" });
  dispatch({ type: "busy", busy: false });
  dispatch({ type: "go", screen: nextScreen(classified.items) });
}

/** Skip the review queue when Jev was confident about everything. */
function nextScreen(items: { routing: string }[]) {
  return items.some((i) => i.routing === "review") ? "review" : "results";
}

/**
 * Wait for the free-tier token budget, reporting the countdown as it goes.
 *
 * Measured: extraction *requests* ~7,000 of the 8,000/minute budget, so generation
 * has to wait for the bucket to refill. Showing the reason and a countdown turns an
 * unexplained pause into a statement about cost.
 */
export async function waitForBudget(
  needed: number,
  onTick: (seconds: number) => void,
): Promise<void> {
  let status;
  try {
    status = await api.budget(needed);
  } catch {
    return;
  }
  if (!status.known || status.wait_seconds <= 1) return;

  let remaining = Math.ceil(status.wait_seconds);
  while (remaining > 0) {
    onTick(remaining);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    remaining -= 1;
  }
}

/** Review complete → generate the documents. Cached runs already have them. */
export async function buildDocuments(
  state: SessionState,
  dispatch: React.Dispatch<Action>,
): Promise<void> {
  if (state.documents) {
    dispatch({ type: "go", screen: "results" });
    return;
  }
  dispatch({ type: "busy", busy: true });
  try {
    const rag = state.ragOverride
      ? { ...state.classified!.rag, status: state.ragOverride }
      : state.classified!.rag;
    const documents = await api.generate({
      meta: state.extracted!.meta,
      discussion_points: state.extracted!.discussion_points,
      items: approvedItems(state.classified, state.decisions),
      rag,
      project_name: state.projectName || null,
      reporting_period: state.reportingPeriod || null,
    });
    dispatch({ type: "documents", documents });
    dispatch({ type: "go", screen: "results" });
  } catch (err) {
    const message =
      err instanceof ApiError ? err.message : "Couldn't build the reports. Try again.";
    dispatch({ type: "error", message });
  }
}
