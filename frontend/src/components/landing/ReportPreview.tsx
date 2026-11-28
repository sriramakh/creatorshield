import { CircleCheck, OctagonExclamationPoint, Play } from "lucide-react";
import { BRAND } from "@/lib/brand";
import { Badge, SeverityBadge } from "../ui";
import type { Severity } from "@/lib/api";

// A static picture of a report for the hero. Labelled as an example.
const FINDINGS: { at: string; sev: Severity; area: string; text: string; from: string }[] = [
  { at: "0:00", sev: "high", area: "Disclosure", text: "“Sponsored” is not treated as clear in the UK; open with “Ad”", from: "Caption" },
  { at: "0:12", sev: "high", area: "Community guidelines", text: "Risk flag: “guaranteed 20% returns, risk-free”", from: "Speech" },
  { at: "0:21", sev: "medium", area: "Licensing", text: "Broadcaster name on screen: “Star Sports”", from: "On-screen text" },
  { at: "0:37", sev: "medium", area: "Claims", text: "“Guaranteed to burn fat in 7 days”", from: "Speech" },
  { at: "0:44", sev: "medium", area: "Brand brief", text: "Required line “patch test first” was not found", from: "Brief" },
];

const MARKERS: { left: number; sev: Severity }[] = [
  { left: 1, sev: "high" },
  { left: 20, sev: "high" },
  { left: 36, sev: "medium" },
  { left: 63, sev: "medium" },
  { left: 75, sev: "medium" },
];
const MARKER_CLASS: Record<Severity, string> = {
  critical: "bg-critical-solid",
  high: "bg-high-solid",
  medium: "bg-medium-solid",
  low: "bg-low-solid",
  info: "bg-info-solid",
};

export function ReportPreview() {
  return (
    <figure aria-label={`Example ${BRAND.name} report`} className="w-full max-w-[520px] overflow-hidden rounded-[14px] border border-line bg-surface shadow-[var(--shadow-dialog)]">
      <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
        <div className="min-w-0">
          <p className="text-[11px] leading-4 font-semibold tracking-[0.06em] text-ink-3 uppercase">Example report</p>
          <p className="mt-0.5 truncate text-[15px] font-semibold text-ink">Morning routine with FitFuel</p>
          <p className="text-[12px] text-ink-3">Instagram Reel · 0:58 · English</p>
        </div>
        <Badge tone="critical" icon={OctagonExclamationPoint} className="shrink-0">
          Fix first
        </Badge>
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-line px-5 py-3 text-[12px] text-ink-2">
        <span className="text-ink-3">Disclosure</span>
        <span className="inline-flex items-center gap-1.5">
          India (ASCI) <Badge tone="success">Clear</Badge>
        </span>
        <span className="inline-flex items-center gap-1.5">
          UK (ASA / CMA) <Badge tone="high">Not clear enough</Badge>
        </span>
      </div>
      <div className="px-5 pt-4">
        <div className="relative h-7 rounded-[6px] bg-surface-3" aria-hidden>
          {MARKERS.map((m) => (
            <span key={m.left} className={`absolute top-1.5 h-4 w-2.5 rounded-[3px] ${MARKER_CLASS[m.sev]}`} style={{ left: `${m.left}%` }} />
          ))}
        </div>
        <p className="mt-1.5 text-[11px] text-ink-3">Findings timeline · tap a finding to jump to that second</p>
      </div>
      <ul className="divide-y divide-line px-2 py-2">
        {FINDINGS.map((f) => (
          <li key={f.at + f.text} className="flex items-start gap-3 rounded-[8px] px-3 py-2.5">
            <span className="tabular mt-0.5 inline-flex h-6 shrink-0 items-center gap-1 rounded-[6px] bg-ink px-1.5 text-[11px] font-semibold text-surface">
              <Play className="size-2.5" fill="currentColor" aria-hidden />
              {f.at}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <SeverityBadge severity={f.sev} />
                <span className="text-[12px] text-ink-3">
                  {f.area} · {f.from}
                </span>
              </div>
              <p className="mt-1 text-[13px] leading-5 text-ink">{f.text}</p>
            </div>
          </li>
        ))}
      </ul>
      <figcaption className="flex items-center gap-2 border-t border-line bg-surface-2 px-5 py-3 text-[12px] text-ink-3">
        <CircleCheck className="size-3.5 text-success-fg" aria-hidden />
        Each policy finding cites an official platform or regulator page.
      </figcaption>
    </figure>
  );
}
