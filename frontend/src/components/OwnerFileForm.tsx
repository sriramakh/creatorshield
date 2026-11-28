"use client";

import { Upload, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { attachOwnerFile, errorMessage, isAbortError } from "@/lib/api";
import { fmtBytes } from "@/lib/format";
import { Button, Callout, Field, Progress } from "./ui";
import { FilePicker } from "./ui/FilePicker";

const ACCEPT = ".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm";

/** Attach the creator's own file to an imported post (full review, cross-checked against the post). */
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
  const abortRef = useRef<AbortController | null>(null);
  useEffect(() => () => abortRef.current?.abort(), []);

  async function submit() {
    if (!file) return;
    setBusy(true);
    setError(null);
    setProgress(0);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await attachOwnerFile(analysisId, file, setProgress, controller.signal);
      setFile(null);
      setBusy(false);
      onStarted();
    } catch (e) {
      if (!isAbortError(e)) setError(errorMessage(e));
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <Field
        label={replace ? "Replace the file and cross-check again" : "Original video file"}
        hint="Use the file you published: YouTube Studio and Instagram’s “Download your information” both provide it. The platform copy is not downloaded and songs are not identified."
      >
        {(p) => <FilePicker {...p} accept={ACCEPT} disabled={busy} files={file ? [file] : []} onFiles={(f) => setFile(f[0] ?? null)} />}
      </Field>
      {busy && (
        <div className="space-y-1.5" aria-live="polite">
          <div className="flex justify-between text-[13px] text-ink-2">
            <span>{progress < 1 ? "Uploading…" : "Starting the review…"}</span>
            {file && progress < 1 && (
              <span className="tabular text-ink-3">
                {fmtBytes(file.size * progress)} of {fmtBytes(file.size)}
              </span>
            )}
          </div>
          <Progress value={progress < 1 ? progress * 100 : null} label="Upload progress" />
        </div>
      )}
      {error && (
        <Callout tone="danger" title="The file was not attached">
          {error}
        </Callout>
      )}
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" size="sm" leadingIcon={<Upload />} disabled={!file || busy} loading={busy && progress >= 1} onClick={submit}>
          Review this file against the post
        </Button>
        {busy && progress < 1 && (
          <Button size="sm" variant="ghost" leadingIcon={<X />} onClick={() => abortRef.current?.abort()}>
            Cancel upload
          </Button>
        )}
      </div>
    </div>
  );
}
