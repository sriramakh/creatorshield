"use client";

import { CircleCheck, CircleExclamationPoint, OctagonExclamationPoint, type LucideIcon } from "lucide-react";
import { useId, useState, type KeyboardEvent } from "react";
import { cn } from "@/lib/cn";
import { niceTicks, useWidth } from "./useWidth";

export interface DayCounts {
  date: string;
  ready: number;
  review: number;
  fix_first: number;
}

/** Series in stack order, baseline first: the outcome that matters most sits on the axis. */
export const VERDICT_SERIES: { key: "fix_first" | "review" | "ready"; label: string; color: string; icon: LucideIcon }[] = [
  { key: "fix_first", label: "Fix first", color: "var(--chart-fix)", icon: OctagonExclamationPoint },
  { key: "review", label: "Review", color: "var(--chart-review)", icon: CircleExclamationPoint },
  { key: "ready", label: "No issues found", color: "var(--chart-ready)", icon: CircleCheck },
];

const H = 200;
const PAD = { top: 8, right: 4, bottom: 24, left: 32 };
const GAP = 2; // surface gap between stacked segments
const RADIUS = 4;

function fmtDay(date: string, long = false) {
  return new Date(`${date}T00:00:00Z`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    ...(long ? { weekday: "short" } : {}),
    timeZone: "UTC",
  });
}

function describe(d: DayCounts) {
  const total = d.ready + d.review + d.fix_first;
  if (!total) return `${fmtDay(d.date, true)}: no reviews`;
  return `${fmtDay(d.date, true)}: ${total} review${total === 1 ? "" : "s"} — ${d.fix_first} fix first, ${d.review} review, ${d.ready} no issues found`;
}

/** Rect with only the top corners rounded (data end), square at the baseline. */
function topRounded(x: number, y: number, w: number, h: number, r: number) {
  const rr = Math.min(r, w / 2, h);
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`;
}

/**
 * Reviews per day stacked by verdict. Hover or focus (arrow keys) shows one day's breakdown;
 * the table view lists every value.
 */
export function VerdictColumns({ days, label }: { days: DayCounts[]; label: string }) {
  const [wrapRef, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const titleId = useId();
  const n = days.length;
  const totals = days.map((d) => d.ready + d.review + d.fix_first);
  const ticks = niceTicks(Math.max(...totals, 0));
  const top = ticks[ticks.length - 1];
  const plotW = Math.max(width - PAD.left - PAD.right, 10);
  const plotH = H - PAD.top - PAD.bottom;
  const band = plotW / Math.max(n, 1);
  const barW = Math.max(2, Math.min(24, band * 0.68));
  const y = (v: number) => PAD.top + plotH - (v / top) * plotH;
  const sum = days.reduce((acc, d) => acc + d.ready + d.review + d.fix_first, 0);
  const labelIdx = n <= 1 ? [0] : [0, Math.floor((n - 1) / 2), n - 1];

  function onKey(e: KeyboardEvent) {
    if (!n) return;
    const cur = active ?? n - 1;
    let next: number | null = null;
    if (e.key === "ArrowRight") next = Math.min(n - 1, cur + 1);
    else if (e.key === "ArrowLeft") next = Math.max(0, cur - 1);
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = n - 1;
    if (next === null) return;
    e.preventDefault();
    setActive(next);
  }

  const a = active != null ? days[active] : null;
  const tipLeft = active != null ? PAD.left + band * active + band / 2 : 0;

  return (
    <figure className="min-w-0 space-y-3">
      <figcaption className="sr-only" id={titleId}>
        {label}. {sum} reviews in the period. Use the left and right arrow keys to read each day.
      </figcaption>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-ink-2" aria-label="Legend">
        {VERDICT_SERIES.map((s) => {
          const total = days.reduce((acc, d) => acc + d[s.key], 0);
          return (
            <li key={s.key} className="inline-flex items-center gap-1.5">
              <span className="size-2.5 rounded-[2px]" style={{ background: s.color }} aria-hidden />
              <s.icon className="size-3.5 text-ink-3" aria-hidden />
              {s.label}
              <span className="tabular text-ink-3">{total}</span>
            </li>
          );
        })}
      </ul>
      <div
        ref={wrapRef}
        tabIndex={0}
        role="group"
        aria-labelledby={titleId}
        aria-describedby={`${titleId}-live`}
        onKeyDown={onKey}
        onFocus={() => setActive((v) => v ?? n - 1)}
        onBlur={() => setActive(null)}
        onPointerLeave={() => setActive(null)}
        className="relative w-full min-w-0 overflow-hidden rounded-[6px] focus-visible:outline-offset-4"
      >
        <svg width={width} height={H} role="presentation" className="block overflow-visible">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeWidth={1} shapeRendering="crispEdges" />
              <text x={PAD.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-ink-3 text-[11px] tabular-nums">
                {t}
              </text>
            </g>
          ))}
          {days.map((d, i) => {
            const x = PAD.left + band * i + (band - barW) / 2;
            const segs = VERDICT_SERIES.map((s) => ({ s, v: d[s.key] })).filter((p) => p.v > 0);
            let acc = 0;
            return (
              <g key={d.date} opacity={active == null || active === i ? 1 : 0.45}>
                {segs.map(({ s, v }, j) => {
                  const y0 = y(acc);
                  acc += v;
                  const y1 = y(acc);
                  const isTop = j === segs.length - 1;
                  // Leave a 2px surface gap above every segment that has another on top of it.
                  const h = Math.max(1, y0 - y1 - (isTop ? 0 : GAP));
                  const yy = isTop ? y1 : y1 + GAP;
                  return isTop ? (
                    <path key={s.key} d={topRounded(x, yy, barW, h, RADIUS)} fill={s.color} />
                  ) : (
                    <rect key={s.key} x={x} y={yy} width={barW} height={h} fill={s.color} />
                  );
                })}
                {/* Hit target: the whole band, taller than the mark. */}
                <rect
                  x={PAD.left + band * i}
                  y={PAD.top}
                  width={band}
                  height={plotH}
                  fill="transparent"
                  onPointerEnter={() => setActive(i)}
                  onPointerMove={() => setActive(i)}
                />
              </g>
            );
          })}
          <line x1={PAD.left} x2={width - PAD.right} y1={y(0)} y2={y(0)} stroke="var(--line-strong)" strokeWidth={1} shapeRendering="crispEdges" />
          {labelIdx.map((i) =>
            days[i] ? (
              <text
                key={i}
                x={PAD.left + band * i + band / 2}
                y={H - 6}
                textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"}
                className="fill-ink-3 text-[11px]"
              >
                {fmtDay(days[i].date)}
              </text>
            ) : null,
          )}
        </svg>
        {a && (
          <div
            className="pointer-events-none absolute top-0 z-10 w-max min-w-40 -translate-x-1/2 rounded-[8px] border border-line bg-surface px-3 py-2 text-[12px] shadow-[var(--shadow-pop)]"
            style={{ left: Math.min(Math.max(tipLeft, 90), width - 90) }}
          >
            <div className="font-medium text-ink-2">{fmtDay(a.date, true)}</div>
            <ul className="mt-1 space-y-0.5">
              {[...VERDICT_SERIES].reverse().map((s) => (
                <li key={s.key} className="flex items-center gap-2">
                  <span className="h-0.5 w-3 rounded-full" style={{ background: s.color }} aria-hidden />
                  <span className="tabular font-semibold text-ink">{a[s.key]}</span>
                  <span className="text-ink-3">{s.label}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <p id={`${titleId}-live`} className="sr-only" aria-live="polite">
          {a ? describe(a) : ""}
        </p>
      </div>
      <details className="group text-[13px]">
        <summary className={cn("cursor-pointer rounded-[4px] text-accent select-none hover:underline")}>Show as a table</summary>
        <div className="scroll-thin mt-2 max-h-64 overflow-auto rounded-[8px] border border-line">
          <table className="w-full text-[13px]">
            <caption className="sr-only">{label}</caption>
            <thead className="sticky top-0 bg-surface-2 text-left text-[12px] text-ink-3">
              <tr>
                <th className="px-3 py-1.5 font-medium">Day</th>
                {[...VERDICT_SERIES].reverse().map((s) => (
                  <th key={s.key} className="px-3 py-1.5 text-right font-medium">
                    {s.label}
                  </th>
                ))}
                <th className="px-3 py-1.5 text-right font-medium">Total</th>
              </tr>
            </thead>
            <tbody>
              {days.map((d, i) => (
                <tr key={d.date} className="border-t border-line">
                  <td className="px-3 py-1.5 text-ink-2">{fmtDay(d.date, true)}</td>
                  {[...VERDICT_SERIES].reverse().map((s) => (
                    <td key={s.key} className="tabular px-3 py-1.5 text-right">
                      {d[s.key]}
                    </td>
                  ))}
                  <td className="tabular px-3 py-1.5 text-right font-medium">{totals[i]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
