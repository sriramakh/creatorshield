"use client";

import { useEffect, useState } from "react";
import { api, type PolicyKB } from "@/lib/api";
import { ExternalIcon } from "./icons";
import { Banner, Card, Skeleton } from "./ui";

const GROUPS = [
  { key: "youtube", label: "YouTube", applies: "YouTube Shorts" },
  { key: "meta_all", label: "Meta Community Standards", applies: "Instagram Reels" },
  { key: "instagram", label: "Instagram", applies: "Instagram Reels" },
  { key: "india_advisory", label: "India advisory (ASCI)", applies: "Both platforms" },
];

export function PolicyLibrary() {
  const [kb, setKb] = useState<PolicyKB | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    api.policies().then(setKb).catch((e: Error) => setError(e.message));
  }, []);

  const q = query.toLowerCase();
  const match = (r: PolicyKB["rules"][number]) =>
    !q || [r.id, r.title, r.official_title, r.category, ...r.key_points].some((t) => t.toLowerCase().includes(q));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Policy library</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">
            The rules every finding is checked against. Each rule links to the official policy page and shows when its content was last
            verified. Rule IDs are CreatorShield identifiers — the platforms do not number their policies.
          </p>
        </div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search policies"
          className="w-64 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
        />
      </div>
      {error && <Banner tone="danger" title="Could not load policies">{error}</Banner>}
      {!kb && !error && <Skeleton className="h-64 w-full" />}
      {kb && (
        <>
          <p className="text-xs text-slate-500">
            Knowledge base version <strong>{kb.version}</strong> · {kb.rules.length} rules · verified {kb.verified_on}
          </p>
          {GROUPS.map((g) => {
            const rules = kb.rules.filter((r) => r.platform === g.key && match(r));
            if (rules.length === 0) return null;
            return (
              <section key={g.key}>
                <h2 className="text-sm font-semibold">
                  {g.label} <span className="font-normal text-slate-500">· applies to {g.applies}</span>
                </h2>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {rules.map((r) => (
                    <Card key={r.id} className="p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700">{r.id}</code>
                          <h3 className="mt-1.5 text-sm font-semibold">{r.title}</h3>
                        </div>
                        <span className="flex-none rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                          {r.category.replace(/_/g, " ")}
                        </span>
                      </div>
                      <ul className="mt-2 list-disc space-y-1 pl-4 text-[13px] text-slate-600">
                        {r.key_points.map((p, i) => <li key={i}>{p}</li>)}
                      </ul>
                      {r.quote && <blockquote className="mt-2 border-l-2 border-slate-300 pl-3 text-[13px] italic text-slate-600">“{r.quote}”</blockquote>}
                      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs">
                        <a href={r.official_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline">
                          {r.official_title}
                          <ExternalIcon className="h-3 w-3" />
                        </a>
                        <span className="text-slate-400">verified {r.verified_on}</span>
                      </div>
                    </Card>
                  ))}
                </div>
              </section>
            );
          })}
        </>
      )}
    </div>
  );
}
