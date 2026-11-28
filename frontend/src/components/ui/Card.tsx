import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

export function Card({
  className,
  label,
  children,
  ...rest
}: HTMLAttributes<HTMLDivElement> & { label?: string }) {
  return (
    <div aria-label={label} className={cn("rounded-[10px] border border-line bg-surface", className)} {...rest}>
      {children}
    </div>
  );
}

/** A titled card with optional description and actions. */
export function Section({
  title,
  description,
  actions,
  children,
  className,
  bodyClassName,
  id,
  as: Heading = "h2",
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  id?: string;
  as?: "h2" | "h3";
}) {
  const headingId = id ? `${id}-title` : undefined;
  return (
    <section id={id} aria-labelledby={headingId} className={cn("rounded-[10px] border border-line bg-surface", className)}>
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
        <div className="min-w-0">
          <Heading id={headingId} className="text-[15px] leading-[22px] font-semibold text-ink">
            {title}
          </Heading>
          {description && <p className="mt-0.5 max-w-[72ch] text-[13px] leading-5 text-ink-3">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </header>
      <div className={cn("p-5", bodyClassName)}>{children}</div>
    </section>
  );
}

/** KPI tile: label, value, optional delta/hint and a tiny sparkline. */
export function StatTile({
  label,
  value,
  hint,
  delta,
  sparkline,
  icon,
  className,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  /** Signed change vs a named period; `sentiment` says whether that direction is good. */
  delta?: { value: string; sentiment: "good" | "bad" | "neutral"; label?: string };
  sparkline?: number[];
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-[10px] border border-line bg-surface px-4 py-4", className)}>
      <div className="flex items-center justify-between gap-2">
        <div className="text-[11px] leading-4 font-semibold tracking-[0.06em] text-ink-3 uppercase">{label}</div>
        {icon && <span className="text-ink-3 [&_svg]:size-4">{icon}</span>}
      </div>
      <div className="mt-2 flex items-end justify-between gap-3">
        <div className="text-[26px] leading-8 font-semibold tracking-tight text-ink">{value}</div>
        {sparkline && sparkline.length > 1 && <Sparkline values={sparkline} />}
      </div>
      {(hint || delta) && (
        <div className="mt-1 flex items-center gap-2 text-[12px] leading-4 text-ink-3">
          {delta && (
            <span
              className={cn(
                "tabular font-semibold",
                delta.sentiment === "good" ? "text-success-fg" : delta.sentiment === "bad" ? "text-critical-fg" : "text-ink-2",
              )}
            >
              {delta.value}
              {delta.label && <span className="sr-only"> {delta.label}</span>}
            </span>
          )}
          {hint}
        </div>
      )}
    </div>
  );
}

function Sparkline({ values }: { values: number[] }) {
  const w = 72;
  const h = 24;
  const max = Math.max(...values, 1);
  const step = w / (values.length - 1);
  const points = values.map((v, i) => `${(i * step).toFixed(1)},${(h - 2 - (v / max) * (h - 4)).toFixed(1)}`).join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden className="text-accent">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
