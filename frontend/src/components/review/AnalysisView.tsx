"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Braces,
  ChevronDown,
  CircleExclamationPoint,
  CircleX,
  Download,
  ExternalLink,
  FileText,
  Package,
  RefreshCw,
  Trash,
  UserCheck,
} from "lucide-react";
import { useCallback, useMemo, useRef, useState, type ReactNode } from "react";
import {
  api,
  errorMessage,
  safeUrl,
  type Analysis,
  type ChecklistItem,
  type Finding,
  type FindingType,
  type Severity,
  type SponsorshipRelationship,
} from "@/lib/api";
import { cn } from "@/lib/cn";
import {
  fmtBytes,
  fmtDate,
  fmtLength,
  fmtTime,
  LANGUAGE_LABEL,
  MODE_LABEL,
  reportSection,
  reviewTitle,
  SEVERITY_ORDER,
  SOURCE_LABEL,
  STAGE_LABEL,
  TYPE_LABEL,
} from "@/lib/format";
import { usePolledResource } from "@/lib/usePolledResource";
import { useWorkspace } from "@/lib/workspace";
import { BriefCheckTable } from "../creator/BriefCheckTable";
import { CaptionFixPanel } from "../creator/CaptionFixPanel";
import { MarketLabelTable, ReadinessPanel } from "../creator/Readiness";
import { BriefSummary } from "../creator/BriefPicker";
import { MarketChips } from "../ReviewsPage";
import { OwnerFileForm } from "../OwnerFileForm";
import { PageContainer } from "../shell/AppShell";
import {
  Badge,
  Button,
  ButtonLink,
  Callout,
  Card,
  ConfirmDialog,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLink,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  EmptyState,
  ErrorNotice,
  Progress,
  SegmentedControl,
  Select,
  SEVERITY_ICON,
  SEVERITY_TEXT,
  Skeleton,
  Stepper,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  SOLID,
  TONE_TEXT,
  buttonClasses,
  useToast,
  RISK,
  type StepState,
} from "../ui";
import { FindingCard } from "./FindingCard";
import { ProvenanceSection } from "./ProvenanceSection";
import { VideoPanel, type VideoHandle } from "./VideoPanel";

export function AnalysisView() {
  const { id } = useParams<{ id: string }>();
  // A new id is a new resource: remount so polling state never leaks between reviews.
  return <AnalysisLoader key={id} id={id} />;
}

const isRunning = (a: Analysis) => a.status === "queued" || a.status === "processing";

function AnalysisLoader({ id }: { id: string }) {
  const fetcher = useCallback((signal: AbortSignal) => api.get(id, signal), [id]);
  const { data: analysis, error, autoRetry, stopped, reload, dismissError } = usePolledResource(fetcher, {
    intervalMs: 1500,
    maxBackoffMs: 30_000,
    shouldPoll: isRunning,
  });

  if (stopped === "gone")
    return (
      <PageContainer className="max-w-xl">
        <Card>
          <EmptyState
            icon={<CircleX />}
            title="This review was deleted or has expired"
            description="It may have been deleted, or removed under the retention policy."
            action={
              <ButtonLink href="/dashboard" leadingIcon={<ArrowLeft />}>
                Back to overview
              </ButtonLink>
            }
          />
        </Card>
      </PageContainer>
    );
  if (stopped === "auth")
    return (
      <PageContainer className="max-w-xl">
        <p className="text-sm text-ink-2">This review can be shown again once you have signed in.</p>
      </PageContainer>
    );
  if (!analysis) {
    if (!error) return <LoadingSkeleton />;
    return (
      <PageContainer className="max-w-xl space-y-4">
        <ErrorNotice
          title="Could not load this review"
          message={error.message}
          note={autoRetry ? "Retrying automatically…" : undefined}
          onRetry={reload}
        />
        <BackLink />
      </PageContainer>
    );
  }

  // A failed refresh keeps the last good report on screen.
  const notice = error && (
    <ErrorNotice
      title={isRunning(analysis) ? "Lost contact with the server" : "Could not refresh this review"}
      message={error.message}
      note={autoRetry ? "Retrying automatically…" : "The report below is the last version that loaded."}
      onRetry={reload}
      onDismiss={dismissError}
    />
  );
  let view: ReactNode;
  if (analysis.status === "awaiting_file") view = <NeedsFileView analysis={analysis} onStarted={reload} />;
  else if (isRunning(analysis)) view = <ProcessingView analysis={analysis} />;
  else if (analysis.status === "failed") view = <FailedView analysis={analysis} onRetry={reload} />;
  else view = <ReviewDashboard analysis={analysis} onReload={reload} />;
  return (
    <div className="space-y-4">
      {notice}
      {view}
    </div>
  );
}

function BackLink() {
  return (
    <Link href="/dashboard" className="inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline">
      <ArrowLeft className="size-4" aria-hidden /> Back to overview
    </Link>
  );
}

function LoadingSkeleton() {
  return (
    <PageContainer wide className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-4 w-1/3" />
      </div>
      <Skeleton className="h-36 w-full rounded-[10px]" />
      <div className="grid gap-6 lg:grid-cols-[minmax(300px,380px)_minmax(0,1fr)]">
        <Skeleton className="aspect-[9/14] w-full rounded-[10px]" />
        <div className="space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-32 w-full rounded-[10px]" />
          <Skeleton className="h-32 w-full rounded-[10px]" />
        </div>
      </div>
    </PageContainer>
  );
}

// --------------------------------------------------------------------------- header

function ReviewHeader({ analysis, actions }: { analysis: Analysis; actions?: ReactNode }) {
  const { platformLabel, agency } = useWorkspace();
  const postUrl = safeUrl(analysis.source_url);
  const mi = analysis.media_info;
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
      <div className="min-w-0 flex-1">
        <h1 className="line-clamp-2 text-[20px] leading-7 font-[650] tracking-tight break-words md:line-clamp-1 md:text-[24px] md:leading-8" title={reviewTitle(analysis)}>
          {reviewTitle(analysis)}
        </h1>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[13px] text-ink-3">
          <span className="font-medium text-ink-2">{platformLabel(analysis.platform)}</span>
          {analysis.markets?.length > 0 && <MarketChips markets={analysis.markets} />}
          {analysis.source !== "upload" && (
            <Badge>
              {SOURCE_LABEL[analysis.source]} · {MODE_LABEL[analysis.analysis_mode]}
            </Badge>
          )}
          {analysis.mock_mode && <Badge tone="medium">MOCK</Badge>}
          {agency && analysis.client_label && <span>Client: {analysis.client_label}</span>}
          <span>{LANGUAGE_LABEL[analysis.language]}</span>
          {analysis.duration_seconds != null && <span className="tabular">{fmtLength(analysis.duration_seconds)}</span>}
          {mi?.original ? (
            <span className="tabular" title="Large files are reviewed from a smaller working copy">
              {mi.original.width}×{mi.original.height}, reviewed at {mi.width}×{mi.height}
            </span>
          ) : (
            mi && (
              <span className="tabular">
                {mi.width}×{mi.height}
              </span>
            )
          )}
          {analysis.size_bytes > 0 && <span className="tabular">{fmtBytes(analysis.size_bytes)}</span>}
          <span>Created {fmtDate(analysis.created_at)}</span>
          {postUrl && (
            <a href={postUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-medium text-accent hover:underline">
              View post <ExternalLink className="size-3.5" aria-hidden />
            </a>
          )}
        </div>
      </div>
      {actions}
    </div>
  );
}

function ReviewActions({ analysis, onReload }: { analysis: Analysis; onReload: () => void }) {
  const router = useRouter();
  const toast = useToast();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const completed = analysis.status === "completed";
  const canRerun = !(analysis.source === "upload" && analysis.media_deleted) && !isRunning(analysis);

  async function rerun() {
    try {
      await api.rerun(analysis.id);
      toast({ tone: "success", title: "Review restarted", description: "The page updates as each step finishes." });
      onReload();
    } catch (e) {
      toast({ tone: "error", title: "Could not re-run the review", description: errorMessage(e) });
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {completed && (
        <a href={api.reportHtmlUrl(analysis.id, true)} className={buttonClasses("secondary", "md")}>
          <Download aria-hidden />
          Download report
        </a>
      )}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button trailingIcon={<ChevronDown />}>Actions</Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          {completed && (
            <>
              <DropdownMenuLink icon={<FileText />} href={api.reportHtmlUrl(analysis.id)} external>
                Open report in a new tab
              </DropdownMenuLink>
              <DropdownMenuLink icon={<Download />} href={api.reportHtmlUrl(analysis.id, true)}>
                Download report
              </DropdownMenuLink>
              <DropdownMenuLink icon={<Braces />} href={api.reportJsonUrl(analysis.id)}>
                Download JSON
              </DropdownMenuLink>
              <DropdownMenuLink icon={<Package />} href={api.evidencePackUrl(analysis.id)}>
                Download evidence pack
              </DropdownMenuLink>
              <DropdownMenuSeparator />
            </>
          )}
          <DropdownMenuItem icon={<RefreshCw />} disabled={!canRerun} onSelect={rerun}>
            Re-run review
          </DropdownMenuItem>
          <DropdownMenuItem icon={<Trash />} tone="danger" onSelect={() => setConfirmDelete(true)}>
            Delete review
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete this review?"
        description="The video, frames, transcript and report are deleted now. This cannot be undone."
        confirmLabel="Delete review"
        onConfirm={async () => {
          await api.remove(analysis.id);
          toast({ tone: "success", title: "Review deleted" });
          router.push("/dashboard");
        }}
      />
    </div>
  );
}

// --------------------------------------------------------------------------- non-final states

const STEPS = [
  { key: "queued", label: "Queued" },
  { key: "fetching_source", label: "Fetch from platform" },
  { key: "optimizing_video", label: "Make a smaller working copy (large files)" },
  { key: "extracting_audio", label: "Extract audio", match: ["extracting", "extracting_audio"] },
  { key: "transcribing", label: "Transcribe speech" },
  { key: "sampling_frames", label: "Sample key frames" },
  { key: "reading_on_screen_text", label: "Read on-screen text" },
  { key: "provenance", label: "Provenance and rights checks" },
  { key: "rule_checks", label: "Rule-based checks" },
  { key: "ai_review", label: "AI policy review" },
  { key: "finalizing", label: "Build report" },
];

function ProcessingView({ analysis }: { analysis: Analysis }) {
  const idx = STEPS.findIndex((s) => (s.match ?? [s.key]).includes(analysis.stage));
  const steps = STEPS.map((s, i) => ({ label: s.label, state: (i < idx ? "done" : i === idx ? "current" : "todo") as StepState }));
  return (
    <PageContainer className="max-w-2xl space-y-6">
      <ReviewHeader analysis={analysis} />
      <Card className="p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-[18px] leading-[26px] font-semibold">Reviewing your video</h2>
          <span className="tabular text-sm text-ink-3">{analysis.progress}%</span>
        </div>
        <p className="mt-1 text-[13px] text-ink-3">{STAGE_LABEL[analysis.stage] ?? analysis.stage}</p>
        <Progress value={analysis.progress} label="Review progress" className="mt-4" />
        <div className="mt-6">
          <Stepper label="Review steps" steps={steps} />
        </div>
        <p className="mt-6 text-[13px] text-ink-3">
          About a minute for a one-minute clip; longer videos take a few minutes. You can leave this page; the review keeps running.
        </p>
      </Card>
    </PageContainer>
  );
}

function NeedsFileView({ analysis, onStarted }: { analysis: Analysis; onStarted: () => void }) {
  return (
    <PageContainer className="max-w-2xl space-y-6">
      <ReviewHeader analysis={analysis} actions={<ReviewActions analysis={analysis} onReload={onStarted} />} />
      <Card className="p-5">
        <h2 className="text-[15px] font-semibold">Attach the original file to review the post in full</h2>
        <p className="mt-1 mb-4 text-[13px] text-ink-2">
          The platform record is saved. Frames, speech, on-screen text and audio are reviewed from the file you supply, then
          compared with this post’s duration, caption and cover. The platform’s video is not downloaded and music is not identified.
        </p>
        <OwnerFileForm analysisId={analysis.id} onStarted={onStarted} />
      </Card>
    </PageContainer>
  );
}

function FailedView({ analysis, onRetry }: { analysis: Analysis; onRetry: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  return (
    <PageContainer className="max-w-2xl space-y-6">
      <ReviewHeader analysis={analysis} actions={<ReviewActions analysis={analysis} onReload={onRetry} />} />
      <Callout
        tone="danger"
        title="The review did not finish"
        action={
          !analysis.media_deleted ? (
            <Button
              variant="primary"
              size="sm"
              leadingIcon={<RefreshCw />}
              loading={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await api.rerun(analysis.id);
                  onRetry();
                } catch (e) {
                  toast({ tone: "error", title: "Could not retry the review", description: errorMessage(e) });
                } finally {
                  setBusy(false);
                }
              }}
            >
              Retry review
            </Button>
          ) : undefined
        }
      >
        {analysis.error_message ?? "Unknown error."}
      </Callout>
      {analysis.source !== "upload" && (
        <Card className="p-5">
          <h2 className="mb-3 text-[15px] font-semibold">Or attach the original file and run the review again</h2>
          <OwnerFileForm analysisId={analysis.id} onStarted={onRetry} replace={analysis.owner_supplied_media} />
        </Card>
      )}
    </PageContainer>
  );
}

// --------------------------------------------------------------------------- verdict

/** Risk indicator, summary and counts: secondary to the readiness verdict. */
function RiskSummary({ analysis, actionable, wide }: { analysis: Analysis; actionable: Finding[]; wide?: boolean }) {
  const counted = actionable.filter((f) => f.rights_status == null);
  const notCounted = actionable.length - counted.length;
  const human = counted.filter((f) => f.requires_human_review).length;
  const cannot = analysis.findings.filter((f) => f.finding_type === "cannot_check").length;
  const v = analysis.risk_level ? RISK[analysis.risk_level] : null;
  const score = analysis.risk_score ?? 0;

  return (
    <Card className={cn("p-5", wide && "md:grid md:grid-cols-[minmax(0,1fr)_minmax(240px,320px)] md:gap-6")}>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-[13px] font-semibold text-ink">Risk indicator</h3>
          {v && (
            <span className={cn("inline-flex items-center gap-1 text-[13px] font-semibold", TONE_TEXT[v.tone])}>
              <v.icon className="size-4" aria-hidden /> {v.label}
            </span>
          )}
        </div>
        <div className="mt-2 flex items-center gap-3">
          <div className="h-1.5 w-32 shrink-0 overflow-hidden rounded-full bg-surface-3" aria-hidden>
            <div className={cn("h-full rounded-full", v ? SOLID[v.tone] : "bg-ink-3")} style={{ width: `${score}%` }} />
          </div>
          <span className="tabular text-[13px] whitespace-nowrap text-ink-2">Score {score}/100</span>
        </div>
        <p className="mt-1 text-[12px] text-ink-3">A summary of severity and confidence, not a probability of removal, strikes or suspension.</p>
        {analysis.summary && <p className="mt-3 max-w-[72ch] text-[13px] leading-5 text-ink">{analysis.summary}</p>}
        {analysis.context_assessment && (
          <p className="mt-2 max-w-[72ch] text-[13px] text-ink-2">
            <span className="font-semibold text-ink">Context: </span>
            {analysis.context_assessment}
          </p>
        )}
      </div>
      <div className={cn("mt-4", wide && "md:mt-0")}>
        <ul className="grid grid-cols-5 gap-1.5" aria-label="Counted findings by severity">
          {SEVERITY_ORDER.map((sv) => {
            const n = counted.filter((f) => f.severity === sv).length;
            const I = SEVERITY_ICON[sv];
            return (
              <li key={sv} className={cn("rounded-[6px] border border-line bg-surface-2 px-1 py-1.5 text-center", n === 0 && "opacity-60")}>
                <div className={cn("flex items-center justify-center gap-1", n ? TONE_TEXT[sv] : "text-ink-3")}>
                  <I className="size-3.5" aria-hidden />
                  <span className="tabular text-[15px] font-semibold">{n}</span>
                </div>
                <div className="text-[11px] text-ink-3">{SEVERITY_TEXT[sv]}</div>
              </li>
            );
          })}
        </ul>
        <ul className="mt-3 space-y-1.5 text-[13px] text-ink-2">
          <li className="flex gap-2">
            <UserCheck className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
            {human} finding{human === 1 ? "" : "s"} need human review
          </li>
          {cannot > 0 && (
            <li className="flex gap-2">
              <CircleX className="mt-0.5 size-4 shrink-0 text-ink-3" aria-hidden />
              {cannot} check{cannot === 1 ? "" : "s"} this tool cannot perform
            </li>
          )}
          {notCounted > 0 && (
            <li className="flex gap-2 text-ink-3">
              <CircleExclamationPoint className="mt-0.5 size-4 shrink-0" aria-hidden />
              {notCounted} covered or duplicate, not counted
            </li>
          )}
        </ul>
      </div>
    </Card>
  );
}

// --------------------------------------------------------------------------- completed review

type Filter = "all" | Severity | "human_review";

type GroupKey = "disclosure" | "community" | "brief" | "rights" | "other";

const GROUPS: { key: GroupKey; title: string; note: string; empty: string; always?: boolean }[] = [
  {
    key: "disclosure",
    title: "Sponsored-content disclosure",
    note: "Paid-promotion and sponsorship signals for this platform and the selected markets. These checks do not confirm the platform’s paid-promotion setting.",
    empty: "No sponsorship-disclosure issue was flagged in the text that was checked. This is not a clearance.",
    always: true,
  },
  {
    key: "community",
    title: "Community guidelines",
    note: "Flags for content that may lead to a strike, removal, age restriction, reduced distribution or lost monetisation. The rule check reads speech, on-screen text, caption and hashtags; it does not classify imagery.",
    empty: "No community-guideline flags in the text that was checked. This is not a clearance.",
    always: true,
  },
  {
    key: "brief",
    title: "Brand brief",
    note: "What the sponsor asked for, compared with the caption, speech and on-screen text.",
    empty: "Every brief requirement that could be checked was met.",
  },
  {
    key: "rights",
    title: "Rights and reused content",
    note: "Music, footage, other creators’ content and earlier posts.",
    empty: "Nothing in this group.",
  },
  {
    key: "other",
    title: "Other findings",
    note: "Claims, monetisation and other signals outside the groups above.",
    empty: "Nothing in this group.",
  },
];

/** Group a finding: the readiness checklist knows which area each finding belongs to. */
function groupOf(f: Finding, byChecklist: Map<string, string>): GroupKey {
  if (f.report_section === "brief" || f.category === "brand_brief") return "brief";
  const key = byChecklist.get(f.id);
  if (key === "disclosure" || key === "community" || key === "rights" || key === "brief") return key;
  if (key === "claims") return "other";
  if (f.category === "licensing" || f.category === "originality" || f.source === "provenance") return "rights";
  const section = reportSection(f);
  return section === "disclosure" || section === "community" ? section : "other";
}

function ReviewDashboard({ analysis, onReload }: { analysis: Analysis; onReload: () => void }) {
  const videoRef = useRef<VideoHandle>(null);
  const [tab, setTab] = useState("findings");
  const [filter, setFilter] = useState<Filter>("all");
  const [typeFilter, setTypeFilter] = useState<FindingType | "all">("all");
  const [highlight, setHighlight] = useState<Set<string>>(new Set());
  const [textTab, setTextTab] = useState<"speech" | "ocr">("speech");

  const actionable = useMemo(() => analysis.findings.filter((f) => f.finding_type !== "cannot_check"), [analysis]);
  const cannotCheck = useMemo(() => analysis.findings.filter((f) => f.finding_type === "cannot_check"), [analysis]);
  const filtered = actionable.filter(
    (f) =>
      (filter === "all" || (filter === "human_review" ? f.requires_human_review : f.severity === filter)) &&
      (typeFilter === "all" || f.finding_type === typeFilter),
  );

  const seek = (t: number) => videoRef.current?.seek(t);
  /** Show these findings: Findings tab, filters cleared, highlighted, first one scrolled into view. */
  const focusFindings = (ids: string[]) => {
    if (!ids.length) return;
    setTab("findings");
    setFilter("all");
    setTypeFilter("all");
    setHighlight(new Set());
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        setHighlight(new Set(ids));
        const first = ids.map((id) => document.getElementById(`finding-${id}`)).find(Boolean);
        first?.scrollIntoView({ behavior: "smooth", block: "center" });
        (first?.querySelector("button") as HTMLButtonElement | null)?.focus({ preventScroll: true });
      }),
    );
  };
  const focusFinding = (f: Finding) => focusFindings([f.id]);
  const onChecklistRow = (item: ChecklistItem) => focusFindings(item.finding_ids);
  const byChecklist = useMemo(() => {
    const m = new Map<string, string>();
    analysis.readiness?.checklist.forEach((c) => c.finding_ids.forEach((id) => m.set(id, c.key)));
    return m;
  }, [analysis]);
  const hasCaptionTab = !!(analysis.market_disclosure || analysis.caption_fix?.needed);
  const counted = actionable.filter((f) => f.rights_status == null).length;
  const ex = analysis.extraction;

  return (
    <PageContainer wide className="space-y-5">
      <ReviewHeader analysis={analysis} actions={<ReviewActions analysis={analysis} onReload={onReload} />} />

      {analysis.readiness ? (
        <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
          <ReadinessPanel readiness={analysis.readiness} onRow={onChecklistRow} />
          <RiskSummary analysis={analysis} actionable={actionable} />
        </div>
      ) : (
        <RiskSummary analysis={analysis} actionable={actionable} wide />
      )}

      {ex?.cross_check?.file_matches_post === "no" && (
        <Callout tone="danger" title="The supplied file does not match the published post">
          Its length or speech differs from what the platform reports, so this report describes the supplied file, which may not
          be the cut that is live. Attach the exact published file.
        </Callout>
      )}
      {analysis.mock_mode && (
        <Callout tone="warning" title="Mock mode: AI findings are placeholders">
          No AI model was called. Findings marked “AI review” are not a real assessment. Rule-based findings are real.
        </Callout>
      )}
      {!analysis.mock_mode && analysis.ai_status === "skipped" && (
        <Callout tone="warning" title="AI review did not run: rule-based checks only">
          {analysis.ai_status_detail}
        </Callout>
      )}
      {analysis.ai_status === "failed" && (
        <Callout tone="danger" title="AI review failed: rule-based checks only">
          {analysis.ai_status_detail}
        </Callout>
      )}
      {analysis.analysis_mode === "metadata_only" && (
        <Card className="p-5">
          <Callout tone="info" title="Metadata review only: the video itself was not reviewed" className="mb-4">
            YouTube’s API policies do not allow downloading video or audio, so only the title, description, tags and
            {ex?.transcript.segments.length ? " captions" : " hashtags (no captions were read)"} were checked. Attach the original
            file to review frames, speech, on-screen text and audio, and to cross-check it against this post.
          </Callout>
          <OwnerFileForm analysisId={analysis.id} onStarted={onReload} />
        </Card>
      )}
      {analysis.analysis_mode === "caption_thumbnail" && (
        <Card className="p-5">
          <Callout tone="warning" title="Caption and thumbnail only: Instagram did not provide the video file" className="mb-4">
            Instagram withholds the file for Reels with licensed audio (including its audio library) or copyright flags. Nothing
            shown or said inside the video was checked. A withheld file is a signal to check the audio, not proof of a specific
            infringement.
          </Callout>
          <OwnerFileForm analysisId={analysis.id} onStarted={onReload} />
        </Card>
      )}
      {analysis.analysis_mode === "cross_checked" && ex?.cross_check && <CrossCheckCard lines={ex.cross_check.lines} analysisId={analysis.id} onReload={onReload} />}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(300px,380px)_minmax(0,1fr)]">
        <aside aria-label="Video" className="lg:sticky lg:top-[72px]">
          <Card className="p-3">
            <VideoPanel ref={videoRef} analysis={analysis} findings={analysis.findings} onMarkerClick={focusFinding} />
          </Card>
        </aside>

        <Tabs value={tab} onValueChange={setTab} className="min-w-0">
          <TabsList aria-label="Review sections">
            <TabsTrigger value="findings" count={counted}>
              Findings
            </TabsTrigger>
            {hasCaptionTab && <TabsTrigger value="caption">Caption</TabsTrigger>}
            {ex && <TabsTrigger value="text">Transcript and on-screen text</TabsTrigger>}
            {analysis.provenance && <TabsTrigger value="rights">Rights and provenance</TabsTrigger>}
            <TabsTrigger value="details">Details</TabsTrigger>
          </TabsList>

          <TabsContent value="findings" className="space-y-8">
            <div className="flex flex-wrap items-center gap-2">
              <div className="scroll-thin max-w-full overflow-x-auto">
                <SegmentedControl
                  size="sm"
                  label="Filter by severity"
                  value={filter}
                  onChange={setFilter}
                  options={[
                    { value: "all", label: "All" },
                    ...SEVERITY_ORDER.map((s) => ({ value: s, label: SEVERITY_TEXT[s] })),
                    { value: "human_review", label: "Needs human review" },
                  ]}
                />
              </div>
              <Select
                aria-label="Filter by finding type"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value as FindingType | "all")}
                className="w-52"
              >
                <option value="all">All finding types</option>
                {(["observed_evidence", "suspected_violation", "licensing_uncertainty"] as const).map((t) => (
                  <option key={t} value={t}>
                    {TYPE_LABEL[t]}
                  </option>
                ))}
              </Select>
            </div>
            {actionable.length > 0 && filtered.length === 0 && (
              <p className="text-sm text-ink-3">No findings match these filters.</p>
            )}
            {GROUPS.map((g) => {
              const total = actionable.filter((f) => groupOf(f, byChecklist) === g.key);
              const showBrief = g.key === "brief" && !!analysis.brief_check;
              if (!g.always && total.length === 0 && !showBrief) return null;
              const items = filtered
                .filter((f) => groupOf(f, byChecklist) === g.key)
                .sort(
                  (a, b) =>
                    SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity) ||
                    Number(a.rights_status != null) - Number(b.rights_status != null),
                );
              return (
                <section key={g.key} aria-labelledby={`group-${g.key}`} className="space-y-3">
                  <div>
                    <h3 id={`group-${g.key}`} className="flex items-center gap-2 text-[15px] font-semibold">
                      {g.title}
                      <span className="tabular rounded-full bg-surface-3 px-1.5 text-[11px] leading-4 font-semibold text-ink-2">{total.length}</span>
                    </h3>
                    <p className="mt-0.5 max-w-[80ch] text-[13px] text-ink-3">{g.note}</p>
                    {g.key === "disclosure" && <DeclaredSponsorship sponsorship={analysis.sponsorship} />}
                  </div>
                  {showBrief && analysis.brief_check && (
                    <div className="space-y-3 rounded-[10px] border border-line bg-surface p-4">
                      <BriefCheckTable check={analysis.brief_check} onSeek={seek} />
                      {analysis.brief && (
                        <details className="text-[13px]">
                          <summary className="cursor-pointer text-accent select-none hover:underline">What the brief asked for</summary>
                          <div className="mt-2">
                            <BriefSummary brief={analysis.brief} />
                          </div>
                        </details>
                      )}
                    </div>
                  )}
                  {items.length === 0 ? (
                    <p className="rounded-[10px] border border-dashed border-line-strong px-4 py-3 text-[13px] text-ink-3">
                      {total.length > 0 ? "Nothing in this group matches the filters." : g.empty}
                    </p>
                  ) : (
                    items.map((f) => <FindingCard key={f.id} finding={f} onSeek={seek} highlighted={highlight.has(f.id)} />)
                  )}
                </section>
              );
            })}
            {cannotCheck.length > 0 && (
              <section aria-labelledby="group-cannot" className="space-y-3">
                <div>
                  <h3 id="group-cannot" className="text-[15px] font-semibold">
                    Checks this tool cannot perform
                  </h3>
                  <p className="mt-0.5 text-[13px] text-ink-3">Review these yourself before posting.</p>
                </div>
                <div className="grid gap-3 xl:grid-cols-2">
                  {cannotCheck.map((f) => (
                    <div key={f.id} className="rounded-[10px] border border-line bg-surface-2 p-4">
                      <div className="text-sm font-semibold">{f.title}</div>
                      <p className="mt-1 text-[13px] text-ink-2">{f.explanation}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </TabsContent>

          {hasCaptionTab && (
            <TabsContent value="caption" className="space-y-6">
              {analysis.market_disclosure && (
                <section aria-labelledby="caption-labels" className="space-y-2">
                  <h3 id="caption-labels" className="text-[15px] font-semibold">
                    Disclosure by market
                  </h3>
                  <p className="text-[13px] text-ink-3">Which disclosure labels in the caption each selected market treats as clear.</p>
                  <MarketLabelTable md={analysis.market_disclosure} />
                </section>
              )}
              {analysis.caption_fix?.needed && (
                <section aria-labelledby="caption-fix" className="space-y-2">
                  <h3 id="caption-fix" className="text-[15px] font-semibold">
                    Suggested caption
                  </h3>
                  <CaptionFixPanel fix={analysis.caption_fix} original={analysis.caption} />
                </section>
              )}
            </TabsContent>
          )}

          {ex && (
            <TabsContent value="text" className="space-y-3">
              <SegmentedControl
                label="Extracted text"
                size="sm"
                value={textTab}
                onChange={setTextTab}
                options={[
                  { value: "speech", label: `Speech (${ex.transcript.segments.length})` },
                  { value: "ocr", label: `On-screen text (${ex.ocr.length})` },
                ]}
              />
              <Card>
                <ul className="scroll-thin max-h-[60vh] divide-y divide-line overflow-y-auto">
                  {textTab === "speech" &&
                    (ex.transcript.segments.length === 0 ? (
                      <li className="p-4 text-sm text-ink-3">No speech detected.</li>
                    ) : (
                      ex.transcript.segments.map((s) => (
                        <TextRow key={s.id} id={s.id} time={s.start} text={s.text} onSeek={seek} />
                      ))
                    ))}
                  {textTab === "ocr" &&
                    (ex.ocr.length === 0 ? (
                      <li className="p-4 text-sm text-ink-3">No on-screen text detected.</li>
                    ) : (
                      ex.ocr.map((o) => <TextRow key={o.id} id={o.id} time={o.timestamp} text={o.text} onSeek={seek} />)
                    ))}
                </ul>
              </Card>
              <p className="text-[12px] text-ink-3">
                Speech: {ex.transcript.provider}
                {ex.transcript.model && ` (${ex.transcript.model})`}. Automatic transcription and text recognition can contain errors.
              </p>
            </TabsContent>
          )}

          {analysis.provenance && (
            <TabsContent value="rights">
              <ProvenanceSection key={analysis.id} analysis={analysis} provenance={analysis.provenance} onSeek={seek} onReload={onReload} />
            </TabsContent>
          )}

          <TabsContent value="details" className="space-y-5">
            <DetailsPanel analysis={analysis} />
          </TabsContent>
        </Tabs>
      </div>
    </PageContainer>
  );
}

function TextRow({ id, time, text, onSeek }: { id: string; time: number; text: string; onSeek: (t: number) => void }) {
  return (
    <li>
      <button
        type="button"
        onClick={() => onSeek(time)}
        aria-label={`Play from ${fmtTime(time)}: ${text}`}
        className="flex w-full gap-3 px-4 py-2.5 text-left text-sm hover:bg-surface-2 focus-visible:outline-offset-[-2px]"
      >
        <span className="w-9 flex-none font-mono text-[11px] leading-[22px] text-ink-3">{id}</span>
        <span className="tabular w-16 flex-none text-[12px] leading-[22px] font-medium text-accent">{fmtTime(time)}</span>
        <span className="text-ink">{text}</span>
      </button>
    </li>
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
    ok: "text-success-fg",
    warn: "text-medium-fg",
    bad: "text-critical-fg",
    muted: "text-ink-3",
  };
  return (
    <Card className="p-5">
      <h2 className="text-[15px] font-semibold">Cross-check against the published post</h2>
      <p className="mt-0.5 text-[13px] text-ink-3">
        The file you supplied is compared with the platform record. This is not a Content ID or Rights Manager result, and it does
        not name a song.
      </p>
      <dl className="mt-4 grid gap-3 sm:grid-cols-2">
        {lines.map((line) => (
          <div key={line.label}>
            <dt className={cn("text-[12px] font-semibold", tone[line.status] ?? "text-ink-3")}>{line.label}</dt>
            <dd className="mt-0.5 text-[13px] text-ink-2">{line.detail}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-5 border-t border-line pt-4">
        <OwnerFileForm analysisId={analysisId} onStarted={onReload} replace />
      </div>
    </Card>
  );
}

function DetailsPanel({ analysis }: { analysis: Analysis }) {
  const { platformLabel, marketLabel } = useWorkspace();
  const mi = analysis.media_info;
  const rows: [string, ReactNode][] = [
    ["Platform", platformLabel(analysis.platform)],
    ["Markets", analysis.markets?.length ? analysis.markets.map(marketLabel).join(", ") : "—"],
    ["Source", `${SOURCE_LABEL[analysis.source]} · ${MODE_LABEL[analysis.analysis_mode]}`],
    ["Language", LANGUAGE_LABEL[analysis.language]],
    ["Duration", analysis.duration_seconds != null ? fmtLength(analysis.duration_seconds) : "—"],
    ["Resolution", mi ? `${mi.width}×${mi.height}${mi.original ? ` (original ${mi.original.width}×${mi.original.height})` : ""}` : "—"],
    ["Video codec", mi ? `${mi.video_codec}${mi.fps ? ` · ${Math.round(mi.fps)} fps` : ""}` : "—"],
    ["Audio", mi ? (mi.has_audio ? (mi.audio_codec ?? "Yes") : "No audio track") : "—"],
    ["File size", analysis.size_bytes > 0 ? fmtBytes(analysis.size_bytes) : "—"],
    ["AI", `${analysis.ai_provider ?? "—"} / ${analysis.ai_model ?? "—"} · ${analysis.ai_status ?? "—"}`],
    ["Policy library", analysis.policy_kb_version ?? "—"],
    ["Created", fmtDate(analysis.created_at)],
    ["Kept until", analysis.media_deleted ? "Media deleted; report kept" : fmtDate(analysis.expires_at)],
  ];
  return (
    <>
      <Card>
        <dl className="grid divide-y divide-line sm:grid-cols-2 sm:divide-y-0">
          {rows.map(([k, v]) => (
            <div key={k} className="flex justify-between gap-4 border-line px-4 py-2.5 text-[13px] sm:border-b">
              <dt className="text-ink-3">{k}</dt>
              <dd className="tabular text-right text-ink">{v}</dd>
            </div>
          ))}
        </dl>
      </Card>
      {mi?.original_sha256 && (
        <p className="text-[12px] text-ink-3">
          Original file SHA-256: <span className="font-mono break-all text-ink-2">{mi.original_sha256}</span>
        </p>
      )}
      <Card className="p-4">
        <h3 className="text-[15px] font-semibold">Limitations and notes ({analysis.limitations.length})</h3>
        {analysis.limitations.length === 0 ? (
          <p className="mt-1 text-[13px] text-ink-3">None recorded.</p>
        ) : (
          <ul className="mt-2 list-disc space-y-1.5 pl-5 text-[13px] text-ink-2">
            {analysis.limitations.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}

const RELATIONSHIP_LABEL: Record<SponsorshipRelationship, string> = {
  unknown: "Not declared",
  none: "No commercial relationship",
  paid: "Paid sponsorship",
  gifted: "Gift or free product",
  affiliate: "Affiliate commission",
  employment: "Employment or family connection",
  other: "Other benefit or mixed arrangements",
};

function DeclaredSponsorship({ sponsorship }: { sponsorship: Analysis["sponsorship"] }) {
  if (!sponsorship) {
    return <p className="mt-1.5 text-[13px] text-ink-3">No sponsorship declaration was recorded for this review.</p>;
  }
  const sponsors = sponsorship.sponsors ?? [];
  return (
    <p className="mt-1.5 inline-flex flex-wrap items-center gap-x-1.5 rounded-[6px] bg-surface-2 px-2 py-1 text-[13px] text-ink-2">
      <span className="font-semibold text-ink">Declared:</span>
      {RELATIONSHIP_LABEL[sponsorship.relationship] ?? sponsorship.relationship}
      {sponsors.length > 0 && <span>· sponsors: {sponsors.join(", ")}</span>}
      <span className="text-ink-3">(your declaration, not verified)</span>
    </p>
  );
}
