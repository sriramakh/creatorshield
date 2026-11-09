"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type AnalysisSummary } from "@/lib/api";
import { fmtDate, LANGUAGE_LABEL, PLATFORM_LABEL, SOURCE_LABEL } from "@/lib/format";
import { ShieldIcon, UploadIcon } from "./icons";
import { SystemStatusBanner } from "./SystemStatusBanner";
import { Card, RiskBadge, Skeleton, StatusBadge } from "./ui";

export function AnalysesDashboard() {
  const [rows, setRows] = useState<AnalysisSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .list()
      .then((r) => {
        setRows(r);
        setError(null);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while anything is in flight.
  const busy = rows?.some((r) => r.status === "queued" || r.status === "processing");
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, [busy, load]);

  const completed = rows?.filter((r) => r.status === "completed") ?? [];
  const needsAttention = completed.filter((r) => r.risk_level === "elevated" || r.risk_level === "high").length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Analyses</h1>
          <p className="mt-1 text-sm text-slate-500">
            Review Shorts and Reels for policy, monetization, disclosure and licensing risks before you publish.
          </p>
        </div>
      </div>

      <SystemStatusBanner />

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Videos analysed" value={rows ? completed.length : null} />
        <Stat label="Elevated or high risk" value={rows ? needsAttention : null} />
        <Stat label="In progress" value={rows ? rows.filter((r) => r.status === "queued" || r.status === "processing").length : null} />
      </div>

      <Card>
        {error && <div className="p-6 text-sm text-red-700">{error}</div>}
        {!error && rows === null && (
          <div className="space-y-3 p-6">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        )}
        {rows && rows.length === 0 && <EmptyState />}
        {rows && rows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                  <th className="px-5 py-3">Video</th>
                  <th className="px-5 py-3">Platform</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Heuristic risk</th>
                  <th className="px-5 py-3 text-right">Findings</th>
                  <th className="px-5 py-3 text-right">Created</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="group border-b border-slate-100 last:border-0 hover:bg-slate-50/70">
                    <td className="px-5 py-3.5">
                      <Link href={`/analyses/${r.id}`} className="block">
                        <div className="max-w-xs truncate font-medium text-slate-900 group-hover:text-brand-700">
                          {r.source_title?.trim() || r.caption?.trim().split("\n")[0] || "Untitled video"}
                        </div>
                        <div className="mt-0.5 text-xs text-slate-500">
                          {r.client_label && (
                            <span className="mr-1.5 font-medium text-slate-600" title="Client / account">
                              {r.client_label} ·
                            </span>
                          )}
                          {r.source !== "upload" && (
                            <span className="mr-1.5 rounded bg-slate-100 px-1.5 py-0.5 font-medium text-slate-600">
                              {SOURCE_LABEL[r.source]}
                              {r.analysis_mode === "cross_checked"
                                ? " · cross-checked"
                                : r.analysis_mode !== "full_video" && " · limited"}
                            </span>
                          )}
                          {r.duration_seconds != null && `${r.duration_seconds.toFixed(1)}s · `}
                          {LANGUAGE_LABEL[r.language]}
                          {r.mock_mode && <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 font-semibold text-amber-800">MOCK</span>}
                        </div>
                      </Link>
                    </td>
                    <td className="px-5 py-3.5 text-slate-700">{PLATFORM_LABEL[r.platform]}</td>
                    <td className="px-5 py-3.5"><StatusBadge a={r} /></td>
                    <td className="px-5 py-3.5"><RiskBadge level={r.risk_level} score={r.risk_score} /></td>
                    <td className="px-5 py-3.5 text-right tabular-nums text-slate-700">
                      {r.status === "completed" ? r.finding_count : "—"}
                    </td>
                    <td className="px-5 py-3.5 text-right text-xs text-slate-500">{fmtDate(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | null }) {
  return (
    <Card className="px-5 py-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value ?? <Skeleton className="mt-1 h-7 w-10" />}</div>
    </Card>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center px-6 py-16 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
        <ShieldIcon className="h-6 w-6" />
      </span>
      <h2 className="mt-4 text-base font-semibold">No analyses yet</h2>
      <p className="mt-1 max-w-sm text-sm text-slate-500">
        Upload a Short or Reel (up to 30 minutes) to get a timestamped policy-risk report with official policy references.
      </p>
      <Link
        href="/analyses/new"
        className="mt-5 inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
      >
        <UploadIcon className="h-4 w-4" /> Analyse a video
      </Link>
    </div>
  );
}
