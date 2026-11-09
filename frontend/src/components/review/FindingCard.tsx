"use client";

import { useState } from "react";
import type { Finding } from "@/lib/api";
import { fmtTime, SEVERITY_STYLE, TYPE_HELP, TYPE_LABEL } from "@/lib/format";
import { ClockIcon, ExternalIcon, PlayIcon, UserCheckIcon } from "../icons";
import { ConfidenceMeter, Pill, SeverityBadge } from "../ui";

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
};

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
  const hasTime = f.start_seconds != null;
  const notCounted = f.rights_status != null;

  return (
    <article
      id={`finding-${f.id}`}
      className={`rounded-xl border border-l-4 border-slate-200 bg-white ${SEVERITY_STYLE[f.severity].bar} ${
        highlighted ? "highlight-flash" : ""
      } ${notCounted ? "opacity-70" : ""}`}
    >
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-start gap-3 px-4 pt-4 text-left">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <SeverityBadge severity={f.severity} />
            <Pill title={TYPE_HELP[f.finding_type]}>{TYPE_LABEL[f.finding_type]}</Pill>
            <Pill>{f.category_label}</Pill>
            <Pill
              className={f.source === "deterministic" ? "" : "border-brand-100 bg-brand-50 text-brand-700"}
              title={f.source === "combined" ? "Flagged by the AI review and independently by a rule-based check" : undefined}
            >
              {SOURCE_LABEL[f.source]}
            </Pill>
            {f.rights_status === "covered" && (
              <Pill className="border-emerald-200 bg-emerald-50 text-emerald-800">Covered by rights ledger · not counted</Pill>
            )}
            {f.rights_status === "duplicate" && <Pill>Duplicate · not counted</Pill>}
          </div>
          <h3 className="mt-2 text-[15px] font-semibold leading-snug text-slate-900">{f.title}</h3>
        </div>
        <span className="mt-1 text-slate-400">{open ? "−" : "+"}</span>
      </button>

      {f.rights_note && <p className="px-4 pt-2 text-[13px] text-slate-600">{f.rights_note}</p>}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 pt-2 pb-3">
        {hasTime && (
          <button
            type="button"
            onClick={() => onSeek(f.start_seconds!)}
            className="inline-flex items-center gap-1.5 rounded-md bg-slate-900 px-2 py-1 text-[11px] font-semibold text-white hover:bg-slate-700"
          >
            <PlayIcon className="h-3 w-3" />
            {fmtTime(f.start_seconds)}
            {f.end_seconds != null && f.end_seconds !== f.start_seconds && `–${fmtTime(f.end_seconds)}`}
          </button>
        )}
        <ConfidenceMeter confidence={f.confidence} />
        {f.requires_human_review && (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-violet-700">
            <UserCheckIcon className="h-3.5 w-3.5" /> Human review required
          </span>
        )}
      </div>

      {open && (
        <div className="space-y-4 border-t border-slate-100 px-4 py-4 text-sm">
          <p className="leading-relaxed text-slate-700">{f.explanation}</p>

          {f.evidence.length > 0 && (
            <section>
              <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Evidence</h4>
              <ul className="mt-1.5 space-y-1.5">
                {f.evidence.map((e, i) => (
                  <li key={i} className="flex gap-2 text-[13px]">
                    <code className="h-fit rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700">{e.ref_id}</code>
                    {e.timestamp != null && (
                      <button
                        type="button"
                        onClick={() => onSeek(e.timestamp!)}
                        className="inline-flex h-fit items-center gap-1 text-[11px] font-semibold text-brand-700 hover:underline"
                      >
                        <ClockIcon className="h-3 w-3" />
                        {fmtTime(e.timestamp)}
                      </button>
                    )}
                    <span className="text-slate-600">
                      {e.detail}
                      {e.url && (
                        <a
                          href={e.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="ml-1.5 inline-flex items-center gap-1 break-all font-medium text-brand-700 hover:underline"
                        >
                          {e.url.replace(/^https?:\/\//, "").slice(0, 60)}
                          <ExternalIcon className="h-3 w-3 flex-none" />
                        </a>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {f.context_exception && (
            <section className="rounded-lg bg-sky-50 px-3 py-2.5">
              <h4 className="text-[11px] font-semibold uppercase tracking-wide text-sky-800">Context consideration</h4>
              <p className="mt-1 text-[13px] text-sky-900">{f.context_exception}</p>
            </section>
          )}

          <section className="rounded-lg bg-emerald-50 px-3 py-2.5">
            <h4 className="text-[11px] font-semibold uppercase tracking-wide text-emerald-800">Suggested action</h4>
            <p className="mt-1 text-[13px] text-emerald-950">{f.suggested_action}</p>
          </section>

          <section>
            <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Policy reference</h4>
            {f.policies.length > 0 ? (
              <ul className="mt-1.5 space-y-1.5">
                {f.policies.map((p) => (
                  <li key={p.id} className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[13px]">
                    <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700">{p.id}</code>
                    <span className="text-[11px] font-medium text-slate-500">{POLICY_PLATFORM_LABEL[p.platform] ?? p.platform}</span>
                    <a
                      href={p.official_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline"
                    >
                      {p.official_title}
                      <ExternalIcon className="h-3 w-3" />
                    </a>
                    <span className="text-[11px] text-slate-400">verified {p.verified_on}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-[13px] text-slate-500">No verified policy reference attached — treat as advisory.</p>
            )}
          </section>

          {f.validation_notes.length > 0 && (
            <details className="text-[12px] text-slate-500">
              <summary className="cursor-pointer select-none">Validation notes ({f.validation_notes.length})</summary>
              <ul className="mt-1 list-disc pl-5">
                {f.validation_notes.map((n, i) => <li key={i}>{n}</li>)}
              </ul>
            </details>
          )}
        </div>
      )}
    </article>
  );
}
