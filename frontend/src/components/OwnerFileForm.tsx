"use client";

import { useState } from "react";
import { attachOwnerFile } from "@/lib/api";
import { UploadIcon } from "./icons";

const ACCEPT = ".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm";

export function OwnerFileForm({
  analysisId,
  onStarted,
  replace = false,
}: {
  analysisId: string;
  onStarted: () => void;
  replace?: boolean;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  async function submit() {
    if (!file) return;
    setBusy(true);
    setError(null);
    setProgress(0);
    try {
      await attachOwnerFile(analysisId, file, setProgress);
      onStarted();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="mt-3 space-y-2">
      <label className="block text-sm font-medium">
        {replace ? "Replace the file and cross-check again" : "Original video file"}
        <input
          type="file"
          accept={ACCEPT}
          disabled={busy}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="mt-1 block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-white file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-slate-800"
        />
      </label>
      <p className="text-xs opacity-80">
        Use the file you published. YouTube Studio and Instagram&apos;s &quot;Download your information&quot; export both
        provide it. The platform copy is not downloaded. Songs are not identified.
      </p>
      {busy && (
        <div className="flex items-center gap-2" aria-live="polite">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/70">
            <div className="h-full rounded-full bg-slate-900 transition-all" style={{ width: `${Math.round(progress * 100)}%` }} />
          </div>
          <span className="text-xs tabular-nums">{progress < 1 ? `Uploading ${Math.round(progress * 100)}%` : "Processing…"}</span>
        </div>
      )}
      {error && <p className="text-sm font-medium text-red-700">{error}</p>}
      <button
        type="button"
        disabled={!file || busy}
        onClick={submit}
        className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:bg-slate-300"
      >
        <UploadIcon className="h-4 w-4" />
        {busy ? "Starting review…" : "Review this file against the post"}
      </button>
    </div>
  );
}
