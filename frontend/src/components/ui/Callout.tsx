import { CircleCheck, CircleExclamationPoint, Info, TriangleExclamationPoint, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export type CalloutTone = "info" | "success" | "warning" | "danger";

const STYLE: Record<CalloutTone, { box: string; icon: string; Icon: LucideIcon }> = {
  info: { box: "border-low-line bg-low-bg", icon: "text-low-fg", Icon: Info },
  success: { box: "border-success-line bg-success-bg", icon: "text-success-fg", Icon: CircleCheck },
  warning: { box: "border-medium-line bg-medium-bg", icon: "text-medium-fg", Icon: TriangleExclamationPoint },
  danger: { box: "border-critical-line bg-critical-bg", icon: "text-critical-fg", Icon: CircleExclamationPoint },
};

/** Inline message for a section or page. Danger callouts are announced (role="alert"). */
export function Callout({
  tone = "info",
  title,
  children,
  action,
  className,
  icon,
}: {
  tone?: CalloutTone;
  title?: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
  icon?: LucideIcon;
}) {
  const s = STYLE[tone];
  const Icon = icon ?? s.Icon;
  return (
    <div
      role={tone === "danger" ? "alert" : undefined}
      className={cn("flex gap-3 rounded-[10px] border px-4 py-3 text-sm text-ink", s.box, className)}
    >
      <Icon className={cn("mt-[3px] size-4 shrink-0", s.icon)} strokeWidth={2} aria-hidden />
      <div className="min-w-0 flex-1">
        {title && <div className="font-semibold">{title}</div>}
        {children && <div className={cn("text-ink-2", title ? "mt-0.5" : undefined)}>{children}</div>}
        {action && <div className="mt-2.5 flex flex-wrap items-center gap-2">{action}</div>}
      </div>
    </div>
  );
}
