import { useState } from "react";
import { api, setAccessCode } from "../api/client";
import { Button } from "../components/Chrome";

/** One field, one button. Not an auth system — a shared code so a public URL
 *  cannot be used as a free LLM proxy. */
export function AccessGate({ onUnlocked }: { onUnlocked: () => void }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!code.trim() || busy) return;
    setBusy(true);
    setError(null);
    setAccessCode(code.trim());
    try {
      await api.samples();
      onUnlocked();
    } catch {
      setError("That code wasn't recognised. Check it and try again.");
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-full w-full max-w-[26rem] flex-col justify-center px-5 py-10">
      <h1 className="text-[1.75rem] font-semibold leading-tight tracking-[-0.02em]">
        StatusPilot
      </h1>
      <p className="mt-1.5 font-doc text-lg leading-snug text-ink-soft">
        Meeting notes in. Client-ready status out.
      </p>

      <form onSubmit={submit} className="mt-8">
        <label htmlFor="code" className="block text-sm font-medium">
          Access code
        </label>
        <input
          id="code"
          value={code}
          autoFocus
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          onChange={(e) => setCode(e.target.value)}
          className="mt-2 min-h-[2.75rem] w-full rounded-lg border border-line bg-paper px-3 text-base outline-none focus:border-indigo"
          placeholder="Enter the demo code"
        />
        {error ? (
          <p role="alert" className="mt-2 text-sm text-rag-red">
            {error}
          </p>
        ) : null}
        <div className="mt-4">
          <Button type="submit" full disabled={!code.trim() || busy}>
            {busy ? "Checking…" : "Open StatusPilot"}
          </Button>
        </div>
      </form>
    </div>
  );
}
