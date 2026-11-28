"use client";

import { ChevronDown, ExternalLink, Play, UserCheck } from "lucide-react";
import { useState } from "react";
import { safeUrl, type Confidence, type Finding } from "@/lib/api";
import { cn } from "@/lib/cn";
import { CONFIDENCE_LEVEL, fmtTime, TYPE_HELP, TYPE_LABEL } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace";
import { Badge, SeverityBadge, SOLID } from "../ui";

const SOURCE_LABEL: Record<Finding["source"], string> = {
  ai: "AI review",
  deterministic: "Rule-based check",
  combined: "AI + rule check",
  provenance: "Provenance check",
};

const POLICY_PLATFORM_LABEL: Record<string, string> = {
  youtube: "YouTube",
  instagram: "Instagram",
  meta_all: "Meta",
  india_advisory: "India · ASCI",
  uk_advisory: "UK advisory",
  us_advisory: "US advisory",
};

/** Policy-library platform label, naming the market for regulator packs (e.g. "United States — FTC"). */
function usePolicyPlatformLabel() {
  const { markets } = useWorkspace();
  return (platform: string) => {
    const m = markets.find((x) => x.kb_platform === platform);
    return m ? `${m.label} — ${m.regulator}` : (POLICY_PLATFORM_LABEL[platform] ?? platform);
  };
}

function ConfidenceMeter({ confidence }: { confidence: Confidence }) {
  const level = CONFIDENCE_LEVEL[confidence];
  return (
    <span className="inline-flex items-center gap-1.5 text-[12px] text-ink-3" title="Model or rule confidence in this finding">
      <span className="flex items-end gap-0.5" aria-hidden>
        {[1, 2, 3].map((i) => (
          <span key={i} className={cn("w-1 rounded-[1px]", i <= level ? "bg-ink-2" : "bg-line-strong")} style={{ height: 4 + i * 3 }} />
        ))}
      </span>
      {confidence[0].toUpperCase() + confidence.slice(1)} confidence
    </span>
  );
}

/** One finding: severity first, then what, where (seekable), why and what to do. */
export function FindingCard({
  finding: f,
  onSeek,
  highlighted,
}: {
  finding: Finding;
  onSeek: (t: number) => void;
  highlighted?: boolean;
}) {
  const [open, setOpen] = useState(f.severity !== "info" && f.rights_status == null);
  const policyLabel = usePolicyPlatformLabel();
  const notCounted = f.rights_status != null;
  const bodyId = `finding-body-${f.id}`;

  return (
    <article
      id={`finding-${f.id}`}
      aria-label={`${f.severity} finding: ${f.title}`}
      className={cn(
        "relative scroll-mt-24 overflow-hidden rounded-[10px] border border-line bg-surface",
        highlighted && "highlight-flash",
        notCounted && "bg-surface-2",
      )}
    >
      <span aria-hidden className={cn("absolute inset-y-0 left-0 w-[3px]", SOLID[f.severity], notCounted && "opacity-40")} />
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={bodyId}
        className="flex w-full items-start gap-3 px-4 pt-3.5 pb-2 text-left focus-visible:outline-offset-[-2px]"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <SeverityBadge severity={f.severity} />
            <Badge title={TYPE_HELP[f.finding_type]}>{TYPE_LABEL[f.finding_type]}</Badge>
            <Badge>{f.category_label}</Badge>
            <Badge tone={f.source === "deterministic" ? "neutral" : "accent"} title={f.source === "combined" ? "Flagged by the AI review and independently by a rule-based check" : undefined}>
              {SOURCE_LABEL[f.source]}
            </Badge>
            {f.rights_status === "covered" && <Badge tone="success">Covered by rights ledger · not counted</Badge>}
            {f.rights_status === "duplicate" && <Badge>Duplicate · not counted</Badge>}
          </div>
          <h4 className="mt-2 text-[15px] leading-[22px] font-semibold text-ink">{f.title}</h4>
        </div>
        <ChevronDown className={cn("mt-1 size-4 shrink-0 text-ink-3 transition-transform duration-[180ms]", open && "rotate-180")} aria-hidden />
      </button>

      {f.rights_note && <p className="px-4 pb-1 text-[13px] text-ink-2">{f.rights_note}</p>}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 pb-3">
        {f.start_seconds != null && (
          <button
            type="button"
            onClick={() => onSeek(f.start_seconds!)}
            title="Play from here"
            className="tabular inline-flex h-7 items-center gap-1.5 rounded-[6px] bg-ink px-2 text-[12px] font-semibold text-surface hover:opacity-90"
          >
            <Play className="size-3" fill="currentColor" aria-hidden />
            {fmtTime(f.start_seconds)}
            {f.end_seconds != null && f.end_seconds !== f.start_seconds && `–${fmtTime(f.end_seconds)}`}
          </button>
        )}
        <ConfidenceMeter confidence={f.confidence} />
        {f.requires_human_review && (
          <span className="inline-flex items-center gap-1 text-[12px] font-medium text-ink-2">
            <UserCheck className="size-3.5 text-accent" aria-hidden /> Needs human review
          </span>
        )}
      </div>

      {open && (
        <div id={bodyId} className="space-y-4 border-t border-line px-4 py-4 text-sm">
          <p className="max-w-[72ch] leading-[22px] text-ink-2">{f.explanation}</p>

          {f.evidence.length > 0 && (
            <section>
              <h5 className="text-[11px] leading-4 font-semibold tracking-[0.06em] text-ink-3 uppercase">Evidence</h5>
              <ul className="mt-2 space-y-2">
                {f.evidence.map((e, i) => {
                  const href = safeUrl(e.url);
                  const chip = (
                    <>
                      <span className="font-mono">{e.ref_id}</span>
                      {e.timestamp != null && <span className="tabular">· {fmtTime(e.timestamp)}</span>}
                    </>
                  );
                  return (
                    <li key={i} className="flex gap-2.5 text-[13px]">
                      {e.timestamp != null ? (
                        <button
                          type="button"
                          onClick={() => onSeek(e.timestamp!)}
                          aria-label={`Play evidence ${e.ref_id} from ${fmtTime(e.timestamp)}`}
                          className="inline-flex h-6 shrink-0 items-center gap-1 rounded-[6px] border border-accent/30 bg-accent-soft px-1.5 text-[12px] font-medium text-accent hover:border-accent"
                        >
                          <Play className="size-2.5" fill="currentColor" aria-hidden />
                          {chip}
                        </button>
                      ) : (
                        <span className="inline-flex h-6 shrink-0 items-center gap-1 rounded-[6px] border border-line bg-surface-2 px-1.5 text-[12px] font-medium text-ink-2">
                          {chip}
                        </span>
                      )}
                      <span className="min-w-0 pt-0.5 text-ink-2">
                        {e.detail}
                        {href && (
                          <a href={href} target="_blank" rel="noopener noreferrer" className="ml-1.5 inline-flex items-center gap-1 font-medium break-all text-accent hover:underline">
                            {href.replace(/^https?:\/\//, "").slice(0, 60)}
                            <ExternalLink className="size-3 shrink-0" aria-hidden />
                          </a>
                        )}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          {f.context_exception && (
            <section className="rounded-[8px] border border-low-line bg-low-bg px-3 py-2.5">
              <h5 className="text-[12px] font-semibold text-low-fg">Context to consider</h5>
              <p className="mt-0.5 text-[13px] text-ink-2">{f.context_exception}</p>
            </section>
          )}

          <section className="rounded-[8px] border border-success-line bg-success-bg px-3 py-2.5">
            <h5 className="text-[12px] font-semibold text-success-fg">Suggested fix</h5>
            <p className="mt-0.5 text-[13px] text-ink">{f.suggested_action}</p>
          </section>

          {f.category !== "brand_brief" && (
          <section>
            <h5 className="text-[11px] leading-4 font-semibold tracking-[0.06em] text-ink-3 uppercase">Policy reference</h5>
            {f.policies.length > 0 ? (
              <ul className="mt-2 space-y-1.5">
                {f.policies.map((p) => (
                  <li key={p.id} className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[13px]">
                    <code className="rounded-[4px] bg-surface-3 px-1.5 py-0.5 font-mono text-[11px] text-ink-2">{p.id}</code>
                    <span className="text-[12px] text-ink-3">{policyLabel(p.platform)}</span>
                    <a
                      href={safeUrl(p.official_url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 font-medium text-accent hover:underline"
                    >
                      {p.official_title}
                      <ExternalLink className="size-3" aria-hidden />
                    </a>
                    <span className="text-[12px] text-ink-3">verified {p.verified_on}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-[13px] text-ink-3">No verified policy reference is attached. Treat this as advisory.</p>
            )}
          </section>
          )}

          {f.validation_notes.length > 0 && (
            <details className="text-[12px] text-ink-3">
              <summary className="cursor-pointer select-none hover:text-ink-2">Validation notes ({f.validation_notes.length})</summary>
              <ul className="mt-1 list-disc pl-5">
                {f.validation_notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </article>
  );
}
