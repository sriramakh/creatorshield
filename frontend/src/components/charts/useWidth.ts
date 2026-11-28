"use client";

import { useEffect, useRef, useState } from "react";

/** Width of an element in CSS px, kept current with a ResizeObserver. */
export function useWidth<T extends HTMLElement>(fallback = 640) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

/** Round a max up to a clean axis top and return 3–5 integer ticks. */
export function niceTicks(max: number): number[] {
  if (max <= 0) return [0, 1];
  const raw = max / 4;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const s = Math.max(1, Math.round(step));
  const top = Math.ceil(max / s) * s;
  const out: number[] = [];
  for (let v = 0; v <= top; v += s) out.push(v);
  return out;
}
