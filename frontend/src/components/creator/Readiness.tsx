"use client";

import { ChevronRight, CircleCheck, CircleQuestionMark, CircleX, TriangleExclamationPoint, type LucideIcon } from "lucide-react";
import type { ChecklistItem, DisclosureStatus, MarketDisclosure, Readiness } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useWorkspace } from "@/lib/workspace";
import { Badge, TONE_SOFT, TONE_TEXT, VERDICT, type BadgeTone, type StatusTone } from "../ui";

const CHECK: Record<ChecklistItem["status"], { icon: LucideIcon; tone: StatusTone; word: string }> = {
  pass: { icon: CircleCheck, tone: "success", word: "Pass" },
  warn: { icon: TriangleExclamationPoint, tone: "medium", word: "Check" },
  fail: { icon: CircleX, tone: "critical", word: "Fix" },
  unknown: { icon: CircleQuestionMark, tone: "info", word: "Not checked" },
};

/** Verdict headline, counts and the checklist. Rows with findings call `onRow`. */
export function ReadinessPanel({
  readiness,
  onRow,
  compact = false,
  className,
}: {
  readiness: Readiness;
  onRow?: (item: ChecklistItem) => void;
  compact?: boolean;
  className?: string;
}) {
  const v = VERDICT[readiness.verdict];
  return (
    <section aria-label="Verdict" className={cn("overflow-hidden rounded-[10px] border border-line bg-surface", className)}>
      <div className={cn("flex items-start gap-3 border-b border-line", compact ? "px-4 py-3" : "px-5 py-4")}>
        <span className={cn("flex shrink-0 items-center justify-center rounded-full", TONE_SOFT[v.tone], TONE_TEXT[v.tone], compact ? "size-8" : "size-11")} aria-hidden>
          <v.icon className={compact ? "size-4" : "size-6"} strokeWidth={2} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-[11px] leading-4 font-semibold tracking-[0.06em] text-ink-3 uppercase">Verdict</div>
          <h2 className={cn("font-[650] tracking-tight", TONE_TEXT[v.tone], compact ? "text-[18px] leading-[26px]" : "text-[22px] leading-8")}>{readiness.headline}</h2>
          <p className="mt-0.5 text-[13px] text-ink-2">
            {readiness.blockers} to fix · {readiness.warnings} to check
          </p>
        </div>
      </div>
      <ul className="divide-y divide-line">
        {readiness.checklist.map((item) => {
          const c = CHECK[item.status];
          const clickable = !!onRow && item.finding_ids.length > 0;
          const body = (
            <>
              <c.icon className={cn("mt-0.5 size-4 shrink-0", TONE_TEXT[c.tone])} strokeWidth={2} aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium text-ink">
                  {item.label}
                  <span className="sr-only">: {c.word}</span>
                </span>
                <span className="block text-[13px] text-ink-2">{item.detail}</span>
              </span>
              {clickable && <ChevronRight className="mt-0.5 size-4 shrink-0 text-ink-3" aria-hidden />}
            </>
          );
          return (
            <li key={item.key}>
              {clickable ? (
                <button
                  type="button"
                  onClick={() => onRow(item)}
                  className={cn("flex w-full items-start gap-3 text-left hover:bg-surface-2 focus-visible:outline-offset-[-2px]", compact ? "px-4 py-2.5" : "px-5 py-3")}
                  aria-label={`${item.label}: ${c.word}. ${item.detail}. Show ${item.finding_ids.length} finding${item.finding_ids.length === 1 ? "" : "s"}`}
                >
                  {body}
                </button>
              ) : (
                <div className={cn("flex items-start gap-3", compact ? "px-4 py-2.5" : "px-5 py-3")}>{body}</div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export const DISCLOSURE_STATUS: Record<DisclosureStatus, { label: string; tone: BadgeTone; help: string }> = {
  clear: { label: "Clear", tone: "success", help: "A label this regulator treats as clear opens the caption." },
  buried: { label: "Buried", tone: "medium", help: "A clear label is present but not at the start of the caption." },
  unclear: { label: "Not clear enough", tone: "high", help: "The label used is not one this regulator treats as clear." },
  none: { label: "No label", tone: "neutral", help: "No disclosure label was found in the caption." },
};

/** One row per market: status of the caption's disclosure, with the regulator named. */
export function MarketStatusRow({ md, needed }: { md: MarketDisclosure; needed?: boolean }) {
  const { marketLabel } = useWorkspace();
  const entries = Object.entries(md.by_market);
  if (!entries.length) return null;
  return (
    <ul className="flex flex-wrap gap-2" aria-label="Disclosure by market">
      {entries.map(([id, m]) => {
        const s = DISCLOSURE_STATUS[m.status];
        const tone: BadgeTone = m.status === "none" && needed ? "critical" : s.tone;
        return (
          <li key={id} className="inline-flex items-center gap-1.5 text-[13px]" title={s.help}>
            <span className="text-ink-2">
              {marketLabel(id)} <span className="text-ink-3">({m.regulator})</span>
            </span>
            <Badge tone={tone}>{s.label}</Badge>
          </li>
        );
      })}
    </ul>
  );
}

/** Which labels each market treats as clear. */
export function MarketLabelTable({ md }: { md: MarketDisclosure }) {
  const { marketLabel } = useWorkspace();
  const markets = Object.keys(md.by_market);
  return (
    <div className="space-y-3">
      <MarketStatusRow md={md} />
      {md.labels.length === 0 ? (
        <p className="text-[13px] text-ink-3">No disclosure label was found in the caption.</p>
      ) : (
        <div className="scroll-thin overflow-x-auto rounded-[8px] border border-line">
          <table className="w-full text-[13px]">
            <caption className="sr-only">Disclosure labels found, by market</caption>
            <thead className="bg-surface-2 text-left text-[12px] text-ink-3">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">
                  Label found
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Position
                </th>
                {markets.map((m) => (
                  <th key={m} scope="col" className="px-3 py-2 font-medium">
                    {marketLabel(m)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {md.labels.map((l, i) => (
                <tr key={`${l.text}-${i}`} className="border-t border-line">
                  <td className="px-3 py-2 font-medium text-ink">
                    “{l.text}”
                    {l.denied && <span className="ml-1.5 text-[12px] font-normal text-critical-fg">negated</span>}
                  </td>
                  <td className="px-3 py-2 text-ink-2">{l.opening ? "Opens the caption" : "Later in the caption"}</td>
                  {markets.map((m) => {
                    const clear = l.clear_in.includes(m);
                    const unclear = l.unclear_in.includes(m);
                    return (
                      <td key={m} className="px-3 py-2">
                        {clear ? (
                          <Badge tone="success" icon={CircleCheck}>
                            Clear
                          </Badge>
                        ) : unclear ? (
                          <Badge tone="high" icon={TriangleExclamationPoint}>
                            Not treated as clear
                          </Badge>
                        ) : (
                          <span className="text-ink-3">—</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
