import { useEffect, useRef } from "react";
import type { Action, Screen } from "./session";

/**
 * Make browser Back — and therefore the iOS edge-swipe — move between steps.
 *
 * The flow is reducer state inside one page, so without this a swipe-back leaves the
 * app entirely and the whole run is lost. On a phone, mid-demo, that is one stray
 * gesture away.
 *
 * Navigation only ever changes which screen is shown. It never re-runs the pipeline,
 * so going back from Results to Review costs nothing and preserves every accept,
 * edit and drop the user has made.
 */
export function useScreenHistory(screen: Screen, dispatch: React.Dispatch<Action>) {
  // Set while we are applying a popstate, so the sync effect below does not push a
  // new entry for a move the browser just made — that would fight the back button.
  const fromPopstate = useRef(false);
  const lastPushed = useRef<Screen | null>(null);

  useEffect(() => {
    if (lastPushed.current === null) {
      // Seed the stack so the first Back has somewhere to land.
      window.history.replaceState({ screen: "input" }, "");
      lastPushed.current = "input";
      return;
    }
    if (fromPopstate.current) {
      fromPopstate.current = false;
      lastPushed.current = screen;
      return;
    }
    if (screen !== lastPushed.current) {
      window.history.pushState({ screen }, "");
      lastPushed.current = screen;
    }
  }, [screen]);

  useEffect(() => {
    function onPopState(event: PopStateEvent) {
      let target = (event.state?.screen as Screen | undefined) ?? "input";
      // `processing` is transient: going "back" to a finished progress stepper is a
      // dead end with no way forward. Treat it as transparent, so Back from the
      // review queue reaches the sample list rather than stranding the user on a
      // completed run.
      if (target === "processing") target = "input";
      fromPopstate.current = true;
      dispatch({ type: "go", screen: target });
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [dispatch]);
}
