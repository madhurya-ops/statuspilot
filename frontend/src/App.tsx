import { useCallback, useEffect, useState } from "react";
import { getAccessCode } from "./api/client";
import { Toast } from "./components/Chrome";
import { AccessGate } from "./pages/AccessGate";
import { InputPage } from "./pages/InputPage";
import { ProcessingPage } from "./pages/ProcessingPage";
import { runPipeline } from "./state/run";
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
      {state.screen === "review" || state.screen === "results" ? (
        <ProcessingPage state={state} />
      ) : null}
      {state.error ? (
        <Toast message={state.error} onDismiss={() => dispatch({ type: "error", message: null })} />
      ) : null}
    </>
  );
}
