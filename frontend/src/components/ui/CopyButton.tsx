"use client";

import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";
import { IconButton } from "./IconButton";

/** Copies `value`; the icon turns into a check for two seconds. */
export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(t);
  }, [copied]);
  return (
    <>
      <IconButton
        size="sm"
        label={copied ? "Copied" : label}
        icon={copied ? <Check className="text-success-fg" /> : <Copy />}
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(value);
            setCopied(true);
          } catch {
            /* clipboard blocked: nothing to report beyond the unchanged icon */
          }
        }}
      />
      <span className="sr-only" aria-live="polite">
        {copied ? "Copied to clipboard" : ""}
      </span>
    </>
  );
}
