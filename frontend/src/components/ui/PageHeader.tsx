import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/** Page title, one-line description and page-level actions. */
export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  eyebrow?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-x-6 gap-y-4", className)}>
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-[11px] leading-4 font-semibold tracking-[0.06em] text-ink-3 uppercase">{eyebrow}</div>}
        <h1 className="text-[24px] leading-8 font-[650] tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1 max-w-[72ch] text-sm text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
