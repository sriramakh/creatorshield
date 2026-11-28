"use client";

import { Check } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/** Multi-select chips (each chip is a toggle button). */
export function ChipGroup<T extends string>({
  value,
  onChange,
  options,
  label,
  className,
}: {
  value: T[];
  onChange: (value: T[]) => void;
  options: { value: T; label: ReactNode; count?: number }[];
  label: string;
  className?: string;
}) {
  return (
    <div role="group" aria-label={label} className={cn("flex flex-wrap gap-1.5", className)}>
      {options.map((o) => {
        const on = value.includes(o.value);
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(on ? value.filter((v) => v !== o.value) : [...value, o.value])}
            className={cn(
              "inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-[13px] font-medium transition-colors duration-[120ms]",
              on ? "border-accent bg-accent-soft text-accent" : "border-line-strong bg-surface text-ink-2 hover:bg-surface-2 hover:text-ink",
            )}
          >
            {on && <Check className="size-3.5" aria-hidden />}
            {o.label}
            {o.count != null && <span className="tabular text-[12px] opacity-80">{o.count}</span>}
          </button>
        );
      })}
    </div>
  );
}
