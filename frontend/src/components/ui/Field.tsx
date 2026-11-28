"use client";

import { ChevronDown } from "lucide-react";
import {
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { cn } from "@/lib/cn";

const CONTROL =
  "w-full rounded-[6px] border border-line-strong bg-surface text-sm text-ink transition-colors duration-[120ms] " +
  "hover:border-ink-3 focus:border-accent focus-visible:outline-2 focus-visible:outline-offset-0 " +
  "disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-ink-3 " +
  "aria-[invalid=true]:border-critical-fg";

export interface FieldControlProps {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
  required?: boolean;
}

/** Label, hint, error and optional counter around one control. */
export function Field({
  label,
  hint,
  error,
  required,
  counter,
  className,
  labelHidden,
  children,
}: {
  label: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  required?: boolean;
  counter?: { value: number; max: number; unit?: string };
  className?: string;
  labelHidden?: boolean;
  children: (props: FieldControlProps) => ReactNode;
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  const over = counter ? counter.value > counter.max : false;
  return (
    <div className={cn("space-y-1.5", className)}>
      <div className={cn("flex items-baseline justify-between gap-3", labelHidden && "sr-only")}>
        <label htmlFor={id} className="text-[13px] font-medium text-ink">
          {label}
          {required && (
            <span className="text-critical-fg" aria-hidden>
              {" "}
              *
            </span>
          )}
        </label>
        {counter && (
          <span className={cn("tabular text-[12px]", over ? "font-semibold text-critical-fg" : "text-ink-3")}>
            {counter.value}/{counter.max}
            {counter.unit ? ` ${counter.unit}` : ""}
          </span>
        )}
      </div>
      {children({ id, "aria-describedby": describedBy, "aria-invalid": error || over ? true : undefined, required })}
      {hint && !error && (
        <p id={hintId} className="text-[12px] leading-4 text-ink-3">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="text-[12px] leading-4 font-medium text-critical-fg">
          {error}
        </p>
      )}
    </div>
  );
}

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  // suppressHydrationWarning: password/autofill extensions add attributes (e.g. data-sharkid) to
  // inputs before hydration; that is not a mismatch in our markup.
  return <input suppressHydrationWarning className={cn(CONTROL, "h-9 px-3", className)} {...rest} />;
}

export function Textarea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea suppressHydrationWarning className={cn(CONTROL, "min-h-20 resize-y px-3 py-2 leading-[22px]", className)} {...rest} />;
}

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className={cn("relative", className)}>
      <select suppressHydrationWarning className={cn(CONTROL, "h-9 appearance-none pr-8 pl-3")} {...rest}>
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute top-1/2 right-2.5 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
    </div>
  );
}

export function Checkbox({
  label,
  description,
  className,
  ...rest
}: { label: ReactNode; description?: ReactNode } & Omit<InputHTMLAttributes<HTMLInputElement>, "type">) {
  return (
    <label
      className={cn(
        "flex cursor-pointer items-start gap-3 text-sm text-ink",
        rest.disabled && "cursor-not-allowed opacity-60",
        className,
      )}
    >
      <input type="checkbox" suppressHydrationWarning className="mt-[3px] size-4 shrink-0 cursor-[inherit] accent-[var(--accent)]" {...rest} />
      <span>
        {label}
        {description && <span className="mt-0.5 block text-[13px] text-ink-3">{description}</span>}
      </span>
    </label>
  );
}

export function Switch({
  checked,
  onCheckedChange,
  label,
  disabled,
}: {
  checked: boolean;
  onCheckedChange: (value: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors duration-[120ms] disabled:opacity-50",
        checked ? "bg-accent" : "bg-line-strong",
      )}
    >
      <span
        className={cn(
          "inline-block size-4 rounded-full bg-surface shadow transition-transform duration-[120ms]",
          checked ? "translate-x-[18px]" : "translate-x-0.5",
        )}
      />
    </button>
  );
}
