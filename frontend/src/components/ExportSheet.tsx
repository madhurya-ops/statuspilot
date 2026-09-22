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
  const canShare = typeof navigator !== "undefined" && typeof navigator.share === "function";

  /**
   * Save a generated file.
   *
   * iOS Safari is the awkward case and it is the one that matters here, because the
   * demo happens on a phone. A blob URL plus `<a download>` is the desktop pattern:
   * on iOS it frequently navigates to the blob instead of saving, and for .docx and
   * .xlsx — which Safari cannot render — that can dead-end on a blank tab.
   *
   * The native route is the share sheet with an actual File attached, which puts
   * "Save to Files", AirDrop and Mail in front of the user. We use it whenever the
   * browser says it can share this specific file, and fall back to the anchor
   * otherwise. `navigator.canShare({files})` is the correct feature test — plain
   * `"share" in navigator` is true on browsers that cannot take files.
   */
  async function download(fmt: Format) {
    setBusy(fmt);
    try {
      const { blob, filename } = await api.exportFile(fmt, documents, projectName, rag);
      const file = new File([blob], filename, { type: blob.type });

      if (typeof navigator.canShare === "function" && navigator.canShare({ files: [file] })) {
        try {
          await navigator.share({ files: [file], title: filename });
          return;
        } catch (err) {
          // A cancelled share is a deliberate choice, not a failure to report.
          if (err instanceof DOMException && err.name === "AbortError") return;
          // Anything else: fall through to the anchor.
        }
      }

      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.rel = "noopener";
      document.body.appendChild(link);
      link.click();
      link.remove();
      // Revoke on a later tick: Safari cancels an in-flight download otherwise.
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
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
        <h2 className="text-sm font-semibold">Save or share</h2>
        <p className="mt-1 text-xs leading-relaxed text-ink-soft">
          On a phone these open the share sheet — choose <strong>Save to Files</strong>,
          Mail, or any app that accepts documents.
        </p>
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
                  {busy === format.id ? "Preparing…" : "Save"}
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
