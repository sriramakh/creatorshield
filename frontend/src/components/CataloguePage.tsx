"use client";

import Link from "next/link";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { addToCatalogue, api, type CatalogueEntry, type Platform, type ProvenanceStatus } from "@/lib/api";
import { fmtBytes, fmtDay, fmtUsd, PLATFORM_LABEL } from "@/lib/format";
import { CheckIcon, TrashIcon, UploadIcon } from "./icons";
import { Banner, Card, Skeleton } from "./ui";

const ACCEPT = ".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm";
const MAX_MB = 200;

const SERVICE_LABEL: Record<string, string> = {
  music_id: "Song identification",
  web_detection: "Web image search",
};

type ItemStatus = "pending" | "uploading" | "added" | "duplicate" | "error";
interface QueueItem {
  file: File;
  status: ItemStatus;
  progress: number;
  message?: string;
}

export function CataloguePage() {
  const [entries, setEntries] = useState<CatalogueEntry[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [status, setStatus] = useState<ProvenanceStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [owner, setOwner] = useState("all");

  const load = useCallback(() => {
    api
      .catalogue()
      .then((r) => {
        setEntries(r);
        setLoadError(null);
      })
      .catch((e: Error) => setLoadError(e.message));
    api
      .provenanceStatus()
      .then((s) => {
        setStatus(s);
        setStatusError(null);
      })
      .catch((e: Error) => setStatusError(e.message));
  }, []);
  useEffect(load, [load]);

  const owners = [...new Set((entries ?? []).map((e) => e.owner_label))].sort((a, b) => a.localeCompare(b));
  const shown = (entries ?? []).filter((e) => owner === "all" || e.owner_label === owner);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Catalogue</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-500">
          Index past posts so new videos are checked for reposts and for the same footage under a different client. Only a
          fingerprint is kept — the file is discarded. No AI or paid calls.
        </p>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[1fr_360px]">
        <BulkAdd onDone={load} />
        <ServicesCard status={status} error={statusError} />
      </div>

      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="text-base font-semibold">
            Indexed videos {entries && <span className="text-slate-400">({shown.length})</span>}
          </h2>
          {owners.length > 1 && (
            <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
              Client / account
              <select
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs font-medium text-slate-700"
              >
                <option value="all">All clients</option>
                {owners.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </label>
          )}
        </div>
        {loadError && <Banner tone="danger" title="Could not load the catalogue">{loadError}</Banner>}
        <Card>
          {!entries && !loadError && (
            <div className="space-y-3 p-6">
              {[0, 1, 2].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          )}
          {entries && entries.length === 0 && (
            <p className="p-6 text-sm text-slate-600">
              Nothing indexed yet. Reviewed videos are added automatically; add past posts above to compare against them too.
            </p>
          )}
          {entries && entries.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                    <th className="px-4 py-3">Video</th>
                    <th className="px-4 py-3">Client / account</th>
                    <th className="px-4 py-3">Source</th>
                    <th className="px-4 py-3 text-right">Length</th>
                    <th className="px-4 py-3 text-right">Frames</th>
                    <th className="px-4 py-3">Audio</th>
                    <th className="px-4 py-3">Expires</th>
                    <th className="px-4 py-3 text-right"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((e) => <EntryRow key={e.id} entry={e} onChange={load} />)}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </section>
    </div>
  );
}

function EntryRow({ entry: e, onChange }: { entry: CatalogueEntry; onChange: () => void }) {
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await api.removeCatalogueEntry(e.id);
      onChange();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <tr className="border-b border-slate-100 last:border-0">
      <td className="px-4 py-3">
        <div className="max-w-xs truncate font-medium text-slate-900" title={e.title ?? undefined}>{e.title || "Untitled"}</div>
        {e.platform && <div className="text-xs text-slate-500">{PLATFORM_LABEL[e.platform]}</div>}
      </td>
      <td className="px-4 py-3 text-slate-700">{e.owner_label}</td>
      <td className="px-4 py-3">
        {e.source === "analysis" ? (
          e.analysis_id ? (
            <Link href={`/analyses/${e.analysis_id}`} className="rounded bg-brand-50 px-1.5 py-0.5 text-xs font-medium text-brand-700 hover:underline">
              Reviewed video
            </Link>
          ) : (
            <span className="rounded bg-brand-50 px-1.5 py-0.5 text-xs font-medium text-brand-700">Reviewed video</span>
          )
        ) : (
          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-700">Indexed post</span>
        )}
      </td>
      <td className="px-4 py-3 text-right tabular-nums text-slate-700">{e.duration_seconds.toFixed(1)}s</td>
      <td className="px-4 py-3 text-right tabular-nums text-slate-700">{e.frames_hashed}</td>
      <td className="px-4 py-3 text-slate-700">{e.has_audio ? "Yes" : "No"}</td>
      <td className="px-4 py-3 text-xs text-slate-500">{fmtDay(e.expires_at)}</td>
      <td className="px-4 py-3 text-right">
        {confirm ? (
          <span className="inline-flex items-center gap-1 text-xs">
            <button
              type="button"
              disabled={busy}
              onClick={remove}
              className="rounded bg-red-600 px-2 py-1 font-semibold text-white hover:bg-red-700 disabled:bg-red-300"
            >
              Delete
            </button>
            <button type="button" onClick={() => setConfirm(false)} className="px-1 text-slate-600">
              Cancel
            </button>
          </span>
        ) : (
          <button
            type="button"
            onClick={() => setConfirm(true)}
            title="Remove this fingerprint from the catalogue"
            aria-label={`Delete ${e.title || "untitled"} from the catalogue`}
            className="inline-flex items-center rounded-lg p-1.5 text-slate-400 hover:text-red-600"
          >
            <TrashIcon className="h-4 w-4" />
          </button>
        )}
        {error && <div className="mt-1 text-xs text-red-700" role="alert">{error}</div>}
      </td>
    </tr>
  );
}

function BulkAdd({ onDone }: { onDone: () => void }) {
  const [ownerLabel, setOwnerLabel] = useState("");
  const [platform, setPlatform] = useState<Platform | "">("");
  const [items, setItems] = useState<QueueItem[]>([]);
  const [fileKey, setFileKey] = useState(0);
  const [running, setRunning] = useState(false);
  const runningRef = useRef(false);

  // Routes stay mounted (hidden) after navigation; start clean on the next visit.
  useLayoutEffect(
    () => () => {
      if (runningRef.current) return;
      setOwnerLabel("");
      setPlatform("");
      setItems([]);
      setFileKey((k) => k + 1);
    },
    [],
  );

  const update = (i: number, patch: Partial<QueueItem>) =>
    setItems((prev) => prev.map((it, j) => (j === i ? { ...it, ...patch } : it)));

  function pick(list: FileList | null) {
    setItems(
      Array.from(list ?? []).map((file): QueueItem => {
        const ext = file.name.toLowerCase().split(".").pop() ?? "";
        if (!["mp4", "mov", "webm"].includes(ext))
          return { file, status: "error", progress: 0, message: "Only MP4, MOV and WebM are supported." };
        if (file.size > MAX_MB * 1024 * 1024) return { file, status: "error", progress: 0, message: `Larger than ${MAX_MB} MB.` };
        return { file, status: "pending", progress: 0 };
      }),
    );
  }

  async function run() {
    runningRef.current = true;
    setRunning(true);
    const label = ownerLabel.trim();
    for (const [i, it] of items.entries()) {
      if (it.status !== "pending") continue;
      update(i, { status: "uploading", progress: 0 });
      const form = new FormData();
      form.append("file", it.file);
      form.append("owner_label", label);
      if (platform) form.append("platform", platform);
      form.append("title", it.file.name.replace(/\.[^.]+$/, "").slice(0, 300));
      try {
        const res = await addToCatalogue(form, (p) => update(i, { progress: p }));
        update(i, {
          status: res.duplicate ? "duplicate" : "added",
          progress: 1,
          message: res.duplicate
            ? "Already indexed for this client."
            : res.truncated
              ? "Added — only the first part was fingerprinted."
              : undefined,
        });
      } catch (e) {
        update(i, { status: "error", message: (e as Error).message });
      }
    }
    runningRef.current = false;
    setRunning(false);
    setFileKey((k) => k + 1);
    onDone();
  }

  const pending = items.filter((it) => it.status === "pending").length;

  return (
    <Card className="space-y-4 p-5" label="Add past posts">
      <h2 className="text-sm font-semibold">Add past posts</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="catalogue-owner" className="text-xs font-semibold text-slate-700">Client / account</label>
          <input
            id="catalogue-owner"
            value={ownerLabel}
            onChange={(e) => setOwnerLabel(e.target.value.slice(0, 100))}
            disabled={running}
            placeholder="Who published these videos"
            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
          />
        </div>
        <div>
          <label htmlFor="catalogue-platform" className="text-xs font-semibold text-slate-700">Platform (optional)</label>
          <select
            id="catalogue-platform"
            value={platform}
            onChange={(e) => setPlatform(e.target.value as Platform | "")}
            disabled={running}
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
          >
            <option value="">Not specified</option>
            {(Object.keys(PLATFORM_LABEL) as Platform[]).map((p) => (
              <option key={p} value={p}>{PLATFORM_LABEL[p]}</option>
            ))}
          </select>
        </div>
      </div>
      <div>
        <label htmlFor="catalogue-files" className="text-xs font-semibold text-slate-700">Video files</label>
        <input
          key={fileKey}
          id="catalogue-files"
          type="file"
          multiple
          accept={ACCEPT}
          disabled={running}
          onChange={(e) => pick(e.target.files)}
          className="mt-1 block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-slate-800"
        />
        <p className="mt-1 text-[11px] text-slate-500">MP4, MOV or WebM · max {MAX_MB} MB each · up to 15 minutes of each video is fingerprinted.</p>
      </div>

      {items.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-lg border border-slate-100" aria-live="polite">
          {items.map((it, i) => (
            <li key={`${it.file.name}-${i}`} className="flex items-center gap-3 px-3 py-2 text-xs">
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium text-slate-800" title={it.file.name}>{it.file.name}</div>
                <div className="text-slate-500">
                  {fmtBytes(it.file.size)}
                  {it.message && <span className={it.status === "error" ? "text-red-700" : ""}> · {it.message}</span>}
                </div>
                {it.status === "uploading" && (
                  <div className="mt-1 h-1 overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${Math.round(it.progress * 100)}%` }} />
                  </div>
                )}
              </div>
              <ItemBadge item={it} />
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={run}
        disabled={running || pending === 0 || !ownerLabel.trim()}
        className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        <UploadIcon className="h-4 w-4" />
        {running ? "Indexing…" : pending > 1 ? `Index ${pending} videos` : "Index video"}
      </button>
      {!ownerLabel.trim() && pending > 0 && <p className="text-xs text-slate-500">Enter the client or account these videos belong to.</p>}
    </Card>
  );
}

function ItemBadge({ item }: { item: QueueItem }) {
  switch (item.status) {
    case "pending":
      return <span className="text-slate-400">Waiting</span>;
    case "uploading":
      return (
        <span className="tabular-nums text-brand-700">
          {item.progress < 1 ? `Uploading ${Math.round(item.progress * 100)}%` : "Fingerprinting…"}
        </span>
      );
    case "added":
      return (
        <span className="inline-flex items-center gap-1 font-semibold text-emerald-700">
          <CheckIcon className="h-3.5 w-3.5" /> Added
        </span>
      );
    case "duplicate":
      return <span className="font-semibold text-slate-600">Duplicate</span>;
    default:
      return <span className="font-semibold text-red-700">Error</span>;
  }
}

function ServicesCard({ status, error }: { status: ProvenanceStatus | null; error: string | null }) {
  if (error)
    return (
      <Card className="p-5 text-sm text-red-700" label="Provenance services">
        Could not load provenance services: {error}
      </Card>
    );
  if (!status) return <Skeleton className="h-64 w-full" />;
  const { budget, music_id, web_detection, youtube_search, catalogue } = status;
  const pct = budget.budget_usd > 0 ? Math.min(100, (budget.spent_usd / budget.budget_usd) * 100) : 0;
  const services = [
    {
      name: "Song identification",
      on: music_id.configured,
      detail: music_id.configured
        ? `${music_id.provider}${music_id.provider === "mock" ? " (mock)" : ""} · ≈ ${fmtUsd(music_id.est_cost_per_call_usd)} per clip · ${music_id.auto ? "automatic" : "on request"}`
        : "Set MUSIC_ID_PROVIDER and AUDD_API_TOKEN",
    },
    {
      name: "Web image search",
      on: web_detection.configured,
      detail: web_detection.configured
        ? `${web_detection.provider}${web_detection.provider === "mock" ? " (mock)" : ""} · ≈ ${fmtUsd(web_detection.est_cost_per_image_usd)} per image, up to ${web_detection.max_frames} · ${web_detection.auto ? "automatic on third-party cues" : "on request"}`
        : "Set WEB_DETECTION_PROVIDER and GOOGLE_VISION_API_KEY",
    },
    {
      name: "YouTube look-alikes",
      on: youtube_search.available,
      detail: youtube_search.available
        ? `Free · ${youtube_search.units_used_today} of ${youtube_search.daily_unit_cap} quota units used today (${youtube_search.units_per_search} per search)`
        : "Needs YOUTUBE_SEARCH_API_KEY or a connected YouTube channel",
    },
  ];

  return (
    <Card className="space-y-4 p-5" label="Provenance services">
      <h2 className="text-sm font-semibold">Provenance services</h2>
      <div>
        <div className="flex justify-between text-xs">
          <span className="font-medium text-slate-700">Paid lookups this month</span>
          <span className="tabular-nums text-slate-600">
            {fmtUsd(budget.spent_usd)} / {fmtUsd(budget.budget_usd)}
          </span>
        </div>
        <div
          className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100"
          role="meter"
          aria-label="Monthly paid-lookup budget used"
          aria-valuemin={0}
          aria-valuemax={budget.budget_usd}
          aria-valuenow={budget.spent_usd}
        >
          <div className={`h-full rounded-full ${pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-amber-500" : "bg-brand-600"}`} style={{ width: `${pct}%` }} />
        </div>
        <p className="mt-1 text-[11px] text-slate-500">
          Since {fmtDay(budget.month_start)} · {fmtUsd(budget.remaining_usd)} left · estimates, not invoices.
        </p>
        {Object.keys(budget.by_service).length > 0 && (
          <ul className="mt-1.5 space-y-0.5 text-[11px] text-slate-600">
            {Object.entries(budget.by_service).map(([svc, v]) => (
              <li key={svc} className="flex justify-between">
                <span>{SERVICE_LABEL[svc] ?? svc.replace(/_/g, " ")} · {v.calls} call{v.calls === 1 ? "" : "s"}</span>
                <span className="tabular-nums">{fmtUsd(v.est_cost_usd)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <ul className="space-y-2.5 border-t border-slate-100 pt-3">
        {services.map((s) => (
          <li key={s.name} className="text-xs">
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold text-slate-800">{s.name}</span>
              <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${s.on ? "bg-emerald-50 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>
                {s.on ? "On" : "Off"}
              </span>
            </div>
            <p className="mt-0.5 text-[11px] text-slate-500">{s.detail}</p>
          </li>
        ))}
      </ul>
      <p className="border-t border-slate-100 pt-3 text-[11px] text-slate-500">
        {catalogue.entries} fingerprint{catalogue.entries === 1 ? "" : "s"} indexed · kept for {catalogue.retention_days} days.
      </p>
    </Card>
  );
}
