import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { Banner, Button, Screen } from "../components/Chrome";
import type { Action, SessionState } from "../state/session";

const MIN_CHARS = 200;
const MAX_CHARS = 12_000;
/** Measured: the worst density across the bundled samples was 3.2 chars/token. */
const CHARS_PER_TOKEN = 3.2;

export function InputPage({
  state,
  dispatch,
  onRun,
}: {
  state: SessionState;
  dispatch: React.Dispatch<Action>;
  onRun: (text: string) => void;
}) {
  const [showOptions, setShowOptions] = useState(false);
  const [loadingSample, setLoadingSample] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (state.samples.length) return;
    api
      .samples()
      .then((samples) => dispatch({ type: "setSamples", samples }))
      .catch(() => dispatch({ type: "error", message: "Could not load the sample transcripts." }));
  }, [dispatch, state.samples.length]);

  const chars = state.text.length;
  const tokens = Math.round(chars / CHARS_PER_TOKEN);
  const tooShort = chars > 0 && chars < MIN_CHARS;
  const tooLong = chars > MAX_CHARS;

  async function pickSample(id: string) {
    setLoadingSample(id);
    try {
      const sample = await api.sample(id);
      dispatch({ type: "setText", text: sample.text });
      onRun(sample.text);
    } catch {
      dispatch({ type: "error", message: "Could not load that sample." });
    } finally {
      setLoadingSample(null);
    }
  }

  async function upload(file: File) {
    try {
      const parsed = await api.parse(file);
      dispatch({ type: "setText", text: parsed.text });
      if (parsed.truncated) {
        dispatch({
          type: "error",
          message: `That file was longer than ${MAX_CHARS.toLocaleString()} characters, so it was trimmed to fit.`,
        });
      }
    } catch (err) {
      dispatch({ type: "error", message: (err as Error).message });
    }
  }

  return (
    <Screen
      action={
        <Button
          full
          disabled={chars < MIN_CHARS || tooLong}
          onClick={() => onRun(state.text)}
        >
          Generate reports
        </Button>
      }
    >
      <header>
        <h1 className="text-[1.75rem] font-semibold leading-tight tracking-[-0.02em]">
          StatusPilot
        </h1>
        <p className="mt-1 font-doc text-lg leading-snug text-ink-soft">
          Meeting notes in. Client-ready status out.
        </p>
      </header>

      <div className="mt-5">
        <Banner />
      </div>

      <section aria-labelledby="samples">
        <h2 id="samples" className="text-sm font-semibold">
          Try a sample
        </h2>
        <ul className="mt-2 space-y-2">
          {state.samples.map((sample) => (
            <li key={sample.id}>
              <button
                onClick={() => pickSample(sample.id)}
                disabled={loadingSample !== null}
                className="w-full rounded-xl border border-line bg-paper p-3.5 text-left transition-colors hover:border-indigo/40 disabled:opacity-50"
              >
                <span className="block text-sm font-semibold">{sample.title}</span>
                <span className="mt-0.5 block text-[0.8125rem] leading-relaxed text-ink-soft">
                  {sample.description}
                </span>
                {loadingSample === sample.id ? (
                  <span className="mt-1 block text-xs text-indigo">Loading…</span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-6" aria-labelledby="paste">
        <div className="flex items-baseline justify-between">
          <h2 id="paste" className="text-sm font-semibold">
            Or paste a transcript
          </h2>
          <button
            onClick={() => fileInput.current?.click()}
            className="text-xs font-semibold text-indigo"
          >
            Upload a file
          </button>
          <input
            ref={fileInput}
            type="file"
            accept=".txt,.docx,.vtt,.srt"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void upload(file);
              e.target.value = "";
            }}
          />
        </div>

        <textarea
          value={state.text}
          onChange={(e) => dispatch({ type: "setText", text: e.target.value })}
          rows={8}
          placeholder="Paste meeting notes or a transcript…"
          className="mt-2 w-full resize-y rounded-xl border border-line bg-paper p-3 text-base leading-relaxed outline-none focus:border-indigo"
        />

        {/* The counter explains the limit rather than just enforcing it: the ceiling
            is a real free-tier token budget, not an arbitrary cutoff. */}
        <p
          className={`mt-1.5 text-xs tabular-nums ${tooLong ? "text-rag-red" : "text-ink-faint"}`}
        >
          {chars.toLocaleString()} / {MAX_CHARS.toLocaleString()} characters
          {chars > 0 ? ` · about ${tokens.toLocaleString()} tokens` : ""}
          {tooShort ? " · need at least 200 to summarise" : ""}
          {tooLong ? " · too long for one free-tier request" : ""}
        </p>
      </section>

      <section className="mt-5">
        <button
          onClick={() => setShowOptions((v) => !v)}
          className="text-xs font-semibold text-ink-soft"
          aria-expanded={showOptions}
        >
          {showOptions ? "Hide" : "Add"} project name and period
        </button>
        {showOptions ? (
          <div className="mt-3 space-y-3">
            <Field
              label="Project name"
              value={state.projectName}
              onChange={(v) => dispatch({ type: "setField", field: "projectName", value: v })}
            />
            <Field
              label="Reporting period"
              value={state.reportingPeriod}
              onChange={(v) => dispatch({ type: "setField", field: "reportingPeriod", value: v })}
            />
          </div>
        ) : null}
      </section>
    </Screen>
  );
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-medium text-ink-soft">
        {label}
      </label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 min-h-[2.5rem] w-full rounded-lg border border-line bg-paper px-3 text-sm outline-none focus:border-indigo"
      />
    </div>
  );
}
