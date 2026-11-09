import type { ReactNode } from "react";
import type { AnalysisSummary, Confidence, RiskLevel, Severity } from "@/lib/api";
import { CONFIDENCE_LEVEL, RISK_STYLE, SEVERITY_LABEL, SEVERITY_STYLE, STAGE_LABEL } from "@/lib/format";
import { AlertIcon } from "./icons";

export function Card({
  children,
  className = "",
  label,
}: {
  children: ReactNode;
  className?: string;
  label?: string;
}) {
  return (
    <div
      aria-label={label}
      className={`rounded-xl border border-slate-200 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] ${className}`}
    >
      {children}
    </div>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide ${SEVERITY_STYLE[severity].badge}`}
    >
      {SEVERITY_LABEL[severity]}
    </span>
  );
}

export function Pill({ children, className = "", title }: { children: ReactNode; className?: string; title?: string }) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600 ${className}`}
    >
      {children}
    </span>
  );
}

export function ConfidenceMeter({ confidence }: { confidence: Confidence }) {
  const level = CONFIDENCE_LEVEL[confidence];
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-slate-600" title="Model/rule confidence in this finding">
      <span className="flex items-end gap-0.5">
        {[1, 2, 3].map((i) => (
          <span
            key={i}
            className={`w-1 rounded-sm ${i <= level ? "bg-slate-700" : "bg-slate-200"}`}
            style={{ height: 4 + i * 3 }}
          />
        ))}
      </span>
      {confidence[0].toUpperCase() + confidence.slice(1)} confidence
    </span>
  );
}

export function RiskBadge({ level, score }: { level: RiskLevel | null; score?: number | null }) {
  if (!level) return <span className="text-sm text-slate-400">—</span>;
  const s = RISK_STYLE[level];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${s.bg} ${s.text} ${s.ring}`}>
      {s.label}
      {score != null && <span className="font-normal opacity-70">· {score}</span>}
    </span>
  );
}

export function StatusBadge({ a }: { a: Pick<AnalysisSummary, "status" | "stage" | "progress"> }) {
  if (a.status === "completed")
    return <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700"><Dot className="bg-emerald-500" />Completed</span>;
  if (a.status === "failed")
    return <span className="inline-flex items-center gap-1.5 text-xs font-medium text-red-700"><Dot className="bg-red-500" />Failed</span>;
  if (a.status === "awaiting_file")
    return <span className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-700"><Dot className="bg-amber-500" />Needs your file</span>;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-700">
      <Dot className="animate-pulse bg-brand-500" />
      {STAGE_LABEL[a.stage] ?? a.stage} · {a.progress}%
    </span>
  );
}

function Dot({ className }: { className: string }) {
  return <span className={`h-1.5 w-1.5 rounded-full ${className}`} />;
}

export function Banner({
  tone,
  title,
  children,
}: {
  tone: "warning" | "danger" | "info" | "mock";
  title: string;
  children?: ReactNode;
}) {
  const styles = {
    warning: "border-amber-200 bg-amber-50 text-amber-900",
    danger: "border-red-200 bg-red-50 text-red-900",
    info: "border-sky-200 bg-sky-50 text-sky-900",
    mock: "border-amber-400 bg-amber-100 text-amber-950",
  }[tone];
  return (
    <div className={`flex gap-3 rounded-xl border px-4 py-3 text-sm ${styles}`} role="status">
      <AlertIcon className="mt-0.5 h-4 w-4 flex-none" />
      <div>
        <div className="font-semibold">{title}</div>
        {children && <div className="mt-0.5 opacity-90">{children}</div>}
      </div>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton rounded-md ${className}`} />;
}
