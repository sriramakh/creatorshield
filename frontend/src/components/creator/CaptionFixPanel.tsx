"use client";

import { Replace } from "lucide-react";
import type { CaptionFix } from "@/lib/api";
import { Button, CopyButton } from "../ui";

/** Original vs suggested caption, the changes made, the note, Copy and (optionally) Replace. */
export function CaptionFixPanel({
  fix,
  original,
  onReplace,
}: {
  fix: CaptionFix;
  original: string;
  onReplace?: () => void;
}) {
  if (!fix.needed) return null;
  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2">
        <div className="min-w-0 rounded-[8px] border border-line bg-surface-2 p-3">
          <div className="text-[12px] font-medium text-ink-3">Your caption</div>
          <p className="mt-1 text-[13px] break-words whitespace-pre-wrap text-ink-2">{original || <span className="text-ink-3">(empty)</span>}</p>
        </div>
        <div className="min-w-0 rounded-[8px] border border-success-line bg-success-bg p-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[12px] font-medium text-success-fg">Suggested caption</span>
            <CopyButton value={fix.suggested_caption} label="Copy suggested caption" />
          </div>
          <p className="mt-1 text-[13px] break-words whitespace-pre-wrap text-ink">{fix.suggested_caption}</p>
          {fix.suggested_hashtags.length > 0 && (
            <p className="mt-1.5 text-[12px] text-ink-2">{fix.suggested_hashtags.map((h) => `#${h.replace(/^#/, "")}`).join(" ")}</p>
          )}
        </div>
      </div>
      {fix.changes.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-5 text-[13px] text-ink-2" aria-label="What changed">
          {fix.changes.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      )}
      <p className="text-[12px] text-ink-3">{fix.note}</p>
      {onReplace && (
        <Button size="sm" variant="primary" leadingIcon={<Replace />} onClick={onReplace}>
          Replace my caption
        </Button>
      )}
    </div>
  );
}
