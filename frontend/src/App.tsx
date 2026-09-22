import { useCallback, useEffect, useState } from "react";
import { getAccessCode } from "./api/client";
import { Toast } from "./components/Chrome";
import { AccessGate } from "./pages/AccessGate";
import { HowItWorks } from "./pages/HowItWorks";
import { InputPage } from "./pages/InputPage";
import { ProcessingPage } from "./pages/ProcessingPage";
import { ResultsPage } from "./pages/ResultsPage";
import { ReviewPage } from "./pages/ReviewPage";
import { buildDocuments, runPipeline } from "./state/run";
import { useSession } from "./state/session";

export default function App() {
  const [state, dispatch] = useSession();
  const [unlocked, setUnlocked] = useState(() => Boolean(getAccessCode()));

  const run = useCallback(
    (text: string) => {
      void runPipeline(text, dispatch, state.projectName || undefined);
    },
    [dispatch, state.projectName],
  );

  // Guard against a double submit from an impatient tap.
  useEffect(() => {
    if (!state.busy) return;
    const timer = setTimeout(() => dispatch({ type: "busy", busy: false }), 90_000);
    return () => clearTimeout(timer);
  }, [state.busy, dispatch]);

  if (!unlocked) {
    return <AccessGate onUnlocked={() => setUnlocked(true)} />;
  }

  return (
    <>
      {state.screen === "input" ? (
        <InputPage state={state} dispatch={dispatch} onRun={run} />
      ) : null}
      {state.screen === "processing" ? <ProcessingPage state={state} /> : null}
      {state.screen === "review" ? (
        <ReviewPage
          state={state}
          dispatch={dispatch}
          onBuild={() => void buildDocuments(state, dispatch)}
        />
      ) : null}
      {state.screen === "results" ? <ResultsPage state={state} dispatch={dispatch} /> : null}
      {state.screen === "how" ? <HowItWorks dispatch={dispatch} /> : null}
      {state.error ? (
        <Toast
          message={state.error}
          onDismiss={() => dispatch({ type: "error", message: null })}
          onRetry={
            state.errorRetryable && state.text
              ? () => {
                  dispatch({ type: "error", message: null });
                  run(state.text);
                }
              : undefined
          }
        />
      ) : null}
    </>
  );
}
