import {
  CircleCheck,
  CircleExclamationPoint,
  Info,
  OctagonExclamationPoint,
  TriangleExclamationPoint,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";
import type { ReadinessVerdict, RiskLevel, Severity } from "@/lib/api";
import { cn } from "@/lib/cn";

export type StatusTone = "critical" | "high" | "medium" | "low" | "info" | "success";
export type BadgeTone = StatusTone | "neutral" | "accent";

const TONE: Record<BadgeTone, string> = {
  critical: "bg-critical-bg text-critical-fg border-critical-line",
  high: "bg-high-bg text-high-fg border-high-line",
  medium: "bg-medium-bg text-medium-fg border-medium-line",
  low: "bg-low-bg text-low-fg border-low-line",
  info: "bg-info-bg text-info-fg border-info-line",
  success: "bg-success-bg text-success-fg border-success-line",
  neutral: "bg-surface-2 text-ink-2 border-line",
  accent: "bg-accent-soft text-accent border-transparent",
};

export const SOLID: Record<StatusTone, string> = {
  critical: "bg-critical-solid",
  high: "bg-high-solid",
  medium: "bg-medium-solid",
  low: "bg-low-solid",
  info: "bg-info-solid",
  success: "bg-success-solid",
};

export const TONE_SOFT: Record<StatusTone, string> = {
  critical: "bg-critical-bg",
  high: "bg-high-bg",
  medium: "bg-medium-bg",
  low: "bg-low-bg",
  info: "bg-info-bg",
  success: "bg-success-bg",
};

export const TONE_TEXT: Record<StatusTone, string> = {
  critical: "text-critical-fg",
  high: "text-high-fg",
  medium: "text-medium-fg",
  low: "text-low-fg",
  info: "text-info-fg",
  success: "text-success-fg",
};

export function Badge({
  tone = "neutral",
  icon: Icon,
  children,
  className,
  title,
}: {
  tone?: BadgeTone;
  icon?: LucideIcon;
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex h-[22px] items-center gap-1 rounded-[6px] border px-1.5 text-[12px] leading-4 font-medium whitespace-nowrap",
        TONE[tone],
        className,
      )}
    >
      {Icon && <Icon className="size-3.5 shrink-0" strokeWidth={2} aria-hidden />}
      {children}
    </span>
  );
}

export const SEVERITY_ICON: Record<Severity, LucideIcon> = {
  critical: OctagonExclamationPoint,
  high: TriangleExclamationPoint,
  medium: CircleExclamationPoint,
  low: Info,
  info: Info,
};
export const SEVERITY_TEXT: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  return (
    <Badge tone={severity} icon={SEVERITY_ICON[severity]} className={className}>
      {SEVERITY_TEXT[severity]}
    </Badge>
  );
}

/** Risk indicator wording. Never "safe" or "approved" (DESIGN.md content rules). */
export const RISK: Record<RiskLevel, { label: string; tone: StatusTone; icon: LucideIcon; advice: string }> = {
  low: {
    label: "Low risk",
    tone: "success",
    icon: CircleCheck,
    advice: "No serious issues found by these checks. Review the notes below before posting.",
  },
  moderate: {
    label: "Moderate risk",
    tone: "medium",
    icon: CircleExclamationPoint,
    advice: "Fix or consciously accept the flagged items before posting.",
  },
  elevated: {
    label: "Elevated risk",
    tone: "high",
    icon: TriangleExclamationPoint,
    advice: "Fix the flagged items before posting.",
  },
  high: {
    label: "High risk",
    tone: "critical",
    icon: OctagonExclamationPoint,
    advice: "Do not post as is. Fix the flagged items first.",
  },
};

export function RiskBadge({ level, score, className }: { level: RiskLevel | null; score?: number | null; className?: string }) {
  if (!level) return <span className="text-sm text-ink-3">—</span>;
  const v = RISK[level];
  return (
    <Badge tone={v.tone} icon={v.icon} className={className}>
      {v.label}
      {score != null && <span className="tabular font-normal opacity-80">· {score}</span>}
    </Badge>
  );
}

export function StatusDot({ tone, pulse, className }: { tone: StatusTone; pulse?: boolean; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn("inline-block size-2 shrink-0 rounded-full", SOLID[tone], pulse && "animate-pulse", className)}
    />
  );
}

/** Readiness verdict wording (DESIGN.md: never "safe", "approved" or "cleared"). */
export const VERDICT: Record<ReadinessVerdict, { label: string; tone: StatusTone; icon: LucideIcon }> = {
  ready: { label: "No issues found", tone: "success", icon: CircleCheck },
  review: { label: "Review", tone: "medium", icon: CircleExclamationPoint },
  fix_first: { label: "Fix first", tone: "critical", icon: OctagonExclamationPoint },
};

export function VerdictBadge({ verdict, className }: { verdict: ReadinessVerdict | null | undefined; className?: string }) {
  if (!verdict) return <span className="text-sm text-ink-3">—</span>;
  const v = VERDICT[verdict];
  return (
    <Badge tone={v.tone} icon={v.icon} className={className}>
      {v.label}
    </Badge>
  );
}
