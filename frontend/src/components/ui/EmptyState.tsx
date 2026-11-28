import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/** Empty state: icon, title, one sentence, one action. */
export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center px-6 py-12 text-center", className)}>
      {icon && (
        <span className="flex size-11 items-center justify-center rounded-[10px] border border-line bg-surface-2 text-ink-2 [&_svg]:size-5">
          {icon}
        </span>
      )}
      <h2 className="mt-4 text-[15px] leading-[22px] font-semibold text-ink">{title}</h2>
      {description && <p className="mt-1 max-w-sm text-[13px] leading-5 text-ink-3">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
