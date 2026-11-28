"use client";

import { useWidth } from "./useWidth";

export interface BarItem {
  key: string;
  label: string;
  value: number;
  /** Secondary text after the value, e.g. "in 3 reviews". */
  note?: string;
}

const ROW = 30;
const BAR = 10;
const RADIUS = 4;

/** Rect rounded only at the data end (right), square at the baseline. */
function endRounded(x: number, y: number, w: number, h: number, r: number) {
  const rr = Math.min(r, w, h / 2);
  return `M${x},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h - rr}Q${x + w},${y + h} ${x + w - rr},${y + h}H${x}Z`;
}

/**
 * Ranked horizontal bars for one series (one hue: the accent). Every value is printed at the
 * bar tip, so the chart is its own table; the SVG carries a text summary for screen readers.
 */
export function BarList({ items, label, unit }: { items: BarItem[]; label: string; unit: string }) {
  const [ref, width] = useWidth<HTMLDivElement>(480);
  const sorted = [...items].sort((a, b) => b.value - a.value);
  const max = Math.max(...sorted.map((i) => i.value), 1);
  // Narrow screens put the label on its own line above the bar, so text never collides.
  const stacked = width < 440;
  const row = stacked ? 44 : ROW;
  const labelW = stacked ? 0 : Math.min(180, Math.max(110, width * 0.38));
  const valueW = 112;
  const barMax = Math.max(width - labelW - valueW, 20);
  const h = sorted.length * row;
  const summary = `${label}: ${sorted.map((i) => `${i.label} ${i.value} ${unit}${i.note ? ` (${i.note})` : ""}`).join("; ")}`;

  return (
    <div ref={ref} className="w-full min-w-0 overflow-hidden">
      <svg width={width} height={h} role="img" aria-label={summary} className="block">
        <title>{label}</title>
        <desc>{summary}</desc>
        {sorted.map((item, i) => {
          const y = i * row;
          const w = item.value > 0 ? Math.max(2, (item.value / max) * barMax) : 0;
          const cy = stacked ? y + 30 : y + ROW / 2;
          const maxChars = stacked ? 48 : 26;
          return (
            <g key={item.key}>
              <text x={0} y={stacked ? y + 12 : cy} dy="0.32em" className="fill-ink-2 text-[13px]">
                {item.label.length > maxChars ? `${item.label.slice(0, maxChars - 1)}…` : item.label}
              </text>
              <line x1={labelW} x2={labelW} y1={cy - 9} y2={cy + 9} stroke="var(--line-strong)" strokeWidth={1} shapeRendering="crispEdges" />
              {w > 0 && <path d={endRounded(labelW, cy - BAR / 2, w, BAR, RADIUS)} fill="var(--accent)" />}
              <text x={labelW + w + 8} y={cy} dy="0.32em" className="fill-ink text-[13px] font-semibold tabular-nums">
                {item.value}
                {item.note && <tspan className="fill-ink-3 font-normal"> {item.note}</tspan>}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
