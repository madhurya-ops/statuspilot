import type { ReactNode } from "react";

/** The page shell: one column, thumb-reachable, with room for a sticky action bar. */
/**
 * The page shell.
 *
 * Two things this has to get right, both found by looking at a 1440px window rather
 * than trusting the CSS:
 *
 *  1. The action bar is **full-bleed**, with only its contents constrained. Putting
 *     the bar inside the centred column left a visible seam down the side of it on a
 *     wide viewport, because the bar's own background stopped at the column edge.
 *  2. The outer column is `min-h-dvh` with `flex-1` content, so the bar is pushed to
 *     the bottom of the *viewport* when a page is short. `sticky bottom-0` alone only
 *     sticks once the page scrolls, which is why it floated mid-page with empty space
 *     beneath it.
 *
 * `dvh` rather than `vh` so iOS Safari's collapsing address bar does not leave the
 * action bar off-screen.
 */
export function Screen({
  children,
  action,
  wide,
}: {
  children: ReactNode;
  action?: ReactNode;
  /** Results and review pages earn more room on a laptop. */
  wide?: boolean;
}) {
  const column = wide ? "max-w-[56rem]" : "max-w-[34rem]";
  return (
    <div className="flex min-h-dvh flex-col">
      <div className={`mx-auto w-full flex-1 px-4 pb-8 pt-5 sm:px-6 ${column}`}>
        {children}
      </div>
      {action ? (
        <div className="sticky bottom-0 border-t border-line bg-paper/95 backdrop-blur">
          <div
            className={`mx-auto w-full px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-6 ${column}`}
          >
            {action}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function Button({
  children,
  onClick,
  variant = "primary",
  disabled,
  type = "button",
  full,
  grow,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "quiet" | "danger";
  disabled?: boolean;
  type?: "button" | "submit";
  /** Occupies the whole line. Use alone, never beside another button. */
  full?: boolean;
  /** Takes the remaining space in a row, leaving siblings at their natural width. */
  grow?: boolean;
}) {
  // whitespace-nowrap: a wrapped label turns a 44px target into a ragged two-line
  // block, which is what made "Start over" and "Accept all" look broken at 375px.
  const base =
    "inline-flex min-h-[2.75rem] shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-4 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-45";
  const tones = {
    primary: "bg-indigo text-white hover:bg-indigo-deep",
    secondary: "border border-line bg-paper text-ink hover:bg-wash",
    quiet: "text-ink-soft hover:text-ink",
    danger: "border border-line bg-paper text-rag-red hover:bg-rag-red-wash",
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${base} ${tones[variant]} ${full ? "w-full" : ""} ${grow ? "min-w-0 flex-1" : ""}`}
    >
      {children}
    </button>
  );
}

export function Banner() {
  return (
    <p className="mb-4 rounded-lg bg-indigo-wash px-3 py-2 text-xs leading-relaxed text-indigo-deep">
      Demo uses synthetic data. Don't paste confidential client information.
    </p>
  );
}

export function Toast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  return (
    <div
      role="alert"
      className="fixed inset-x-3 bottom-20 z-50 mx-auto max-w-[32rem] rounded-lg border border-rag-red/25 bg-rag-red-wash px-4 py-3 text-sm text-rag-red shadow-lg"
    >
      <div className="flex items-start gap-3">
        <span className="flex-1 leading-relaxed">{message}</span>
        <button onClick={onDismiss} className="font-semibold" aria-label="Dismiss">
          Close
        </button>
      </div>
    </div>
  );
}

/** Says out loud that a run came from the committed cache. Never hidden. */
export function CachedTag() {
  return (
    <span className="inline-flex items-center rounded-full border border-line bg-wash px-2 py-0.5 text-[0.6875rem] font-semibold text-ink-soft">
      Cached sample run
    </span>
  );
}
