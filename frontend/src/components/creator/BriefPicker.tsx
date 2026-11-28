"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, errorMessage, type Brief, type BriefInput } from "@/lib/api";
import { Field, Select } from "../ui";

export function briefCounts(b: BriefInput) {
  return [
    b.must_say.length && `${b.must_say.length} must say`,
    b.must_not_say.length && `${b.must_not_say.length} must not say`,
    b.required_hashtags.length && `${b.required_hashtags.length} hashtag${b.required_hashtags.length === 1 ? "" : "s"}`,
    b.required_mentions.length && `${b.required_mentions.length} mention${b.required_mentions.length === 1 ? "" : "s"}`,
    b.competitors.length && `${b.competitors.length} competitor${b.competitors.length === 1 ? "" : "s"}`,
    b.required_disclosure && `opens with “${b.required_disclosure}”`,
  ].filter(Boolean) as string[];
}

/** A compact read-out of what a brief asks for. */
export function BriefSummary({ brief }: { brief: BriefInput }) {
  const rows: [string, string[]][] = [
    ["Must say", brief.must_say],
    ["Must not say", brief.must_not_say],
    ["Hashtags", brief.required_hashtags.map((h) => `#${h.replace(/^#/, "")}`)],
    ["Mentions", brief.required_mentions.map((m) => `@${m.replace(/^@/, "")}`)],
    ["Competitors", brief.competitors],
    ["Disclosure", brief.required_disclosure ? [brief.required_disclosure] : []],
  ];
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 rounded-[8px] border border-line bg-surface-2 px-3 py-2.5 text-[13px]">
      {rows
        .filter(([, v]) => v.length)
        .map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-ink-3">{k}</dt>
            <dd className="min-w-0 text-ink">{v.join(", ")}</dd>
          </div>
        ))}
      {brief.notes && (
        <>
          <dt className="text-ink-3">Notes</dt>
          <dd className="text-ink-2">{brief.notes}</dd>
        </>
      )}
    </dl>
  );
}

/** Pick a saved brief (or none). Loads /api/briefs once. */
export function BriefPicker({
  value,
  onChange,
  onBriefs,
}: {
  value: string;
  onChange: (id: string, brief: Brief | null) => void;
  onBriefs?: (briefs: Brief[]) => void;
}) {
  const [briefs, setBriefs] = useState<Brief[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api
      .briefs()
      .then((b) => {
        setBriefs(b);
        onBriefs?.(b);
      })
      .catch((e: unknown) => setError(errorMessage(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once
  }, []);
  const picked = briefs?.find((b) => b.id === value) ?? null;
  return (
    <div className="space-y-2">
      <Field
        label="Brand brief"
        error={error}
        hint={
          <>
            Optional. The review checks the sponsor’s must-say lines, banned wording, hashtags and mentions.{" "}
            <Link href="/briefs?new=1" className="font-medium text-accent hover:underline">
              Create a brief
            </Link>
          </>
        }
      >
        {(p) => (
          <Select
            {...p}
            value={value}
            disabled={!briefs}
            onChange={(e) => onChange(e.target.value, briefs?.find((b) => b.id === e.target.value) ?? null)}
          >
            <option value="">{briefs ? "No brief" : "Loading briefs…"}</option>
            {briefs?.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
                {b.brand ? ` · ${b.brand}` : ""}
              </option>
            ))}
          </Select>
        )}
      </Field>
      {picked && <BriefSummary brief={picked} />}
    </div>
  );
}
