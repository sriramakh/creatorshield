import { cn } from "@/lib/cn";

/** Determinate when `value` (0–100) is given, indeterminate otherwise. */
export function Progress({
  value,
  label,
  size = "md",
  className,
}: {
  value?: number | null;
  label: string;
  size?: "sm" | "md";
  className?: string;
}) {
  const determinate = value != null && Number.isFinite(value);
  const pct = determinate ? Math.max(0, Math.min(100, Math.round(value))) : 0;
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={determinate ? pct : undefined}
      className={cn("relative overflow-hidden rounded-full bg-surface-3", size === "sm" ? "h-1" : "h-1.5", className)}
    >
      {determinate ? (
        <div className="h-full rounded-full bg-accent transition-[width] duration-[180ms]" style={{ width: `${pct}%` }} />
      ) : (
        <div className="progress-indeterminate absolute inset-y-0 w-2/5 rounded-full bg-accent" />
      )}
    </div>
  );
}
