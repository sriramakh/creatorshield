"use client";

import Link from "next/link";
import { CircleCheck, CircleX, Copy, Film, LoaderCircle, Trash, Upload, X } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { addToCatalogue, api, errorMessage, isAbortError, type CatalogueEntry, type Platform, type ProvenanceStatus } from "@/lib/api";
import { fmtBytes, fmtDay, fmtLength, fmtUsd } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace";

/** The backend's owner label for uploads without a client (creator mode uses it for "your posts"). */
const OWN_POSTS = "Unlabelled uploads";
import { PageContainer } from "./shell/AppShell";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  DataTable,
  EmptyState,
  ErrorNotice,
  Field,
  FilePicker,
  IconButton,
  Input,
  PageHeader,
  Progress,
  Section,
  Select,
  Skeleton,
  StatusDot,
  useToast,
  type Column,
} from "./ui";

const ACCEPT = ".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm";
// Backend defaults (MAX_UPLOAD_MB, CATALOGUE_MAX_SECONDS) until /api/config answers.
const DEFAULT_LIMITS = { mb: 5120, seconds: 3600 };

const SERVICE_LABEL: Record<string, string> = {
  music_id: "Song identification",
  web_detection: "Web image search",
};

function fmtMinutes(seconds: number) {
  return `${+(seconds / 60).toFixed(1)} minutes`;
}

function fmtSize(mb: number) {
  return mb >= 1024 ? `${+(mb / 1024).toFixed(1)} GB` : `${mb} MB`;
}

type ItemStatus = "pending" | "uploading" | "added" | "duplicate" | "error";
interface QueueItem {
  file: File;
  status: ItemStatus;
  progress: number;
  message?: string;
}

export function CataloguePage() {
  const toast = useToast();
  const { agency, platformLabel } = useWorkspace();
  const [entries, setEntries] = useState<CatalogueEntry[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [status, setStatus] = useState<ProvenanceStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [owner, setOwner] = useState("all");
  const [deleting, setDeleting] = useState<CatalogueEntry | null>(null);

  const load = useCallback(() => {
    api
      .catalogue()
      .then((r) => {
        setEntries(r);
        setLoadError(null);
      })
      .catch((e: unknown) => setLoadError(errorMessage(e)));
    api
      .provenanceStatus()
      .then((s) => {
        setStatus(s);
        setStatusError(null);
      })
      .catch((e: unknown) => setStatusError(errorMessage(e)));
  }, []);
  useEffect(load, [load]);

  const owners = [...new Set((entries ?? []).map((e) => e.owner_label))].sort((a, b) => a.localeCompare(b));
  const shown = entries ? entries.filter((e) => owner === "all" || e.owner_label === owner) : null;

  const columns: Column<CatalogueEntry>[] = [
    {
      key: "title",
      header: "Video",
      sortValue: (e) => (e.title ?? "").toLowerCase(),
      cell: (e) => (
        <div className="min-w-0 max-w-[340px]">
          <div className="truncate font-medium" title={e.title ?? undefined}>
            {e.title || "Untitled"}
          </div>
          {e.platform && <div className="text-[12px] text-ink-3">{platformLabel(e.platform)}</div>}
        </div>
      ),
    },
    ...(agency
      ? [{ key: "owner", header: "Client or account", sortValue: (e: CatalogueEntry) => e.owner_label, cell: (e: CatalogueEntry) => <span className="text-ink-2">{e.owner_label}</span> }]
      : []),
    {
      key: "source",
      header: "Source",
      cell: (e) =>
        e.source === "analysis" ? (
          e.analysis_id ? (
            <Link href={`/analyses/${e.analysis_id}`} className="relative z-10 text-[13px] font-medium text-accent hover:underline">
              Reviewed video
            </Link>
          ) : (
            <Badge tone="accent">Reviewed video</Badge>
          )
        ) : (
          <Badge>Indexed post</Badge>
        ),
    },
    { key: "length", header: "Length", align: "right", sortValue: (e) => e.duration_seconds, cell: (e) => <span className="tabular">{fmtLength(e.duration_seconds)}</span> },
    { key: "frames", header: "Frames", align: "right", sortValue: (e) => e.frames_hashed, cell: (e) => <span className="tabular">{e.frames_hashed}</span> },
    { key: "audio", header: "Audio", cell: (e) => <span className="text-ink-2">{e.has_audio ? "Yes" : "No"}</span> },
    { key: "expires", header: "Kept until", sortValue: (e) => e.expires_at, cell: (e) => <span className="text-[13px] whitespace-nowrap text-ink-3">{fmtDay(e.expires_at)}</span> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (e) => <IconButton size="sm" label={`Delete ${e.title || "untitled"} from the catalogue`} icon={<Trash />} onClick={() => setDeleting(e)} />,
    },
  ];

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        title="Catalogue"
        description={
          agency
            ? "Index past posts so new videos are checked for reposts and for the same footage under a different client. Only a fingerprint is kept; the file is discarded. No AI or paid calls."
            : "Your past posts. New videos are checked against them for reposts. Only a fingerprint is kept; the file is discarded. No AI or paid calls."
        }
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <BulkAdd onDone={load} />
        <ServicesCard status={status} error={statusError} />
      </div>

      {loadError && <ErrorNotice title="Could not load the catalogue" message={loadError} onRetry={load} />}
      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
          <h2 className="mr-auto px-1 text-[15px] font-semibold">
            Indexed videos {shown && <span className="tabular font-normal text-ink-3">({shown.length})</span>}
          </h2>
          {agency && owners.length > 1 && (
            <Select aria-label="Filter by client" value={owner} onChange={(e) => setOwner(e.target.value)} className="w-56">
              <option value="all">All clients</option>
              {owners.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </Select>
          )}
        </div>
        <DataTable
          caption="Indexed videos"
          columns={columns}
          rows={shown}
          loading={!entries && !loadError}
          rowKey={(e) => e.id}
          initialSort={{ key: "expires", dir: "desc" }}
          empty={
            <EmptyState
              icon={<Film />}
              title="Nothing indexed yet"
              description="Reviewed videos are added automatically. Add past posts above to compare new videos against them too."
            />
          }
          card={(e) => (
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate font-medium">{e.title || "Untitled"}</div>
                <div className="mt-0.5 text-[12px] text-ink-3">
                  {agency ? `${e.owner_label} · ` : ""}
                  {fmtLength(e.duration_seconds)} · kept until {fmtDay(e.expires_at)}
                </div>
              </div>
              <IconButton size="sm" label={`Delete ${e.title || "untitled"} from the catalogue`} icon={<Trash />} onClick={() => setDeleting(e)} />
            </div>
          )}
        />
      </Card>
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Remove this fingerprint?"
        description={`“${deleting?.title || "Untitled"}” will no longer be matched against new reviews. The video itself is not affected.`}
        confirmLabel="Remove fingerprint"
        onConfirm={async () => {
          if (!deleting) return;
          await api.removeCatalogueEntry(deleting.id);
          toast({ tone: "success", title: "Fingerprint removed" });
          load();
        }}
      />
    </PageContainer>
  );
}

function BulkAdd({ onDone }: { onDone: () => void }) {
  const toast = useToast();
  const { agency, platforms } = useWorkspace();
  const [ownerLabel, setOwnerLabel] = useState("");
  const [platform, setPlatform] = useState<Platform | "">("");
  const [items, setItems] = useState<QueueItem[]>([]);
  const [running, setRunning] = useState(false);
  const runningRef = useRef(false);
  const abortRef = useRef<AbortController | null>(null);
  const [limits, setLimits] = useState(DEFAULT_LIMITS);

  // The catalogue uses the same upload cap as reviews (MAX_UPLOAD_MB).
  useEffect(() => {
    api
      .config()
      .then((c) => setLimits({ mb: c.max_upload_mb, seconds: c.catalogue_max_seconds ?? DEFAULT_LIMITS.seconds }))
      .catch(() => {});
  }, []);

  // Routes stay mounted (hidden) after navigation; start clean on the next visit.
  useLayoutEffect(
    () => () => {
      if (runningRef.current) return;
      setOwnerLabel("");
      setPlatform("");
      setItems([]);
    },
    [],
  );

  const update = (i: number, patch: Partial<QueueItem>) => setItems((prev) => prev.map((it, j) => (j === i ? { ...it, ...patch } : it)));

  function pick(list: File[]) {
    setItems(
      list.map((file): QueueItem => {
        const ext = file.name.toLowerCase().split(".").pop() ?? "";
        if (!["mp4", "mov", "webm"].includes(ext)) return { file, status: "error", progress: 0, message: "Only MP4, MOV and WebM are supported." };
        if (file.size > limits.mb * 1024 * 1024) return { file, status: "error", progress: 0, message: `Larger than ${fmtSize(limits.mb)}.` };
        return { file, status: "pending", progress: 0 };
      }),
    );
  }

  async function run() {
    runningRef.current = true;
    setRunning(true);
    const controller = new AbortController();
    abortRef.current = controller;
    const label = agency ? ownerLabel.trim() : OWN_POSTS;
    let added = 0;
    for (const [i, it] of items.entries()) {
      if (it.status !== "pending") continue;
      if (controller.signal.aborted) break;
      update(i, { status: "uploading", progress: 0 });
      const form = new FormData();
      form.append("file", it.file);
      form.append("owner_label", label);
      if (platform) form.append("platform", platform);
      form.append("title", it.file.name.replace(/\.[^.]+$/, "").slice(0, 300));
      try {
        const res = await addToCatalogue(form, (p) => update(i, { progress: p }), controller.signal);
        if (!res.duplicate) added += 1;
        update(i, {
          status: res.duplicate ? "duplicate" : "added",
          progress: 1,
          message: res.duplicate ? "Already indexed for this client." : res.truncated ? "Added; only the first part was fingerprinted." : undefined,
        });
      } catch (e) {
        if (isAbortError(e)) {
          update(i, { status: "pending", progress: 0 });
          break;
        }
        update(i, { status: "error", message: errorMessage(e) });
      }
    }
    runningRef.current = false;
    abortRef.current = null;
    setRunning(false);
    if (added) toast({ tone: "success", title: `${added} video${added === 1 ? "" : "s"} indexed` });
    else if (controller.signal.aborted) toast({ tone: "info", title: "Indexing stopped" });
    onDone();
  }

  const pending = items.filter((it) => it.status === "pending").length;

  return (
    <Section
      title={agency ? "Add past posts" : "Add your past posts"}
      description={`MP4, MOV or WebM · max ${fmtSize(limits.mb)} each · up to ${fmtMinutes(limits.seconds)} of each video is fingerprinted.`}
    >
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          {agency && (
            <Field label="Client or account" required hint="Who published these videos.">
              {(p) => <Input {...p} value={ownerLabel} onChange={(e) => setOwnerLabel(e.target.value.slice(0, 100))} disabled={running} />}
            </Field>
          )}
          <Field label="Platform">
            {(p) => (
              <Select {...p} value={platform} onChange={(e) => setPlatform(e.target.value as Platform | "")} disabled={running}>
                <option value="">Not specified</option>
                {platforms.map((pl) => (
                  <option key={pl.id} value={pl.id}>
                    {pl.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
        <Field label="Video files">
          {(p) => (
            <FilePicker
              {...p}
              accept={ACCEPT}
              multiple
              disabled={running}
              files={items.map((it) => it.file)}
              onFiles={pick}
              buttonLabel="Choose files"
              emptyLabel="No files chosen"
            />
          )}
        </Field>

        {items.length > 0 && (
          <ul className="divide-y divide-line rounded-[8px] border border-line" aria-live="polite" aria-label="Files to index">
            {items.map((it, i) => (
              <li key={`${it.file.name}-${i}`} className="flex items-center gap-3 px-3 py-2 text-[13px]">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium" title={it.file.name}>
                    {it.file.name}
                  </div>
                  <div className="text-[12px] text-ink-3">
                    {fmtBytes(it.file.size)}
                    {it.message && <span className={it.status === "error" ? "text-critical-fg" : ""}> · {it.message}</span>}
                  </div>
                  {it.status === "uploading" && <Progress size="sm" className="mt-1.5" value={it.progress < 1 ? it.progress * 100 : null} label={`Upload progress for ${it.file.name}`} />}
                </div>
                <ItemStatusLabel item={it} />
              </li>
            ))}
          </ul>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary" leadingIcon={<Upload />} onClick={run} loading={running} disabled={pending === 0 || (agency && !ownerLabel.trim())}>
            {running ? "Indexing…" : pending > 1 ? `Index ${pending} videos` : "Index video"}
          </Button>
          {running && (
            <Button variant="ghost" leadingIcon={<X />} onClick={() => abortRef.current?.abort()}>
              Stop
            </Button>
          )}
          {agency && !ownerLabel.trim() && pending > 0 && <p className="text-[13px] text-ink-3">Enter the client or account these videos belong to.</p>}
        </div>
      </div>
    </Section>
  );
}

function ItemStatusLabel({ item }: { item: QueueItem }) {
  switch (item.status) {
    case "pending":
      return <span className="text-[12px] text-ink-3">Waiting</span>;
    case "uploading":
      return (
        <span className="tabular inline-flex items-center gap-1 text-[12px] text-accent">
          <LoaderCircle className="size-3.5 animate-spin" aria-hidden />
          {item.progress < 1 ? `${Math.round(item.progress * 100)}%` : "Fingerprinting"}
        </span>
      );
    case "added":
      return (
        <Badge tone="success" icon={CircleCheck}>
          Added
        </Badge>
      );
    case "duplicate":
      return <Badge icon={Copy}>Duplicate</Badge>;
    default:
      return (
        <Badge tone="critical" icon={CircleX}>
          Error
        </Badge>
      );
  }
}

function ServicesCard({ status, error }: { status: ProvenanceStatus | null; error: string | null }) {
  if (error) return <ErrorNotice title="Could not load provenance services" message={error} />;
  if (!status) return <Skeleton className="h-72 w-full rounded-[10px]" />;
  const { budget, music_id, web_detection, youtube_search, catalogue } = status;
  const pct = budget.budget_usd > 0 ? Math.min(100, (budget.spent_usd / budget.budget_usd) * 100) : 0;
  const services = [
    {
      name: "Song identification",
      on: music_id.configured,
      detail: music_id.configured
        ? `${music_id.provider}${music_id.provider === "mock" ? " (mock)" : ""} · about ${fmtUsd(music_id.est_cost_per_call_usd)} per clip · ${music_id.auto ? "automatic" : "on request"}`
        : "Set MUSIC_ID_PROVIDER and AUDD_API_TOKEN",
    },
    {
      name: "Web image search",
      on: web_detection.configured,
      detail: web_detection.configured
        ? `${web_detection.provider}${web_detection.provider === "mock" ? " (mock)" : ""} · about ${fmtUsd(web_detection.est_cost_per_image_usd)} per image, up to ${web_detection.max_frames} · ${web_detection.auto ? "automatic on third-party cues" : "on request"}`
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
    <Section title="Provenance services">
      <div className="space-y-4">
        <div>
          <div className="flex justify-between text-[13px]">
            <span className="font-medium">Paid lookups this month</span>
            <span className="tabular text-ink-2">
              {fmtUsd(budget.spent_usd)} / {fmtUsd(budget.budget_usd)}
            </span>
          </div>
          <div
            className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-3"
            role="meter"
            aria-label="Monthly paid-lookup budget used"
            aria-valuemin={0}
            aria-valuemax={budget.budget_usd}
            aria-valuenow={budget.spent_usd}
          >
            <div className={`h-full rounded-full ${pct >= 90 ? "bg-critical-solid" : pct >= 70 ? "bg-medium-solid" : "bg-accent"}`} style={{ width: `${pct}%` }} />
          </div>
          <p className="mt-1 text-[12px] text-ink-3">
            Since {fmtDay(budget.month_start)} · {fmtUsd(budget.remaining_usd)} left · estimates, not invoices.
          </p>
          {Object.keys(budget.by_service).length > 0 && (
            <ul className="mt-1.5 space-y-0.5 text-[12px] text-ink-2">
              {Object.entries(budget.by_service).map(([svc, v]) => (
                <li key={svc} className="flex justify-between">
                  <span>
                    {SERVICE_LABEL[svc] ?? svc.replace(/_/g, " ")} · {v.calls} call{v.calls === 1 ? "" : "s"}
                  </span>
                  <span className="tabular">{fmtUsd(v.est_cost_usd)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <ul className="space-y-3 border-t border-line pt-4">
          {services.map((s) => (
            <li key={s.name} className="text-[13px]">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{s.name}</span>
                <span className="inline-flex items-center gap-1.5 text-[12px] text-ink-2">
                  <StatusDot tone={s.on ? "success" : "info"} />
                  {s.on ? "On" : "Off"}
                </span>
              </div>
              <p className="mt-0.5 text-[12px] text-ink-3">{s.detail}</p>
            </li>
          ))}
        </ul>
        <p className="border-t border-line pt-3 text-[12px] text-ink-3">
          <span className="tabular">{catalogue.entries}</span> fingerprint{catalogue.entries === 1 ? "" : "s"} indexed · kept for {catalogue.retention_days} days.
        </p>
      </div>
    </Section>
  );
}
