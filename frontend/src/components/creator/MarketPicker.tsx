"use client";

import type { MarketId } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { ChipGroup, Skeleton } from "../ui";

/** Audience markets from /api/config; at least one stays selected. */
export function MarketPicker({
  value,
  onChange,
  label = "Audience markets",
  describedBy,
}: {
  value: MarketId[];
  onChange: (value: MarketId[]) => void;
  label?: string;
  describedBy?: string;
}) {
  const { markets } = useWorkspace();
  if (!markets.length) return <Skeleton className="h-7 w-64" />;
  return (
    <div className="space-y-1.5" aria-describedby={describedBy}>
      <ChipGroup
        label={label}
        value={value}
        onChange={(next) => next.length > 0 && onChange(next)}
        options={markets.map((m) => ({ value: m.id, label: `${m.label} · ${m.regulator}` }))}
      />
      <p className="text-[12px] text-ink-3">
        Each market adds that regulator’s advisory rules and its view of which disclosure labels are clear. At least one is
        required.
      </p>
    </div>
  );
}
