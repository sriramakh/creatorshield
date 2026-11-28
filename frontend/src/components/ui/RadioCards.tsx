"use client";

import { CircleCheck } from "lucide-react";
import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "@/lib/cn";

/** Large single-choice cards (radio group, arrow keys move and select). */
export function RadioCards<T extends string>({
  value,
  onChange,
  options,
  label,
  className,
}: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; title: string; description?: ReactNode; icon?: ReactNode }[];
  label: string;
  className?: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  function onKeyDown(e: KeyboardEvent) {
    const i = options.findIndex((o) => o.value === value);
    let next = -1;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") next = (i + 1) % options.length;
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = (i - 1 + options.length) % options.length;
    if (next < 0) return;
    e.preventDefault();
    onChange(options[next].value);
    refs.current[next]?.focus();
  }
  return (
    <div role="radiogroup" aria-label={label} onKeyDown={onKeyDown} className={cn("grid gap-2", className ?? "sm:grid-cols-2")}>
      {options.map((o, i) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={on}
            tabIndex={on ? 0 : -1}
            onClick={() => onChange(o.value)}
            className={cn(
              "relative flex items-start gap-3 rounded-[10px] border p-3.5 text-left transition-colors duration-[120ms]",
              on ? "border-accent bg-accent-soft ring-1 ring-accent" : "border-line-strong bg-surface hover:bg-surface-2",
            )}
          >
            {o.icon && (
              <span className={cn("mt-0.5 [&_svg]:size-5", on ? "text-accent" : "text-ink-3")} aria-hidden>
                {o.icon}
              </span>
            )}
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-semibold text-ink">{o.title}</span>
              {o.description && <span className="mt-0.5 block text-[12px] leading-4 text-ink-3">{o.description}</span>}
            </span>
            <CircleCheck className={cn("size-4 shrink-0", on ? "text-accent" : "invisible")} aria-hidden />
          </button>
        );
      })}
    </div>
  );
}
