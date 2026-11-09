"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, type Analysis, type Finding, type FindingType, type Severity } from "@/lib/api";
import { OwnerFileForm } from "../OwnerFileForm";
import {
  fmtBytes,
  fmtDate,
  fmtTime,
  LANGUAGE_LABEL,
  MODE_LABEL,
  PLATFORM_LABEL,
  RISK_STYLE,
  SEVERITY_LABEL,
  SEVERITY_ORDER,
  SOURCE_LABEL,
  STAGE_LABEL,
  TYPE_LABEL,
} from "@/lib/format";
import { CheckIcon, DocIcon, DownloadIcon, TrashIcon } from "../icons";
import { Banner, Card, Skeleton } from "../ui";
import { FindingCard } from "./FindingCard";
import { ProvenanceSection } from "./ProvenanceSection";
import { VideoPanel, type VideoHandle } from "./VideoPanel";

export function AnalysisView() {
  const { id } = useParams<{ id: string }>();
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState<{ message: string; status: number } | null>(null);

  const load = useCallback(() => {
    api
      .get(id)
      .then((a) => {
        setAnalysis(a);
        setError(null);
      })
      .catch((e: ApiError) => setError({ message: e.message, status: e.status }));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const running = analysis?.status === "queued" || analysis?.status === "processing";
  useEffect(() => {
    if (!running) return;
    const t = setInterval(load, 1500);
    return () => clearInterval(t);
  }, [running, load]);

  if (error)
    return (
      <div className="mx-auto max-w-xl">
        <Banner tone="danger" title={error.status === 404 ? "Analysis not found" : "Could not load analysis"}>
          {error.status === 404 ? "It may have been deleted or expired under the retention policy." : error.message}
        </Banner>
        <Link href="/" className="mt-4 inline-block text-sm font-medium text-brand-700 hover:underline">← Back to analyses</Link>
      </div>
    );
  if (!analysis) return <LoadingSkeleton />;
  if (analysis.status === "awaiting_file") return <NeedsFileView analysis={analysis} onStarted={load} />;
  if (running) return <ProcessingView analysis={analysis} />;
  if (analysis.status === "failed") return <FailedView analysis={analysis} onRetry={load} />;
  return <ReviewDashboard analysis={analysis} onReload={load} />;
}

// --------------------------------------------------------------------------- processing

const STEPS = [
  { key: "queued", label: "Queued" },
  { key: "fetching_source", label: "Fetch from platform" },
  { key: "extracting_audio", label: "Extract audio", match: ["extracting", "extracting_audio"] },
  { key: "transcribing", label: "Transcribe speech" },
  { key: "sampling_frames", label: "Sample key frames" },
  { key: "reading_on_screen_text", label: "Read on-screen text" },
  { key: "provenance", label: "Provenance & rights checks" },
  { key: "rule_checks", label: "Rule-based checks" },
  { key: "ai_review", label: "AI policy review" },
  { key: "finalizing", label: "Build report" },
];

function ProcessingView({ analysis }: { analysis: Analysis }) {
  const idx = STEPS.findIndex((s) => (s.match ?? [s.key]).includes(analysis.stage));
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Header analysis={analysis} />
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Analysing your video…</h2>
          <span className="text-sm tabular-nums text-slate-500">{analysis.progress}%</span>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
          <div className="h-full rounded-full bg-brand-600 transition-all duration-700" style={{ width: `${analysis.progress}%` }} />
        </div>
        <ol className="mt-6 space-y-3">
          {STEPS.map((s, i) => {
            const done = i < idx;
            const active = i === idx;
            return (
              <li key={s.key} className="flex items-center gap-3 text-sm">
                <span
                  className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold ${
                    done ? "bg-emerald-500 text-white" : active ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-400"
                  }`}
                >
                  {done ? <CheckIcon className="h-3.5 w-3.5" /> : i + 1}
                </span>
                <span className={done ? "text-slate-500" : active ? "font-semibold text-slate-900" : "text-slate-400"}>
                  {s.label}
                  {active && <span className="ml-2 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500 align-middle" />}
                </span>
              </li>
            );
          })}
        </ol>
        <p className="mt-6 text-xs text-slate-500">
          Typically under a minute for a 60-second clip. The first run downloads the speech model and takes longer.
        </p>
      </Card>
    </div>
  );
}

function NeedsFileView({ analysis, onStarted }: { analysis: Analysis; onStarted: () => void }) {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Header analysis={analysis} />
      <Banner tone="info" title="Attach the original file to review the post in full">
        The platform record is saved. Frames, speech, on-screen text and audio are reviewed from the file you supply,
        then compared with this post&apos;s duration, caption and cover. This does not download the platform&apos;s video and
        does not identify music.
        <OwnerFileForm analysisId={analysis.id} onStarted={onStarted} />
      </Banner>
    </div>
  );
}

function FailedView({ analysis, onRetry }: { analysis: Analysis; onRetry: () => void }) {
  const [busy, setBusy] = useState(false);
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Header analysis={analysis} />
      <Banner tone="danger" title="Analysis failed">{analysis.error_message ?? "Unknown error."}</Banner>
      {analysis.source !== "upload" && (
        <Banner tone="info" title="You can attach the original file and run the review again">
          <OwnerFileForm analysisId={analysis.id} onStarted={onRetry} replace={analysis.owner_supplied_media} />
        </Banner>
      )}
      {!analysis.media_deleted && (
        <button
          type="button"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            await api.rerun(analysis.id).catch(() => {});
            onRetry();
            setBusy(false);
          }}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:bg-slate-300"
        >
          Retry analysis
        </button>
      )}
    </div>
  );
}

function CrossCheckCard({
  lines,
  analysisId,
  onReload,
}: {
  lines: { label: string; status: string; detail: string }[];
  analysisId: string;
  onReload: () => void;
}) {
  const tone: Record<string, string> = {
    ok: "text-emerald-800",
    warn: "text-amber-800",
    bad: "text-red-800",
    muted: "text-slate-500",
  };
  return (
    <Card className="p-5">
      <h2 className="text-sm font-semibold">Cross-check against the published post</h2>
      <p className="mt-1 text-xs text-slate-500">
        The file you supplied is compared with the platform record. This is not a Content ID or Rights Manager result,
        and it does not name a song.
      </p>
      <dl className="mt-4 space-y-3">
        {lines.map((line) => (
          <div key={line.label}>
            <dt className={`text-[11px] font-semibold uppercase tracking-wide ${tone[line.status] ?? "text-slate-500"}`}>
              {line.label}
            </dt>
            <dd className="mt-0.5 text-sm text-slate-700">{line.detail}</dd>
          </div>
        ))}
      </dl>
      <OwnerFileForm analysisId={analysisId} onStarted={onReload} replace />
    </Card>
  );
}

function LoadingSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
      <Skeleton className="aspect-[9/14] w-full rounded-xl" />
      <div className="space-y-4">
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- header

function Header({ analysis, actions }: { analysis: Analysis; actions?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <Link href="/" className="text-xs font-medium text-slate-500 hover:text-slate-800">← Analyses</Link>
        <h1 className="mt-1 max-w-2xl truncate text-xl font-semibold tracking-tight">
          {analysis.source_title?.trim() || analysis.caption?.trim().split("\n")[0] || "Untitled video"}
        </h1>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
          <span className="font-medium text-slate-700">{PLATFORM_LABEL[analysis.platform]}</span>
          {analysis.source !== "upload" && (
            <span className="rounded bg-slate-100 px-1.5 py-0.5 font-medium text-slate-700">
              {SOURCE_LABEL[analysis.source]} · {MODE_LABEL[analysis.analysis_mode]}
            </span>
          )}
          {analysis.source_url && (
            <a href={analysis.source_url} target="_blank" rel="noopener noreferrer" className="font-medium text-brand-700 hover:underline">
              View post ↗
            </a>
          )}
          <span>{LANGUAGE_LABEL[analysis.language]}</span>
          {analysis.duration_seconds != null && <span>{analysis.duration_seconds.toFixed(1)}s</span>}
          {analysis.media_info && <span>{analysis.media_info.width}×{analysis.media_info.height}</span>}
          {analysis.size_bytes > 0 && <span>{fmtBytes(analysis.size_bytes)}</span>}
          <span>Created {fmtDate(analysis.created_at)}</span>
        </div>
      </div>
      {actions}
    </div>
  );
}

// --------------------------------------------------------------------------- review

type Filter = "all" | Severity | "human_review";

function ReviewDashboard({ analysis, onReload }: { analysis: Analysis; onReload: () => void }) {
  const router = useRouter();
  const videoRef = useRef<VideoHandle>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [typeFilter, setTypeFilter] = useState<FindingType | "all">("all");
  const [highlight, setHighlight] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [tab, setTab] = useState<"transcript" | "ocr">("transcript");

  const actionable = useMemo(() => analysis.findings.filter((f) => f.finding_type !== "cannot_check"), [analysis]);
  const cannotCheck = useMemo(() => analysis.findings.filter((f) => f.finding_type === "cannot_check"), [analysis]);

  const filtered = actionable.filter(
    (f) =>
      (filter === "all" || (filter === "human_review" ? f.requires_human_review : f.severity === filter)) &&
      (typeFilter === "all" || f.finding_type === typeFilter),
  );
  const grouped = SEVERITY_ORDER.map((sev) => ({
    sev,
    items: filtered
      .filter((f) => f.severity === sev)
      .sort((a, b) => Number(a.rights_status != null) - Number(b.rights_status != null)),
  })).filter(
    (g) => g.items.length > 0,
  );

  const seek = (t: number) => videoRef.current?.seek(t);
  const focusFinding = (f: Finding) => {
    setFilter("all");
    setTypeFilter("all");
    setHighlight(null);
    requestAnimationFrame(() => {
      setHighlight(f.id);
      document.getElementById(`finding-${f.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  };

  const risk = analysis.risk_level ? RISK_STYLE[analysis.risk_level] : null;
  const counted = actionable.filter((f) => f.rights_status == null);
  const counts = SEVERITY_ORDER.map((s) => [s, counted.filter((f) => f.severity === s).length] as const);

  return (
    <div className="space-y-6">
      <Header
        analysis={analysis}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <a
              href={api.reportHtmlUrl(analysis.id)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium hover:bg-slate-50"
            >
              <DocIcon className="h-4 w-4" /> View report
            </a>
            <a
              href={api.reportHtmlUrl(analysis.id, true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700"
            >
              <DownloadIcon className="h-4 w-4" /> Download report
            </a>
            <a
              href={api.reportJsonUrl(analysis.id)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium hover:bg-slate-50"
            >
              JSON
            </a>
            <a
              href={api.evidencePackUrl(analysis.id)}
              title="Report, manifest, rights-ledger records and proofs, and a dispute draft"
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium hover:bg-slate-50"
            >
              <DownloadIcon className="h-4 w-4" /> Evidence pack
            </a>
            {confirmDelete ? (
              <span className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-red-50 px-2 py-1 text-sm">
                <span className="px-1 text-red-800">Delete video & report?</span>
                <button
                  type="button"
                  onClick={async () => {
                    await api.remove(analysis.id);
                    router.push("/");
                  }}
                  className="rounded-md bg-red-600 px-2 py-1 text-xs font-semibold text-white hover:bg-red-700"
                >
                  Delete
                </button>
                <button type="button" onClick={() => setConfirmDelete(false)} className="px-2 py-1 text-xs text-slate-600">
                  Cancel
                </button>
              </span>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmDelete(true)}
                title="Delete this analysis and its media"
                className="inline-flex items-center rounded-lg border border-slate-200 bg-white p-2 text-slate-500 hover:border-red-200 hover:text-red-600"
              >
                <TrashIcon className="h-4 w-4" />
              </button>
            )}
          </div>
        }
      />

      {analysis.extraction?.cross_check?.file_matches_post === "no" && (
        <Banner tone="danger" title="The supplied file does not match the published post">
          Its length or speech differs from what the platform reports, so this report describes the supplied file, which may
          not be the cut that is live. Attach the exact published file.
        </Banner>
      )}
      {analysis.analysis_mode === "metadata_only" && (
        <Banner tone="info" title="Metadata review only — the video itself was not analysed">
          YouTube&apos;s API policies don&apos;t allow downloading video or audio, so only the title, description, tags and
          {analysis.extraction?.transcript.segments.length ? " captions" : " hashtags (no captions were read)"} were checked.
          Attach the original file to review frames, speech, on-screen text and audio, and to cross-check that file
          against this post.
          <OwnerFileForm analysisId={analysis.id} onStarted={onReload} />
        </Banner>
      )}
      {analysis.analysis_mode === "caption_thumbnail" && (
        <Banner tone="warning" title="Caption + thumbnail review only — Instagram did not provide the video file">
          Instagram withholds the file for Reels with licensed audio (including its audio library) or copyright flags. Nothing
          shown or said inside the video was checked. Attach the original file to review it in full and cross-check it
          against this post. A withheld file is a signal to check the audio, not proof of a specific infringement.
          <OwnerFileForm analysisId={analysis.id} onStarted={onReload} />
        </Banner>
      )}
      {analysis.analysis_mode === "cross_checked" && analysis.extraction?.cross_check && (
        <CrossCheckCard
          lines={analysis.extraction.cross_check.lines}
          analysisId={analysis.id}
          onReload={onReload}
        />
      )}
      {analysis.mock_mode && (
        <Banner tone="mock" title="MOCK MODE — AI findings are placeholders">
          No AI model was called. Findings marked “AI review” are not a real assessment. Rule-based findings are real.
        </Banner>
      )}
      {!analysis.mock_mode && analysis.ai_status === "skipped" && (
        <Banner tone="warning" title="AI review did not run — rule-based checks only">{analysis.ai_status_detail}</Banner>
      )}
      {analysis.ai_status === "failed" && (
        <Banner tone="danger" title="AI review failed — rule-based checks only">{analysis.ai_status_detail}</Banner>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-[360px_1fr]">
        <aside className="space-y-4 lg:sticky lg:top-24">
          <Card className="p-4">
            <VideoPanel ref={videoRef} analysis={analysis} findings={analysis.findings} onMarkerClick={focusFinding} />
          </Card>
        </aside>

        <div className="min-w-0 space-y-6">
          {/* Risk + summary */}
          <Card className="overflow-hidden">
            <div className="grid gap-0 md:grid-cols-[220px_1fr]">
              <div className={`flex flex-col justify-center p-5 ${risk?.bg ?? "bg-slate-50"}`}>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Heuristic risk</div>
                <div className={`mt-1 text-3xl font-semibold ${risk?.text ?? ""}`}>{risk?.label ?? "—"}</div>
                <div className={`mt-2 h-1.5 overflow-hidden rounded-full bg-white/70 ${risk?.text ?? ""}`}>
                  <div className="h-full rounded-full bg-current opacity-70" style={{ width: `${analysis.risk_score ?? 0}%` }} />
                </div>
                <div className="mt-1 text-xs text-slate-500">Score {analysis.risk_score ?? 0}/100</div>
                <p className="mt-3 text-[11px] leading-snug text-slate-500">
                  A summary of the findings&apos; severity and confidence — not a probability of removal, strikes or suspension.
                </p>
              </div>
              <div className="space-y-3 p-5">
                <div className="flex flex-wrap gap-2">
                  {counts.map(([sev, n]) => (
                    <span key={sev} className="inline-flex items-center gap-1.5 rounded-md bg-slate-50 px-2 py-1 text-xs">
                      <span className={`h-2 w-2 rounded-full ${sevDot[sev]}`} />
                      <span className="font-semibold tabular-nums">{n}</span>
                      <span className="text-slate-500">{SEVERITY_LABEL[sev]}</span>
                    </span>
                  ))}
                </div>
                {analysis.summary && <p className="text-sm leading-relaxed text-slate-700">{analysis.summary}</p>}
                {analysis.context_assessment && (
                  <p className="text-sm text-slate-600">
                    <span className="font-semibold text-slate-800">Context: </span>
                    {analysis.context_assessment}
                  </p>
                )}
                <div className="text-[11px] text-slate-400">
                  AI: {analysis.ai_provider ?? "—"} / {analysis.ai_model ?? "—"} · Policy KB {analysis.policy_kb_version} ·
                  Retained until {fmtDate(analysis.expires_at)}
                </div>
              </div>
            </div>
          </Card>

          {/* Findings */}
          <section>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-base font-semibold">
                Findings <span className="text-slate-400">({counted.length})</span>
                {actionable.length > counted.length && (
                  <span className="ml-2 text-xs font-normal text-slate-500">
                    + {actionable.length - counted.length} covered or duplicate, not counted
                  </span>
                )}
              </h2>
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1">
                  {(["all", "critical", "high", "medium", "low", "info", "human_review"] as Filter[]).map((f) => (
                    <button
                      key={f}
                      type="button"
                      onClick={() => setFilter(f)}
                      className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                        filter === f ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      {f === "all" ? "All" : f === "human_review" ? "Needs human review" : SEVERITY_LABEL[f]}
                    </button>
                  ))}
                </div>
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value as FindingType | "all")}
                  className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs font-medium text-slate-700"
                  aria-label="Filter by finding type"
                >
                  <option value="all">All finding types</option>
                  {(["observed_evidence", "suspected_violation", "licensing_uncertainty"] as const).map((t) => (
                    <option key={t} value={t}>{TYPE_LABEL[t]}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-4 space-y-6">
              {actionable.length === 0 && (
                <Card className="flex items-center gap-3 p-5 text-sm text-slate-600">
                  <CheckIcon className="h-5 w-5 text-emerald-600" />
                  No issues were identified by the checks that ran. This does not guarantee compliance — see limitations below.
                </Card>
              )}
              {actionable.length > 0 && grouped.length === 0 && (
                <p className="text-sm text-slate-500">No findings match these filters.</p>
              )}
              {grouped.map((g) => (
                <div key={g.sev} className="space-y-3">
                  <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <span className={`h-2 w-2 rounded-full ${sevDot[g.sev]}`} />
                    {SEVERITY_LABEL[g.sev]} · {g.items.length}
                  </h3>
                  {g.items.map((f) => (
                    <FindingCard key={f.id} finding={f} onSeek={seek} highlighted={highlight === f.id} />
                  ))}
                </div>
              ))}
            </div>
          </section>

          {analysis.provenance && (
            <ProvenanceSection key={analysis.id} analysis={analysis} provenance={analysis.provenance} onSeek={seek} onReload={onReload} />
          )}

          {/* Checks not performed */}
          {cannotCheck.length > 0 && (
            <section>
              <h2 className="text-base font-semibold">Checks this tool cannot perform</h2>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                {cannotCheck.map((f) => (
                  <Card key={f.id} className="p-4">
                    <div className="text-sm font-semibold">{f.title}</div>
                    <p className="mt-1 text-[13px] leading-relaxed text-slate-600">{f.explanation}</p>
                  </Card>
                ))}
              </div>
            </section>
          )}

          {/* Transcript / OCR */}
          {analysis.extraction && (
            <Card>
              <div className="flex gap-1 border-b border-slate-100 px-4 pt-3">
                {(
                  [
                    ["transcript", `Transcript (${analysis.extraction.transcript.segments.length})`],
                    ["ocr", `On-screen text (${analysis.extraction.ocr.length})`],
                  ] as const
                ).map(([k, label]) => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => setTab(k)}
                    className={`-mb-px border-b-2 px-3 pb-2 text-sm font-medium ${
                      tab === k ? "border-brand-600 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-800"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="scroll-thin max-h-80 overflow-y-auto p-2">
                {tab === "transcript" &&
                  (analysis.extraction.transcript.segments.length === 0 ? (
                    <p className="p-3 text-sm text-slate-500">No speech detected.</p>
                  ) : (
                    analysis.extraction.transcript.segments.map((s) => (
                      <button
                        key={s.id}
                        type="button"
                        onClick={() => seek(s.start)}
                        className="flex w-full gap-3 rounded-md px-2 py-1.5 text-left text-sm hover:bg-slate-50"
                      >
                        <span className="w-10 flex-none font-mono text-[11px] text-slate-400">{s.id}</span>
                        <span className="w-20 flex-none font-mono text-[11px] text-brand-700">{fmtTime(s.start)}</span>
                        <span className="text-slate-700">{s.text}</span>
                      </button>
                    ))
                  ))}
                {tab === "ocr" &&
                  (analysis.extraction.ocr.length === 0 ? (
                    <p className="p-3 text-sm text-slate-500">No on-screen text detected.</p>
                  ) : (
                    analysis.extraction.ocr.map((o) => (
                      <button
                        key={o.id}
                        type="button"
                        onClick={() => seek(o.timestamp)}
                        className="flex w-full gap-3 rounded-md px-2 py-1.5 text-left text-sm hover:bg-slate-50"
                      >
                        <span className="w-10 flex-none font-mono text-[11px] text-slate-400">{o.id}</span>
                        <span className="w-20 flex-none font-mono text-[11px] text-brand-700">{fmtTime(o.timestamp)}</span>
                        <span className="text-slate-700">{o.text}</span>
                      </button>
                    ))
                  ))}
              </div>
              <div className="border-t border-slate-100 px-4 py-2 text-[11px] text-slate-400">
                Speech: {analysis.extraction.transcript.provider}
                {analysis.extraction.transcript.model && ` (${analysis.extraction.transcript.model})`} · automatic transcription and OCR
                may contain errors.
              </div>
            </Card>
          )}

          {/* Limitations */}
          <details className="group rounded-xl border border-slate-200 bg-white">
            <summary className="cursor-pointer select-none px-5 py-3 text-sm font-semibold">
              Limitations & notes ({analysis.limitations.length})
            </summary>
            <ul className="list-disc space-y-1.5 px-10 pb-4 text-[13px] text-slate-600">
              {analysis.limitations.map((l, i) => <li key={i}>{l}</li>)}
            </ul>
          </details>
          <p className="text-[11px] text-slate-400">Current stage: {STAGE_LABEL[analysis.stage] ?? analysis.stage}</p>
        </div>
      </div>
    </div>
  );
}

const sevDot: Record<Severity, string> = {
  critical: "bg-red-700",
  high: "bg-red-500",
  medium: "bg-amber-500",
  low: "bg-sky-600",
  info: "bg-slate-400",
};
