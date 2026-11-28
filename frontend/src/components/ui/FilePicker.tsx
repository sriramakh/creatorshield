"use client";

import { Paperclip } from "lucide-react";
import { buttonClasses } from "./Button";
import type { FieldControlProps } from "./Field";

/**
 * Native file input with a styled button and the chosen file name(s). The input value is
 * cleared after every pick so choosing the same file again still fires.
 */
export function FilePicker({
  accept,
  multiple,
  disabled,
  files,
  onFiles,
  buttonLabel = "Choose file",
  emptyLabel = "No file chosen",
  ...field
}: Partial<FieldControlProps> & {
  id: string;
  accept: string;
  multiple?: boolean;
  disabled?: boolean;
  files: File[];
  onFiles: (files: File[]) => void;
  buttonLabel?: string;
  emptyLabel?: string;
}) {
  const names = files.map((f) => f.name).join(", ");
  return (
    <div className="flex min-w-0 items-center gap-3">
      <input
        {...field}
        type="file"
        suppressHydrationWarning
        accept={accept}
        multiple={multiple}
        disabled={disabled}
        className="peer sr-only"
        onChange={(e) => {
          onFiles(Array.from(e.target.files ?? []));
          e.target.value = "";
        }}
      />
      <label
        htmlFor={field.id}
        aria-hidden
        className={buttonClasses(
          "secondary",
          "sm",
          "cursor-pointer peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[var(--focus)] peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        )}
      >
        <Paperclip aria-hidden />
        {buttonLabel}
      </label>
      <span className={names ? "min-w-0 truncate text-sm text-ink" : "text-sm text-ink-3"} title={names || undefined}>
        {names || emptyLabel}
      </span>
    </div>
  );
}
