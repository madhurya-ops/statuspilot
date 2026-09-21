import { useState } from "react";
import { api, ApiError } from "../api/client";
import { Button } from "./Chrome";
import type { Documents } from "../types";

type Format = "docx" | "xlsx" | "pdf";

const FORMATS: { id: Format; label: string; hint: string }[] = [
  { id: "docx", label: "Word", hint: "Status report and minutes" },
  { id: "xlsx", label: "Excel", hint: "RAID log and action items" },
  { id: "pdf", label: "PDF", hint: "Status report only" },
];

export function ExportSheet({
  documents,
  projectName,
  rag,
  onClose,
  onError,
}: {
  documents: Documents;
  projectName: string | null;
  rag: string;
  onClose: () => void;
  onError: (message: string) => void;
}) {
  const [busy, setBusy] = useState<Format | null>(null);
  const canShare = typeof navigator !== "undefined" && "share" in navigator;

  async function download(fmt: Format) {
    setBusy(fmt);
    try {
      const { blob, filename } = await api.exportFile(fmt, documents, projectName, rag);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      // Revoke on the next tick: Safari cancels an in-flight download otherwise.
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "That download failed.");
    } finally {
      setBusy(null);
    }
  }

  async function share() {
    try {
      await navigator.share({
        title: projectName || "Status report",
        text: documents.status_report_markdown,
      });
    } catch {
      // A cancelled share is not an error worth reporting.
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-ink/30 p-0 sm:items-center sm:p-4">
      <div
        role="dialog"
        aria-label="Export"
        className="w-full max-w-[34rem] rounded-t-2xl border border-line bg-paper p-4 sm:rounded-2xl"
      >
        <h2 className="text-sm font-semibold">Download or share</h2>
        <ul className="mt-3 space-y-2">
          {FORMATS.map((format) => (
            <li key={format.id}>
              <button
                onClick={() => void download(format.id)}
                disabled={busy !== null}
                className="flex w-full items-center justify-between rounded-xl border border-line px-3.5 py-3 text-left disabled:opacity-50"
              >
                <span>
                  <span className="block text-sm font-semibold">{format.label}</span>
                  <span className="block text-xs text-ink-soft">{format.hint}</span>
                </span>
                <span className="text-xs font-semibold text-indigo">
                  {busy === format.id ? "Preparing…" : "Download"}
                </span>
              </button>
            </li>
          ))}
        </ul>

        <div className="mt-3 flex gap-2">
          {canShare ? (
            <Button variant="secondary" full onClick={() => void share()}>
              Share
            </Button>
          ) : null}
          <Button variant="quiet" full onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}
