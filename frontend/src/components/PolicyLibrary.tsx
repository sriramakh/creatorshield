"use client";

import { BadgeCheck, ExternalLink, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, errorMessage, safeUrl, type PolicyKB } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { PageContainer } from "./shell/AppShell";
import { Badge, Card, ChipGroup, EmptyState, ErrorNotice, Input, PageHeader, Skeleton } from "./ui";

const GROUPS = [
  { key: "youtube", label: "YouTube", applies: "YouTube Shorts" },
  { key: "meta_all", label: "Meta Community Standards", applies: "Instagram Reels" },
  { key: "instagram", label: "Instagram", applies: "Instagram Reels" },
];

type Group = { key: string; label: string; applies: string; market?: boolean };

/**
 * Platform groups first, then one group per audience market (its regulator pack, labelled from
 * /api/config), then anything the library adds later under its raw key.
 */
function groupsFor(kb: PolicyKB, markets: { id: string; label: string; regulator: string; kb_platform: string }[]): Group[] {
  const marketGroups: Group[] = markets.map((m) => ({
    key: m.kb_platform,
    label: `${m.label} — ${m.regulator}`,
    applies: `reviews that select ${m.label}`,
    market: true,
  }));
  const known = [...GROUPS, ...marketGroups];
  const extra = [...new Set(kb.rules.map((r) => r.platform))]
    .filter((p) => !known.some((g) => g.key === p))
    .map((p) => ({ key: p, label: p.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()), applies: "See each rule" }));
  return [...known, ...extra].filter((g) => kb.rules.some((r) => r.platform === g.key));
}

export function PolicyLibrary() {
  const [kb, setKb] = useState<PolicyKB | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [groups, setGroups] = useState<string[]>([]);
  const { markets } = useWorkspace();

  useEffect(() => {
    api
      .policies()
      .then(setKb)
      .catch((e: unknown) => setError(errorMessage(e)));
  }, []);

  const q = query.trim().toLowerCase();
  const visible = useMemo(() => {
    if (!kb) return [];
    return groupsFor(kb, markets)
      .filter((g) => groups.length === 0 || groups.includes(g.key))
      .map((g) => ({
      ...g,
      rules: kb.rules.filter(
        (r) => r.platform === g.key && (!q || [r.id, r.title, r.official_title, r.category, ...r.key_points].some((t) => t.toLowerCase().includes(q))),
      ),
    }));
  }, [kb, groups, q, markets]);
  const total = visible.reduce((n, g) => n + g.rules.length, 0);

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        title="Policy library"
        description="The rules every finding is checked against. Each links to the official page and shows when it was last verified. Rule IDs are our own identifiers; the platforms do not number their policies."
      />
      {error && <ErrorNotice title="Could not load the policy library" message={error} />}
      {!kb && !error && <Skeleton className="h-80 w-full rounded-[10px]" />}
      {kb && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative w-full sm:w-80">
              <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
              <label htmlFor="policy-search" className="sr-only">
                Search policies
              </label>
              <Input id="policy-search" type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search rules, IDs and key points" className="pl-8" />
            </div>
            <ChipGroup
              label="Filter by source"
              value={groups}
              onChange={setGroups}
              options={groupsFor(kb, markets).map((g) => ({ value: g.key, label: g.label, count: kb.rules.filter((r) => r.platform === g.key).length }))}
            />
          </div>
          <p className="text-[13px] text-ink-3">
            Library version <span className="font-medium text-ink-2">{kb.version}</span> · {kb.rules.length} rules · verified {kb.verified_on}
            {(q || groups.length > 0) && <> · showing {total}</>}
          </p>
          {total === 0 && (
            <Card>
              <EmptyState icon={<Search />} title="No rules match" description="Try a different word, or clear the source filter." />
            </Card>
          )}
          {visible.map((g) =>
            g.rules.length === 0 ? null : (
              <section key={g.key} aria-labelledby={`policy-${g.key}`} className="space-y-3">
                <div>
                  <h2 id={`policy-${g.key}`} className="flex flex-wrap items-baseline gap-x-2 text-[18px] leading-[26px] font-semibold">
                    {g.label}
                    <span className="text-[13px] font-normal text-ink-3">applies to {g.applies}</span>
                  </h2>
                  {g.market && (
                    <p className="mt-0.5 text-[13px] text-ink-3">
                      Advisory guidance, cited to the regulator’s official pages. It applies only to reviews and caption checks that
                      select this market.
                    </p>
                  )}
                </div>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  {g.rules.map((r) => (
                    <Card key={r.id} className="flex min-w-0 flex-col p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <code className="rounded-[4px] bg-surface-3 px-1.5 py-0.5 font-mono text-[11px] text-ink-2">{r.id}</code>
                          <h3 className="mt-1.5 text-[15px] leading-[22px] font-semibold">{r.title}</h3>
                        </div>
                        <Badge className="shrink-0">{r.category.replace(/_/g, " ")}</Badge>
                      </div>
                      <ul className="mt-2 list-disc space-y-1 pl-4 text-[13px] break-words text-ink-2">
                        {r.key_points.map((p, i) => (
                          <li key={i}>{p}</li>
                        ))}
                      </ul>
                      {r.quote && <blockquote className="mt-2 border-l-2 border-line-strong pl-3 text-[13px] text-ink-2 italic">“{r.quote}”</blockquote>}
                      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-3 text-[13px]">
                        <a href={safeUrl(r.official_url)} target="_blank" rel="noopener noreferrer" className="inline-flex min-w-0 items-center gap-1 font-medium text-accent hover:underline">
                          <span className="truncate">{r.official_title}</span>
                          <ExternalLink className="size-3.5 shrink-0" aria-hidden />
                        </a>
                        <span className="inline-flex items-center gap-1 text-[12px] text-ink-3">
                          <BadgeCheck className="size-3.5 text-success-fg" aria-hidden />
                          Verified {r.verified_on}
                        </span>
                      </div>
                    </Card>
                  ))}
                </div>
              </section>
            ),
          )}
        </>
      )}
    </PageContainer>
  );
}
