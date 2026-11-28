"use client";

import Link from "next/link";
import {
  CircleCheck,
  CircleExclamationPoint,
  Clock,
  ExternalLink,
  FileMusic,
  Globe,
  Info,
  RefreshCw,
  Scale,
  Search,
  TriangleExclamationPoint,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  api,
  errorMessage,
  safeUrl,
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
import { Badge, Button, ButtonLink, Callout, Card, EmptyState, Field, Input, useToast, type BadgeTone } from "../ui";

const UNLABELLED = "Unlabelled uploads";

const AREA_LABEL: Record<RightsArea, string> = {
  handle: "On-screen handle",
  broadcaster: "Broadcaster or studio",
  brand: "Brand mention",
  catalogue: "Catalogue match",
  music: "Music",
  web: "Web match",
  youtube: "YouTube look-alike",
};

const RIGHTS_STATUS: Record<RightsStatus, { label: string; tone: BadgeTone; icon: LucideIcon }> = {
  missing: { label: "No record", tone: "critical", icon: CircleExclamationPoint },
  expired: { label: "Expired", tone: "medium", icon: Clock },
  not_started: { label: "Not started", tone: "neutral", icon: Clock },
  review: { label: "Needs review", tone: "medium", icon: TriangleExclamationPoint },
  covered: { label: "Covered", tone: "success", icon: CircleCheck },
  own: { label: "Your own", tone: "neutral", icon: CircleCheck },
  info: { label: "Info", tone: "info", icon: Info },
};

const STATUS_ORDER: RightsStatus[] = ["missing", "expired", "not_started", "review", "covered", "own", "info"];

const LOOKUP_STATUS: Record<string, { label: string; tone: BadgeTone }> = {
  not_run: { label: "Not run", tone: "neutral" },
  not_configured: { label: "Off", tone: "neutral" },
  completed: { label: "Done", tone: "success" },
  partial: { label: "Partly done", tone: "medium" },
  budget_exceeded: { label: "Budget reached", tone: "medium" },
  failed: { label: "Failed", tone: "critical" },
  no_music: { label: "No music found", tone: "neutral" },
  no_frames: { label: "No frames", tone: "neutral" },
};

const VISUAL_MATCH: Record<YouTubeResult["visual_match"], { label: string; tone: BadgeTone }> = {
  strong: { label: "Very similar", tone: "critical" },
  possible: { label: "Possibly similar", tone: "medium" },
  none: { label: "Not similar", tone: "neutral" },
  unknown: { label: "Unknown", tone: "neutral" },
};

const MUSIC_CLIPS = 2;

/** Runs an action, reports the result as a toast, then refreshes. */
function useLookup(fn: () => Promise<unknown>, onDone: () => void, success: string) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  async function run() {
    setBusy(true);
    try {
      await fn();
      toast({ tone: "success", title: success });
      onDone();
    } catch (e) {
      toast({ tone: "error", title: "That did not work", description: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  }
  return { busy, run };
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
      .catch((e: unknown) => setStatusError(errorMessage(e)));
  }, []);
  useEffect(loadStatus, [loadStatus]);

  const afterLookup = () => {
    onReload();
    loadStatus();
  };
  const recheck = useLookup(() => api.recheckRights(analysis.id), onReload, "Rights coverage checked again");

  const rights = [...(p.rights ?? [])].sort((a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status));
  const cat = p.catalogue;

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <h3 className="text-[15px] font-semibold">Rights coverage</h3>
            <p className="mt-0.5 max-w-[72ch] text-[13px] text-ink-3">
              Third-party handles, branding, brands, earlier posts and (when enabled) songs and images found in this video,
              compared with your rights ledger.
              {p.rights_checked_at && <> Checked {fmtDate(p.rights_checked_at)}.</>}
            </p>
          </div>
          <div className="flex gap-2">
            <Button size="sm" leadingIcon={<RefreshCw />} loading={recheck.busy} onClick={recheck.run}>
              Check again
            </Button>
            <ButtonLink href="/rights" size="sm" variant="ghost" leadingIcon={<Scale />}>
              Rights ledger
            </ButtonLink>
          </div>
        </div>
        {rights.length === 0 ? (
          <EmptyState
            className="py-8"
            icon={<CircleCheck />}
            title="Nothing third-party was detected by these checks"
            description="This is not a rights clearance. Music, footage or logos the checks did not detect may still need a licence."
          />
        ) : (
          <ul className="divide-y divide-line">
            {rights.map((line, i) => (
              <RightsRow key={`${line.area}-${line.subject}-${i}`} line={line} onSeek={onSeek} />
            ))}
          </ul>
        )}
        {cat && (
          <div className="border-t border-line px-5 py-3 text-[13px] text-ink-3">
            {cat.skipped ? (
              "Catalogue comparison skipped: no video file was available."
            ) : (
              <>
                Compared with <span className="tabular">{cat.entries_checked}</span> indexed video{cat.entries_checked === 1 ? "" : "s"}
                {cat.owner_label && cat.owner_label !== UNLABELLED && <> for client “{cat.owner_label}”</>}.
              </>
            )}{" "}
            <Link href="/catalogue" className="font-medium text-accent hover:underline">
              Manage catalogue
            </Link>
            {cat.owner_label === UNLABELLED && (
              <p className="mt-1 text-medium-fg">
                This video has no client label, so footage reused across clients cannot be told apart. Set “Client or
                account” when uploading.
              </p>
            )}
          </div>
        )}
      </Card>

      {p.warnings && p.warnings.length > 0 && (
        <Callout tone="warning" title="Provenance notes">
          <ul className="list-disc space-y-0.5 pl-4">
            {p.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </Callout>
      )}

      {statusError && <Callout tone="danger" title="Could not load lookup settings">{statusError}</Callout>}
      <div className="grid gap-4 xl:grid-cols-2">
        <MusicTile analysis={analysis} block={p.music} status={status} onSeek={onSeek} onDone={afterLookup} />
        <WebTile analysis={analysis} block={p.web} status={status} onSeek={onSeek} onDone={afterLookup} />
        <div className="xl:col-span-2">
          <YouTubeTile analysis={analysis} block={p.youtube} status={status} onSeek={onSeek} onDone={afterLookup} />
        </div>
      </div>
    </div>
  );
}

function TimeButton({ start, end, onSeek }: { start: number; end?: number | null; onSeek: (t: number) => void }) {
  return (
    <button
      type="button"
      onClick={() => onSeek(start)}
      className="tabular inline-flex items-center gap-1 text-[12px] font-semibold text-accent hover:underline"
    >
      <Clock className="size-3" aria-hidden />
      {fmtTime(start)}
      {end != null && end !== start && `–${fmtTime(end)}`}
    </button>
  );
}

function RightsRow({ line, onSeek }: { line: RightsLine; onSeek: (t: number) => void }) {
  const st = RIGHTS_STATUS[line.status] ?? RIGHTS_STATUS.info;
  const label = line.area === "brand" && line.status === "missing" ? "No disclosure" : st.label;
  return (
    <li className="flex flex-col gap-2 px-5 py-3.5 sm:flex-row sm:items-start sm:gap-4">
      <div className="sm:w-32 sm:shrink-0">
        <Badge tone={st.tone} icon={st.icon}>
          {label}
        </Badge>
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
          <span className="text-[12px] text-ink-3">{AREA_LABEL[line.area] ?? line.area}</span>
          <span className="text-sm font-semibold text-ink">{line.subject}</span>
          {line.start_seconds != null && <TimeButton start={line.start_seconds} end={line.end_seconds} onSeek={onSeek} />}
        </div>
        <p className="mt-0.5 text-[13px] text-ink-2">{line.detail}</p>
        {(line.records.length > 0 || line.match?.analysis_id) && (
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px]">
            {line.records.map((r) => (
              <Link
                key={r.record_id}
                href={`/rights#record-${r.record_id}`}
                className="font-medium text-accent hover:underline"
                title={[r.kind_label, r.reference, r.valid_until && `until ${r.valid_until}`].filter(Boolean).join(" · ")}
              >
                {r.kind_label}: {r.counterparty}
                {r.status !== "active" && ` (${r.status.replace(/_/g, " ")})`}
              </Link>
            ))}
            {line.match?.analysis_id && (
              <Link href={`/analyses/${line.match.analysis_id}`} className="font-medium text-accent hover:underline">
                Open that review
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
        <span className="flex size-7 items-center justify-center rounded-[6px] bg-surface-3 text-ink-2 [&_svg]:size-4">{icon}</span>
        <h3 className="text-sm font-semibold">{title}</h3>
        {block && <Badge tone={st?.tone ?? "neutral"}>{st?.label ?? block.status.replace(/_/g, " ")}</Badge>}
        {block?.is_mock && <Badge tone="medium">MOCK, not a real result</Badge>}
      </div>
      {block?.detail && <p className="mt-2 text-[13px] text-ink-2">{block.detail}</p>}
      <div className="mt-3 flex-1 space-y-3">{children}</div>
    </Card>
  );
}

function PaidAction({
  label,
  cost,
  status,
  disabledReason,
  lookup,
}: {
  label: string;
  cost: number | null;
  status: ProvenanceStatus | null;
  disabledReason?: string | null;
  lookup: ReturnType<typeof useLookup>;
}) {
  const budget = status?.budget;
  const exhausted = budget != null && budget.remaining_usd <= 0;
  return (
    <div className="space-y-1.5 border-t border-line pt-3">
      <Button size="sm" onClick={lookup.run} loading={lookup.busy} disabled={exhausted || !!disabledReason}>
        {label}
      </Button>
      <p className="text-[12px] text-ink-3">
        {disabledReason ??
          (exhausted
            ? "This month’s paid-lookup budget is used up."
            : `${cost != null ? `About ${fmtUsd(cost)}, ` : "Paid lookup, "}counted toward your monthly cap${
                budget ? ` (${fmtUsd(budget.remaining_usd)} of ${fmtUsd(budget.budget_usd)} left)` : ""
              }.`)}
      </p>
    </div>
  );
}

function OffNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-[8px] border border-dashed border-line-strong bg-surface-2 px-3 py-2 text-[12px] text-ink-2">
      <span className="font-semibold text-ink">Off.</span> {children}
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
  const lookup = useLookup(() => api.lookupMusic(analysis.id), onDone, "Song identification finished");
  const cfg = status?.music_id;
  const clips = block?.clips ?? [];
  return (
    <Tile icon={<FileMusic />} title="Song identification" block={block}>
      {clips.length > 0 && (
        <ul className="space-y-2">
          {clips.map((c, i) => {
            const link = safeUrl(c.song_link);
            return (
              <li key={i} className="text-[13px]">
                <TimeButton start={c.start} end={c.end} onSeek={onSeek} />
                <div className="mt-0.5">
                  {c.matched ? (
                    <>
                      <span className="font-semibold text-ink">{c.title ?? "Unknown title"}</span>
                      {c.artist && <span className="text-ink-2"> — {c.artist}</span>}
                      {c.label && <span className="text-ink-3"> ({c.label})</span>}
                      {link && (
                        <a href={link} target="_blank" rel="noopener noreferrer" className="ml-1.5 inline-flex items-center gap-1 text-[12px] font-medium text-accent hover:underline">
                          Listen <ExternalLink className="size-3" aria-hidden />
                        </a>
                      )}
                    </>
                  ) : (
                    <span className="text-ink-3">{c.error ?? "No song recognised in this clip."}</span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {cfg && !cfg.configured && (
        <OffNote>
          Set <code className="font-mono">MUSIC_ID_PROVIDER</code> and <code className="font-mono">AUDD_API_TOKEN</code> on the server to identify songs.
        </OffNote>
      )}
      {cfg?.configured && (
        <PaidAction
          label={clips.length ? "Identify music again" : "Identify music"}
          cost={cfg.est_cost_per_call_usd * MUSIC_CLIPS}
          status={status}
          disabledReason={analysis.media_deleted ? "The video file was deleted under the retention policy." : null}
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
  const lookup = useLookup(() => api.lookupWeb(analysis.id), onDone, "Web image search finished");
  const cfg = status?.web_detection;
  const frames = block?.frames ?? [];
  return (
    <Tile icon={<Globe />} title="Web image search" block={block}>
      {frames.length > 0 && (
        <ul className="space-y-3">
          {frames.map((fr) => (
            <li key={fr.frame_id} className="flex gap-3">
              <button
                type="button"
                onClick={() => fr.timestamp != null && onSeek(fr.timestamp)}
                className="flex-none overflow-hidden rounded-[6px] ring-1 ring-line hover:ring-accent"
                title={`Play from ${fmtTime(fr.timestamp)}`}
                aria-label={`Play from ${fmtTime(fr.timestamp)} (frame ${fr.frame_id})`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element -- served by the API, not optimisable */}
                <img src={api.frameUrl(analysis.id, fr.frame_id)} alt="" className="h-16 w-9 object-cover" loading="lazy" />
              </button>
              <div className="min-w-0 flex-1 text-[13px]">
                <div className="text-[12px] text-ink-3">
                  {fr.frame_id} · {fmtTime(fr.timestamp)}
                  {fr.best_guess.length > 0 && <> · Best guess: {fr.best_guess.join(", ")}</>}
                </div>
                {fr.error && <p className="mt-0.5 text-critical-fg">{fr.error}</p>}
                {!fr.error && fr.pages.length === 0 && <p className="mt-0.5 text-ink-3">No pages with this image were found.</p>}
                <ul className="mt-1 space-y-1">
                  {fr.pages.slice(0, 5).map((pg, i) => {
                    const href = safeUrl(pg.url);
                    return (
                      <li key={`${pg.url}-${i}`} className="flex items-baseline gap-1.5">
                        <Badge tone={pg.full_match ? "critical" : "medium"} className="h-5 shrink-0 text-[11px]">
                          {pg.full_match ? "Same image" : "Similar image"}
                        </Badge>
                        {href ? (
                          <a href={href} target="_blank" rel="noopener noreferrer" className="min-w-0 truncate text-accent hover:underline" title={pg.url}>
                            <span className="font-medium">{pg.domain || hostOf(pg.url)}</span>
                            {pg.title && <span className="text-ink-2"> · {pg.title}</span>}
                          </a>
                        ) : (
                          <span className="min-w-0 truncate text-ink-2">
                            <span className="font-medium">{pg.domain || "Unlinkable page"}</span>
                            {pg.title && <> · {pg.title}</>}
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
                {fr.pages.length > 5 && <p className="mt-0.5 text-[12px] text-ink-3">+{fr.pages.length - 5} more pages</p>}
              </div>
            </li>
          ))}
        </ul>
      )}
      {cfg && !cfg.configured && (
        <OffNote>
          Set <code className="font-mono">WEB_DETECTION_PROVIDER</code> and <code className="font-mono">GOOGLE_VISION_API_KEY</code> on the server to search the web for these frames.
        </OffNote>
      )}
      {cfg?.configured && (
        <PaidAction
          label={frames.length ? "Search the web again" : "Search the web for these frames"}
          cost={cfg.est_cost_per_image_usd * cfg.max_frames}
          status={status}
          lookup={lookup}
        />
      )}
    </Tile>
  );
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
  const lookup = useLookup(() => api.lookupYouTube(analysis.id, q), onDone, "YouTube search finished");
  const quota = status?.youtube_search ?? suggest;
  const results = block?.results ?? [];
  const tileBlock = block && block.status !== "not_run" ? { status: block.status, detail: block.detail ?? null } : undefined;

  return (
    <Tile icon={<Search />} title="YouTube look-alikes" block={tileBlock}>
      {status && !available && (
        <OffNote>
          Needs <code className="font-mono">YOUTUBE_SEARCH_API_KEY</code> or a connected YouTube channel.
        </OffNote>
      )}
      {available && (
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-end gap-2">
            <Field label="Search YouTube for" className="min-w-0 flex-1">
              {(p) => (
                <Input
                  {...p}
                  value={query ?? ""}
                  onChange={(e) => setQuery(e.target.value.slice(0, 120))}
                  placeholder={query === null ? "Loading a suggested query…" : "A few words from the title or speech"}
                  maxLength={120}
                />
              )}
            </Field>
            <Button onClick={lookup.run} loading={lookup.busy} disabled={q.length < 3}>
              Search
            </Button>
          </div>
          {quota && (
            <p className="text-[12px] text-ink-3">
              Free, but uses {quota.units_per_search} of {quota.daily_unit_cap} daily quota units ({quota.units_used_today} used today).
              Thumbnails are compared with this video’s frames.
            </p>
          )}
        </div>
      )}
      {block?.status === "completed" && (
        <div>
          <p className="text-[12px] text-ink-3">
            {results.length} result{results.length === 1 ? "" : "s"} for “{block.query}”
            {block.searched_at && <> · {fmtDate(block.searched_at)}</>}
            {block.strong_matches ? (
              <>
                {" "}
                · <strong className="text-critical-fg">{block.strong_matches} very similar</strong>
              </>
            ) : null}
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
  const thumbnail = safeUrl(r.thumbnail_url);
  const href = safeUrl(r.url);
  return (
    <li className="flex gap-3">
      {thumbnail ? (
        // eslint-disable-next-line @next/next/no-img-element -- remote YouTube thumbnail, host not configured for next/image
        <img src={thumbnail} alt="" referrerPolicy="no-referrer" loading="lazy" className="h-14 w-24 flex-none rounded-[6px] object-cover ring-1 ring-line" />
      ) : (
        <div className="h-14 w-24 flex-none rounded-[6px] bg-surface-3" />
      )}
      <div className="min-w-0 flex-1">
        <a href={href} target="_blank" rel="noopener noreferrer" className="line-clamp-2 text-[13px] leading-snug font-medium text-ink hover:text-accent hover:underline">
          {r.title || r.video_id}
        </a>
        <div className="mt-0.5 truncate text-[12px] text-ink-3">
          {r.channel_title}
          {r.published_at && <> · {fmtDay(r.published_at)}</>}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          <Badge tone={vm.tone} className="h-5 text-[11px]">
            {vm.label}
          </Badge>
          {r.own_channel && (
            <Badge tone="low" className="h-5 text-[11px]">
              Your channel
            </Badge>
          )}
          {r.matched_at != null && <TimeButton start={r.matched_at} onSeek={onSeek} />}
        </div>
      </div>
    </li>
  );
}
