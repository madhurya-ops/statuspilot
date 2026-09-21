import type { ReactNode } from "react";

/** The page shell: one column, thumb-reachable, with room for a sticky action bar. */
export function Screen({
  children,
  action,
}: {
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="mx-auto flex min-h-full w-full max-w-[34rem] flex-col">
      <div className="flex-1 px-4 pb-6 pt-5">{children}</div>
      {action ? (
        <div className="sticky bottom-0 border-t border-line bg-paper/95 px-4 py-3 backdrop-blur">
          {action}
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
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "quiet" | "danger";
  disabled?: boolean;
  type?: "button" | "submit";
  full?: boolean;
}) {
  const base =
    "inline-flex min-h-[2.75rem] items-center justify-center gap-2 rounded-lg px-4 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-45";
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
      className={`${base} ${tones[variant]} ${full ? "w-full" : ""}`}
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
