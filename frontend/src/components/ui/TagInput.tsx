"use client";

import { X } from "lucide-react";
import { useState, type ClipboardEvent, type KeyboardEvent } from "react";
import { cn } from "@/lib/cn";
import type { FieldControlProps } from "./Field";

/**
 * A list as tags: Enter or comma adds, Backspace on an empty input removes the last one,
 * pasted comma- or line-separated text adds several. `prefix` is shown, never stored.
 */
export function TagInput({
  value,
  onChange,
  max,
  maxLength,
  prefix,
  placeholder,
  ...field
}: Partial<FieldControlProps> & {
  id: string;
  value: string[];
  onChange: (value: string[]) => void;
  max: number;
  maxLength: number;
  prefix?: string;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const full = value.length >= max;

  function add(raw: string[]) {
    const next = [...value];
    let msg: string | null = null;
    for (const r of raw) {
      const item = r.trim().replace(prefix ? new RegExp(`^\\${prefix}`) : /^$/, "").trim();
      if (!item) continue;
      if (item.length > maxLength) {
        msg = `Each entry can be at most ${maxLength} characters.`;
        continue;
      }
      if (next.some((v) => v.toLowerCase() === item.toLowerCase())) continue;
      if (next.length >= max) {
        msg = `At most ${max} entries.`;
        break;
      }
      next.push(item);
    }
    setNote(msg);
    if (next.length !== value.length) onChange(next);
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      if (draft.trim()) {
        add([draft]);
        setDraft("");
      }
    } else if (e.key === "Backspace" && !draft && value.length) {
      e.preventDefault();
      onChange(value.slice(0, -1));
    }
  }

  function onPaste(e: ClipboardEvent<HTMLInputElement>) {
    const text = e.clipboardData.getData("text");
    if (!/[,\n]/.test(text)) return;
    e.preventDefault();
    add(text.split(/[,\n]/));
  }

  return (
    <div>
      <div
        className={cn(
          "flex min-h-9 flex-wrap items-center gap-1.5 rounded-[6px] border border-line-strong bg-surface px-2 py-1.5 transition-colors duration-[120ms]",
          "focus-within:border-accent hover:border-ink-3",
          field["aria-invalid"] && "border-critical-fg",
        )}
      >
        <ul className="contents" aria-label="Entries">
          {value.map((v, i) => (
            <li key={`${v}-${i}`} className="inline-flex h-6 max-w-full items-center gap-1 rounded-[4px] bg-surface-3 pr-0.5 pl-1.5 text-[13px] text-ink">
              <span className="truncate">
                {prefix}
                {v}
              </span>
              <button
                type="button"
                onClick={() => onChange(value.filter((_, j) => j !== i))}
                aria-label={`Remove ${prefix ?? ""}${v}`}
                className="inline-flex size-5 items-center justify-center rounded-[3px] text-ink-3 hover:bg-line hover:text-ink"
              >
                <X className="size-3" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
        <input
          {...field}
          suppressHydrationWarning
          value={draft}
          disabled={full}
          onChange={(e) => {
            // A typed or pasted comma ends an entry (mobile keyboards do not always send key events).
            const parts = e.target.value.split(/[,\n]/);
            if (parts.length > 1) {
              add(parts.slice(0, -1));
              setDraft(parts[parts.length - 1].slice(0, maxLength + 1));
            } else {
              setDraft(e.target.value.slice(0, maxLength + 1));
            }
          }}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          onBlur={() => {
            if (draft.trim()) {
              add([draft]);
              setDraft("");
            }
          }}
          placeholder={full ? `Limit of ${max} reached` : value.length ? "" : placeholder}
          className="h-6 min-w-[8rem] flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-3 focus-visible:outline-none disabled:cursor-not-allowed"
        />
      </div>
      {note && (
        <p role="alert" className="mt-1 text-[12px] font-medium text-critical-fg">
          {note}
        </p>
      )}
    </div>
  );
}
