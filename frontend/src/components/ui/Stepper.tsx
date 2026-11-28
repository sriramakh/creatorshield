import { cn } from "@/lib/cn";

export type StepState = "done" | "current" | "todo";

/** Vertical list of steps with done/current/todo states. */
export function Stepper({ steps, label }: { steps: { label: string; state: StepState }[]; label: string }) {
  return (
    <ol aria-label={label} className="space-y-0">
      {steps.map((s, i) => (
        <li key={s.label} className="relative flex gap-3 pb-4 last:pb-0" aria-current={s.state === "current" ? "step" : undefined}>
          {i < steps.length - 1 && (
            <span aria-hidden className={cn("absolute top-6 left-[9px] h-[calc(100%-20px)] w-px", s.state === "done" ? "bg-accent" : "bg-line")} />
          )}
          <span
            aria-hidden
            className={cn(
              "relative z-10 mt-0.5 flex size-[19px] shrink-0 items-center justify-center rounded-full border text-[10px] font-semibold",
              s.state === "done" && "border-accent bg-accent text-on-accent",
              s.state === "current" && "border-accent bg-surface text-accent",
              s.state === "todo" && "border-line-strong bg-surface text-ink-3",
            )}
          >
            {s.state === "done" ? "✓" : s.state === "current" ? <span className="size-2 animate-pulse rounded-full bg-accent" /> : i + 1}
          </span>
          <span
            className={cn(
              "text-sm",
              s.state === "current" ? "font-semibold text-ink" : s.state === "done" ? "text-ink-2" : "text-ink-3",
            )}
          >
            {s.label}
            <span className="sr-only">{s.state === "done" ? " (done)" : s.state === "current" ? " (in progress)" : ""}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}
