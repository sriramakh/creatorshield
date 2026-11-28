"use client";

import { CircleCheck, CircleQuestionMark, CircleX, Play, TriangleExclamationPoint } from "lucide-react";
import type { BriefCheck, BriefItemKind } from "@/lib/api";
import { fmtTime } from "@/lib/format";
import { Badge, type BadgeTone } from "../ui";

const KIND: Record<BriefItemKind, string> = {
  must_say: "Must say",
  must_not_say: "Must not say",
  required_hashtag: "Hashtag",
  required_mention: "Mention",
  competitor: "Competitor",
  required_disclosure: "Disclosure",
};

type Status = BriefCheck["items"][number]["status"];
const STATUS: Record<Status, { label: string; tone: BadgeTone; icon: typeof CircleCheck }> = {
  met: { label: "Met", tone: "success", icon: CircleCheck },
  missing: { label: "Not found", tone: "critical", icon: CircleX },
  violated: { label: "Found", tone: "critical", icon: TriangleExclamationPoint },
  unverified: { label: "Not checked", tone: "neutral", icon: CircleQuestionMark },
};

/** Requirement-by-requirement result of a brand brief; timestamps seek the video. */
export function BriefCheckTable({ check, onSeek }: { check: BriefCheck; onSeek?: (t: number) => void }) {
  return (
    <div className="space-y-2">
      <p className="text-[13px] text-ink-2">
        <span className="font-semibold text-ink">{check.met}</span> of {check.total} requirements met
        {check.brand && <> for {check.brand}</>}
        {check.unverified > 0 && <> · {check.unverified} can only be confirmed in the video</>}
        {check.scope === "caption_only" && <> · caption only, the video was not read</>}
      </p>
      <div className="scroll-thin overflow-x-auto rounded-[8px] border border-line">
        <table className="w-full text-[13px]">
          <caption className="sr-only">Brand brief requirements</caption>
          <thead className="bg-surface-2 text-left text-[12px] text-ink-3">
            <tr>
              <th scope="col" className="px-3 py-2 font-medium">
                Requirement
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Type
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Result
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Where
              </th>
            </tr>
          </thead>
          <tbody>
            {check.items.map((item, i) => {
              const s = STATUS[item.status];
              return (
                <tr key={`${item.kind}-${item.text}-${i}`} className="border-t border-line align-top">
                  <td className="px-3 py-2 font-medium text-ink">{item.text}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-ink-2">{KIND[item.kind] ?? item.kind}</td>
                  <td className="px-3 py-2">
                    <Badge tone={s.tone} icon={s.icon}>
                      {s.label}
                    </Badge>
                  </td>
                  <td className="px-3 py-2">
                    {item.where.length === 0 ? (
                      <span className="text-ink-3">—</span>
                    ) : (
                      <span className="flex flex-wrap gap-1">
                        {item.where.map((w, j) =>
                          w.timestamp != null && onSeek ? (
                            <button
                              key={j}
                              type="button"
                              onClick={() => onSeek(w.timestamp!)}
                              aria-label={`Play ${w.ref_id} from ${fmtTime(w.timestamp)}`}
                              className="tabular inline-flex h-6 items-center gap-1 rounded-[6px] border border-accent/30 bg-accent-soft px-1.5 text-[12px] font-medium text-accent hover:border-accent"
                            >
                              <Play className="size-2.5" fill="currentColor" aria-hidden />
                              {w.ref_id} · {fmtTime(w.timestamp)}
                            </button>
                          ) : (
                            <Badge key={j}>{w.ref_id}</Badge>
                          ),
                        )}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
