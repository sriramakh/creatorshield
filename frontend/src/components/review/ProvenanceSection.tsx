"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  api,
  type Analysis,
  type LookupBlock,
  type Provenance,
  type ProvenanceStatus,
  type RightsArea,
  type RightsLine,
  type RightsStatus,
  type YouTubeBlock,
  type YouTubeResult,
  type YouTubeSuggest,
} from "@/lib/api";
import { fmtDate, fmtDay, fmtTime, fmtUsd } from "@/lib/format";
import { CheckIcon, ClockIcon, ExternalIcon, GlobeIcon, MusicIcon, SearchIcon } from "../icons";
import { Card } from "../ui";

const UNLABELLED = "Unlabelled uploads";

const AREA_LABEL: Record<RightsArea, string> = {
  handle: "On-screen handle",
  broadcaster: "Broadcaster / studio",
  brand: "Brand mention",
  catalogue: "Catalogue match",
  music: "Music",
  web: "Web match",
  youtube: "YouTube look-alike",
};

const RIGHTS_STATUS: Record<RightsStatus, { label: string; className: string }> = {
  covered: { label: "Covered", className: "bg-emerald-50 text-emerald-800 ring-emerald-200" },
  own: { label: "Your own", className: "bg-slate-100 text-slate-700 ring-slate-200" },
  info: { label: "Info", className: "bg-slate-100 text-slate-700 ring-slate-200" },
  review: { label: "Needs review", className: "bg-amber-50 text-amber-800 ring-amber-200" },
  expired: { label: "Expired", className: "bg-amber-50 text-amber-800 ring-amber-200" },
  not_started: { label: "Not started", className: "bg-slate-100 text-slate-700 ring-slate-200" },
  missing: { label: "No record", className: "bg-red-50 text-red-800 ring-red-200" },
};

const STATUS_ORDER: RightsStatus[] = [
  "missing",
  "expired",
  "not_started",
  "review",
  "covered",
  "own",
  "info",
];

const LOOKUP_STATUS: Record<string, { label: string; className: string }> = {
  not_run: { label: "Not run", className: "bg-slate-100 text-slate-600" },
  not_configured: { label: "Off", className: "bg-slate-100 text-slate-600" },
  completed: { label: "Done", className: "bg-emerald-50 text-emerald-800" },
  partial: { label: "Partly done", className: "bg-amber-50 text-amber-800" },
  budget_exceeded: { label: "Budget reached", className: "bg-amber-50 text-amber-800" },
  failed: { label: "Failed", className: "bg-red-50 text-red-800" },
  no_music: { label: "No music found", className: "bg-slate-100 text-slate-600" },
  no_frames: { label: "No frames", className: "bg-slate-100 text-slate-600" },
};

const VISUAL_MATCH: Record<YouTubeResult["visual_match"], { label: string; className: string }> = {
  strong: { label: "Very similar", className: "bg-red-50 text-red-800 ring-red-200" },
  possible: { label: "Possibly similar", className: "bg-amber-50 text-amber-800 ring-amber-200" },
  none: { label: "Not similar", className: "bg-slate-100 text-slate-600 ring-slate-200" },
  unknown: { label: "Unknown", className: "bg-slate-100 text-slate-500 ring-slate-200" },
};

const MUSIC_CLIPS = 2;

function useLookup(fn: () => Promise<unknown>, onDone: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function run() {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, run };
}

export function ProvenanceSection({
  analysis,
  provenance: p,
  onSeek,
  onReload,
}: {
  analysis: Analysis;
  provenance: Provenance;
  onSeek: (t: number) => void;
  onReload: () => void;
}) {
  const [status, setStatus] = useState<ProvenanceStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  const loadStatus = useCallback(() => {
    api
      .provenanceStatus()
      .then((s) => {
        setStatus(s);
        setStatusError(null);
      })
      .catch((e: Error) => setStatusError(e.message));
  }, []);
  useEffect(loadStatus, [loadStatus]);

  const afterLookup = () => {
    onReload();
    loadStatus();
  };
  const recheck = useLookup(() => api.recheckRights(analysis.id), onReload);

  const rights = [...(p.rights ?? [])].sort((a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status));
  const cat = p.catalogue;

  return (
    <section aria-labelledby="provenance-heading">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="provenance-heading" className="text-base font-semibold">Provenance & rights</h2>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={recheck.run}
            disabled={recheck.busy}
            className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:text-slate-400"
          >
            {recheck.busy ? "Re-checking…" : "Re-check rights"}
          </button>
          <Link
            href="/rights"
            className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-brand-700 hover:bg-slate-50"
          >
            Edit rights ledger
          </Link>
        </div>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Third-party handles, branding, brands, earlier posts and (when enabled) songs and images found in this video,
        compared with your rights ledger.
        {p.rights_checked_at && <> Coverage checked {fmtDate(p.rights_checked_at)}.</>}
      </p>
      <div aria-live="polite">
        {recheck.error && <p className="mt-2 text-sm font-medium text-red-700">{recheck.error}</p>}
      </div>

      <Card className="mt-3">
        {rights.length === 0 ? (
          <div className="flex items-start gap-3 p-5 text-sm text-slate-600">
            <CheckIcon className="mt-0.5 h-5 w-5 flex-none text-emerald-600" />
            <div>
              Nothing third-party was detected by the provenance checks.
              <p className="mt-0.5 text-xs text-slate-500">
                This is not a rights clearance — music, footage or logos the checks did not detect may still need a licence.
              </p>
            </div>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {rights.map((line, i) => (
              <RightsRow key={`${line.area}-${line.subject}-${i}`} line={line} onSeek={onSeek} />
            ))}
          </ul>
        )}
        {cat && (
          <div className="border-t border-slate-100 px-4 py-2.5 text-xs text-slate-500">
            {cat.skipped ? (
              "Catalogue comparison skipped — no video file was available."
            ) : (
              <>
                Compared with {cat.entries_checked} indexed video{cat.entries_checked === 1 ? "" : "s"}
                {cat.owner_label && cat.owner_label !== UNLABELLED && <> · client “{cat.owner_label}”</>}.
              </>
            )}{" "}
            <Link href="/catalogue" className="font-medium text-brand-700 hover:underline">
              Manage catalogue
            </Link>
            {cat.owner_label === UNLABELLED && (
              <p className="mt-1 text-amber-800">
                This video has no client label, so footage reused across clients can&apos;t be told apart. Set
                “Client / account” when uploading.
              </p>
            )}
          </div>
        )}
      </Card>

      {p.warnings && p.warnings.length > 0 && (
        <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-amber-800">
          {p.warnings.map((w, i) => <li key={i}>{w}</li>)}
        </ul>
      )}

      {statusError && <p className="mt-3 text-xs text-red-700">Could not load lookup settings: {statusError}</p>}
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <MusicTile analysis={analysis} block={p.music} status={status} onSeek={onSeek} onDone={afterLookup} />
        <WebTile analysis={analysis} block={p.web} status={status} onSeek={onSeek} onDone={afterLookup} />
        <div className="md:col-span-2">
          <YouTubeTile analysis={analysis} block={p.youtube} status={status} onSeek={onSeek} onDone={afterLookup} />
        </div>
      </div>
    </section>
  );
}

function TimeButton({ start, end, onSeek }: { start: number; end?: number | null; onSeek: (t: number) => void }) {
  return (
    <button
      type="button"
      onClick={() => onSeek(start)}
      className="inline-flex items-center gap-1 text-[11px] font-semibold text-brand-700 hover:underline"
    >
      <ClockIcon className="h-3 w-3" />
      {fmtTime(start)}
      {end != null && end !== start && `–${fmtTime(end)}`}
    </button>
  );
}

function RightsRow({ line, onSeek }: { line: RightsLine; onSeek: (t: number) => void }) {
  const st = RIGHTS_STATUS[line.status] ?? RIGHTS_STATUS.info;
  return (
    <li className="flex items-start gap-3 px-4 py-3">
      <span className={`mt-0.5 inline-flex w-24 flex-none justify-center rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${st.className}`}>
        {line.area === "brand" && line.status === "missing" ? "No disclosure" : st.label}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{AREA_LABEL[line.area] ?? line.area}</span>
          <span className="text-sm font-semibold text-slate-900">{line.subject}</span>
          {line.start_seconds != null && <TimeButton start={line.start_seconds} end={line.end_seconds} onSeek={onSeek} />}
        </div>
        <p className="mt-0.5 text-[13px] text-slate-600">{line.detail}</p>
        {(line.records.length > 0 || line.match?.analysis_id) && (
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
            {line.records.map((r) => (
              <Link
                key={r.record_id}
                href={`/rights#record-${r.record_id}`}
                className="font-medium text-brand-700 hover:underline"
                title={[r.kind_label, r.reference, r.valid_until && `until ${r.valid_until}`].filter(Boolean).join(" · ")}
              >
                {r.kind_label}: {r.counterparty}
                {r.status !== "active" && ` (${r.status.replace(/_/g, " ")})`}
              </Link>
            ))}
            {line.match?.analysis_id && (
              <Link href={`/analyses/${line.match.analysis_id}`} className="font-medium text-brand-700 hover:underline">
                Open that review →
              </Link>
            )}
          </div>
        )}
      </div>
    </li>
  );
}

// --------------------------------------------------------------------------- lookup tiles

function Tile({
  icon,
  title,
  block,
  children,
}: {
  icon: ReactNode;
  title: string;
  block?: Pick<LookupBlock, "status" | "detail"> & { is_mock?: boolean };
  children: ReactNode;
}) {
  const st = block ? LOOKUP_STATUS[block.status] : undefined;
  return (
    <Card className="flex h-full flex-col p-4" label={title}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-100 text-slate-600">{icon}</span>
        <h3 className="text-sm font-semibold">{title}</h3>
        {block && (
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${st?.className ?? "bg-slate-100 text-slate-600"}`}>
            {st?.label ?? block.status.replace(/_/g, " ")}
          </span>
        )}
        {block?.is_mock && (
          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-900">MOCK — not a real result</span>
        )}
      </div>
      {block?.detail && <p className="mt-2 text-xs text-slate-600">{block.detail}</p>}
      <div className="mt-3 flex-1 space-y-3">{children}</div>
    </Card>
  );
}

function PaidAction({
  label,
  busyLabel,
  cost,
  status,
  disabledReason,
  lookup,
}: {
  label: string;
  busyLabel: string;
  cost: number | null;
  status: ProvenanceStatus | null;
  disabledReason?: string | null;
  lookup: ReturnType<typeof useLookup>;
}) {
  const budget = status?.budget;
  const exhausted = budget != null && budget.remaining_usd <= 0;
  return (
    <div className="space-y-1.5 border-t border-slate-100 pt-3">
      <button
        type="button"
        onClick={lookup.run}
        disabled={lookup.busy || exhausted || !!disabledReason}
        className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-700 disabled:bg-slate-300"
      >
        {lookup.busy ? busyLabel : label}
      </button>
      <p className="text-[11px] text-slate-500">
        {disabledReason ??
          (exhausted
            ? "This month's paid-lookup budget is used up."
            : `${cost != null ? `≈ ${fmtUsd(cost)}, ` : "Paid lookup, "}counts toward your monthly cap${
                budget ? ` (${fmtUsd(budget.remaining_usd)} of ${fmtUsd(budget.budget_usd)} left)` : ""
              }.`)}
      </p>
      <div aria-live="polite">{lookup.error && <p className="text-xs font-medium text-red-700">{lookup.error}</p>}</div>
    </div>
  );
}

function OffNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-2 text-[11px] text-slate-600">
      <span className="font-semibold text-slate-800">Off</span> — {children}
    </p>
  );
}

function MusicTile({
  analysis,
  block,
  status,
  onSeek,
  onDone,
}: {
  analysis: Analysis;
  block: Provenance["music"];
  status: ProvenanceStatus | null;
  onSeek: (t: number) => void;
  onDone: () => void;
}) {
  const lookup = useLookup(() => api.lookupMusic(analysis.id), onDone);
  const cfg = status?.music_id;
  const clips = block?.clips ?? [];
  return (
    <Tile icon={<MusicIcon className="h-4 w-4" />} title="Song identification" block={block}>
      {clips.length > 0 && (
        <ul className="space-y-2">
          {clips.map((c, i) => (
            <li key={i} className="text-[13px]">
              <TimeButton start={c.start} end={c.end} onSeek={onSeek} />
              <div className="mt-0.5">
                {c.matched ? (
                  <>
                    <span className="font-semibold text-slate-900">{c.title ?? "Unknown title"}</span>
                    {c.artist && <span className="text-slate-600"> — {c.artist}</span>}
                    {c.label && <span className="text-slate-500"> ({c.label})</span>}
                    {c.song_link && (
                      <a
                        href={c.song_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-1.5 inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline"
                      >
                        Listen <ExternalIcon className="h-3 w-3" />
                      </a>
                    )}
                  </>
                ) : (
                  <span className="text-slate-500">{c.error ?? "No song recognised in this clip."}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {cfg && !cfg.configured && (
        <OffNote>
          set <code className="font-mono">MUSIC_ID_PROVIDER</code> and <code className="font-mono">AUDD_API_TOKEN</code> in
          backend/.env to identify songs.
        </OffNote>
      )}
      {cfg?.configured && (
        <PaidAction
          label={clips.length ? "Identify music again" : "Identify music"}
          busyLabel="Identifying…"
          cost={cfg.est_cost_per_call_usd * MUSIC_CLIPS}
          status={status}
          disabledReason={analysis.media_deleted ? "The video file was deleted under the retention policy." : null}
          lookup={lookup}
        />
      )}
    </Tile>
  );
}

function WebTile({
  analysis,
  block,
  status,
  onSeek,
  onDone,
}: {
  analysis: Analysis;
  block: Provenance["web"];
  status: ProvenanceStatus | null;
  onSeek: (t: number) => void;
  onDone: () => void;
}) {
  const lookup = useLookup(() => api.lookupWeb(analysis.id), onDone);
  const cfg = status?.web_detection;
  const frames = block?.frames ?? [];
  return (
    <Tile icon={<GlobeIcon className="h-4 w-4" />} title="Web image search" block={block}>
      {frames.length > 0 && (
        <ul className="space-y-3">
          {frames.map((fr) => (
            <li key={fr.frame_id} className="flex gap-3">
              <button
                type="button"
                onClick={() => fr.timestamp != null && onSeek(fr.timestamp)}
                className="flex-none overflow-hidden rounded-md ring-1 ring-slate-200 hover:ring-brand-500"
                title={`Play from ${fmtTime(fr.timestamp)}`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element -- served by the API, not optimisable */}
                <img src={api.frameUrl(analysis.id, fr.frame_id)} alt={`Frame ${fr.frame_id}`} className="h-16 w-9 object-cover" loading="lazy" />
              </button>
              <div className="min-w-0 flex-1 text-xs">
                <div className="text-[11px] text-slate-500">
                  {fr.frame_id} · {fmtTime(fr.timestamp)}
                  {fr.best_guess.length > 0 && <> · Best guess: {fr.best_guess.join(", ")}</>}
                </div>
                {fr.error && <p className="mt-0.5 text-red-700">{fr.error}</p>}
                {!fr.error && fr.pages.length === 0 && <p className="mt-0.5 text-slate-500">No pages with this image were found.</p>}
                <ul className="mt-1 space-y-1">
                  {fr.pages.slice(0, 5).map((pg) => (
                    <li key={pg.url} className="flex items-baseline gap-1.5">
                      <span
                        className={`flex-none rounded px-1 text-[10px] font-semibold ${
                          pg.full_match ? "bg-red-50 text-red-800" : "bg-amber-50 text-amber-800"
                        }`}
                      >
                        {pg.full_match ? "same image" : "similar image"}
                      </span>
                      <a href={pg.url} target="_blank" rel="noopener noreferrer" className="min-w-0 truncate text-brand-700 hover:underline" title={pg.url}>
                        <span className="font-medium">{pg.domain || hostOf(pg.url)}</span>
                        {pg.title && <span className="text-slate-600"> · {pg.title}</span>}
                      </a>
                    </li>
                  ))}
                </ul>
                {fr.pages.length > 5 && <p className="mt-0.5 text-[11px] text-slate-500">+{fr.pages.length - 5} more pages</p>}
              </div>
            </li>
          ))}
        </ul>
      )}
      {cfg && !cfg.configured && (
        <OffNote>
          set <code className="font-mono">WEB_DETECTION_PROVIDER</code> and{" "}
          <code className="font-mono">GOOGLE_VISION_API_KEY</code> in backend/.env to search the web for these frames.
        </OffNote>
      )}
      {cfg?.configured && (
        <PaidAction
          label={frames.length ? "Search the web again" : "Search the web for these frames"}
          busyLabel="Searching…"
          cost={cfg.est_cost_per_image_usd * cfg.max_frames}
          status={status}
          lookup={lookup}
        />
      )}
    </Tile>
  );
}

function hostOf(url: string) {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function YouTubeTile({
  analysis,
  block,
  status,
  onSeek,
  onDone,
}: {
  analysis: Analysis;
  block?: YouTubeBlock;
  status: ProvenanceStatus | null;
  onSeek: (t: number) => void;
  onDone: () => void;
}) {
  const available = status?.youtube_search.available ?? false;
  const [suggest, setSuggest] = useState<YouTubeSuggest | null>(null);
  const [query, setQuery] = useState<string | null>(block?.query ?? null);

  useEffect(() => {
    if (!available) return;
    api
      .youtubeSuggest(analysis.id)
      .then((s) => {
        setSuggest(s);
        setQuery((q) => q ?? s.query);
      })
      .catch(() => setQuery((q) => q ?? ""));
  }, [available, analysis.id]);

  const q = (query ?? "").trim();
  const lookup = useLookup(() => api.lookupYouTube(analysis.id, q), onDone);
  const quota = status?.youtube_search ?? suggest;
  const results = block?.results ?? [];
  const tileBlock = block && block.status !== "not_run" ? { status: block.status, detail: block.detail ?? null } : undefined;

  return (
    <Tile icon={<SearchIcon className="h-4 w-4" />} title="YouTube look-alikes" block={tileBlock}>
      {status && !available && (
        <OffNote>
          needs <code className="font-mono">YOUTUBE_SEARCH_API_KEY</code> or a connected YouTube channel.
        </OffNote>
      )}
      {available && (
        <div className="space-y-1.5">
          <label htmlFor={`yt-query-${analysis.id}`} className="block text-xs font-medium text-slate-700">
            Search YouTube for
          </label>
          <div className="flex flex-wrap gap-2">
            <input
              id={`yt-query-${analysis.id}`}
              value={query ?? ""}
              onChange={(e) => setQuery(e.target.value.slice(0, 120))}
              placeholder={query === null ? "Loading a suggested query…" : "A few words from the title or speech"}
              maxLength={120}
              className="min-w-0 flex-1 rounded-lg border border-slate-200 px-3 py-1.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            />
            <button
              type="button"
              onClick={lookup.run}
              disabled={lookup.busy || q.length < 3}
              className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-700 disabled:bg-slate-300"
            >
              {lookup.busy ? "Searching…" : "Search"}
            </button>
          </div>
          {quota && (
            <p className="text-[11px] text-slate-500">
              Free, but uses {quota.units_per_search} of {quota.daily_unit_cap} daily quota units ({quota.units_used_today} used today).
              Thumbnails are compared with this video&apos;s frames.
            </p>
          )}
          <div aria-live="polite">{lookup.error && <p className="text-xs font-medium text-red-700">{lookup.error}</p>}</div>
        </div>
      )}
      {block?.status === "completed" && (
        <div>
          <p className="text-[11px] text-slate-500">
            {results.length} result{results.length === 1 ? "" : "s"} for “{block.query}”
            {block.searched_at && <> · {fmtDate(block.searched_at)}</>}
            {block.strong_matches ? <> · <strong className="text-red-700">{block.strong_matches} very similar</strong></> : null}
          </p>
          <ul className="mt-2 grid gap-3 lg:grid-cols-2">
            {results.map((r) => (
              <YouTubeRow key={r.video_id} r={r} onSeek={onSeek} />
            ))}
          </ul>
        </div>
      )}
    </Tile>
  );
}

function YouTubeRow({ r, onSeek }: { r: YouTubeResult; onSeek: (t: number) => void }) {
  const vm = VISUAL_MATCH[r.visual_match] ?? VISUAL_MATCH.unknown;
  return (
    <li className="flex gap-3">
      {r.thumbnail_url ? (
        // eslint-disable-next-line @next/next/no-img-element -- remote YouTube thumbnail, host not configured for next/image
        <img src={r.thumbnail_url} alt="" referrerPolicy="no-referrer" loading="lazy" className="h-14 w-24 flex-none rounded-md object-cover ring-1 ring-slate-200" />
      ) : (
        <div className="h-14 w-24 flex-none rounded-md bg-slate-100" />
      )}
      <div className="min-w-0 flex-1">
        <a
          href={r.url}
          target="_blank"
          rel="noopener noreferrer"
          className="line-clamp-2 text-[13px] font-medium leading-snug text-slate-900 hover:text-brand-700 hover:underline"
        >
          {r.title || r.video_id}
        </a>
        <div className="mt-0.5 truncate text-[11px] text-slate-500">
          {r.channel_title}
          {r.published_at && <> · {fmtDay(r.published_at)}</>}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold ring-1 ${vm.className}`}>{vm.label}</span>
          {r.own_channel && (
            <span className="rounded-full bg-sky-50 px-1.5 py-0.5 text-[10px] font-semibold text-sky-800 ring-1 ring-sky-200">Your channel</span>
          )}
          {r.matched_at != null && <TimeButton start={r.matched_at} onSeek={onSeek} />}
        </div>
      </div>
    </li>
  );
}
