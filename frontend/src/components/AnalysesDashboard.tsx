"use client";

import Link from "next/link";
import {
  ArrowRight,
  BriefcaseBusiness,
  Check,
  ChartColumnStacked,
  CircleCheck,
  Gauge,
  ListChecks,
  OctagonExclamationPoint,
  Plus,
  ScanText,
} from "lucide-react";
import { useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { api, errorMessage, type AnalysisSummary, type Insights, type InsightSummary } from "@/lib/api";
import { cn } from "@/lib/cn";
import { fmtDate, reviewTitle } from "@/lib/format";
import { NEW_REVIEW_HREF } from "@/lib/nav";
import { usePolledResource } from "@/lib/usePolledResource";
import { useWorkspace } from "@/lib/workspace";
import { AiLimitCallout } from "./AiLimitCallout";
import { BarList } from "./charts/BarList";
import { VerdictColumns } from "./charts/VerdictColumns";
import { isInFlight, ReviewStatusBadge } from "./review/ReviewStatus";
import { MarketChips } from "./ReviewsPage";
import { PageContainer } from "./shell/AppShell";
import {
  ButtonLink,
  Card,
  EmptyState,
  ErrorNotice,
  PageHeader,
  Section,
  SegmentedControl,
  Skeleton,
  StatTile,
  VerdictBadge,
} from "./ui";

const anyInFlight = (rows: AnalysisSummary[]) => rows.some(isInFlight);
type Range = "7" | "30" | "90";

const noop = () => () => {};
/** Time-of-day greeting; the server renders the neutral form. */
function useGreeting(name: string) {
  const part = useSyncExternalStore(
    noop,
    () => {
      const h = new Date().getHours();
      return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
    },
    () => "Welcome back",
  );
  return name ? `${part}, ${name}` : part;
}

function pct(v: number | null | undefined) {
  return v == null ? "—" : `${Math.round(v * 100)}%`;
}

/** Signed delta vs the previous window; `higherIsGood` decides the colour. */
function delta(
  cur: number | null | undefined,
  prev: number | null | undefined,
  higherIsGood: boolean,
  format: (d: number) => string,
  days: number,
) {
  if (cur == null || prev == null) return undefined;
  const d = cur - prev;
  const label = `compared with the previous ${days} days`;
  if (Math.abs(d) < 1e-9) return { value: "No change", sentiment: "neutral" as const, label };
  return {
    value: `${d > 0 ? "+" : "−"}${format(Math.abs(d))}`,
    sentiment: (d > 0) === higherIsGood ? ("good" as const) : ("bad" as const),
    label,
  };
}

export function AnalysesDashboard() {
  const { settings, agency } = useWorkspace();
  const greeting = useGreeting(settings?.display_name?.trim() ?? "");
  const [range, setRange] = useState<Range>("30");
  const [insights, setInsights] = useState<Insights | null>(null);
  const [insightsError, setInsightsError] = useState<string | null>(null);
  const [loadingInsights, setLoadingInsights] = useState(true);
  const [briefCount, setBriefCount] = useState<number | null>(null);
  const reviews = usePolledResource(api.list, { intervalMs: 2500, shouldPoll: anyInFlight });

  useEffect(() => {
    const controller = new AbortController();
    api
      .insights(Number(range), controller.signal)
      .then((d) => {
        setInsights(d);
        setInsightsError(null);
      })
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setInsightsError(errorMessage(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingInsights(false);
      });
    return () => controller.abort();
  }, [range]);

  useEffect(() => {
    api
      .briefs()
      .then((b) => setBriefCount(b.length))
      .catch(() => setBriefCount(null));
  }, []);

  const rows = reviews.data;
  const firstRun = rows !== null && rows.length === 0;
  const t = insights?.totals;
  const p = insights?.previous;
  const days = Number(range);

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        title={greeting}
        description={agency ? "How your clients’ videos are doing before they go live." : "How your videos are doing before they go live."}
        actions={
          !firstRun && (
            <SegmentedControl
              label="Time range"
              size="sm"
              value={range}
              onChange={(v) => {
                setLoadingInsights(true);
                setRange(v);
              }}
              options={[
                { value: "7", label: "7 days" },
                { value: "30", label: "30 days" },
                { value: "90", label: "90 days" },
              ]}
            />
          )
        }
      />
      <AiLimitCallout />
      {reviews.error && !rows && <ErrorNotice title="Could not load reviews" message={reviews.error.message} onRetry={reviews.reload} />}

      {firstRun ? (
        <FirstRun onboarded={settings?.onboarded ?? false} briefCount={briefCount} />
      ) : (
        <>
          {insightsError && <ErrorNotice title="Could not load insights" message={insightsError} />}
          <div className={cn("space-y-6 transition-opacity duration-[180ms]", loadingInsights && insights && "opacity-60")}>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {t && p ? (
                <>
                  <StatTile
                    label="Reviews"
                    value={t.reviews.toLocaleString()}
                    icon={<ChartColumnStacked />}
                    hint={`vs previous ${days} days`}
                    delta={delta(t.reviews, p.reviews, true, (d) => String(d), days)}
                  />
                  <StatTile
                    label="No issues found"
                    value={pct(t.ready_rate)}
                    icon={<CircleCheck />}
                    hint="share of reviews"
                    delta={delta(t.ready_rate, p.ready_rate, true, (d) => `${Math.round(d * 100)} pts`, days)}
                  />
                  <StatTile
                    label="Fix first"
                    value={t.fix_first.toLocaleString()}
                    icon={<OctagonExclamationPoint />}
                    hint="reviews to fix before posting"
                    delta={delta(t.fix_first, p.fix_first, false, (d) => String(d), days)}
                  />
                  <StatTile
                    label="Average risk indicator"
                    value={t.avg_risk_score == null ? "—" : `${Math.round(t.avg_risk_score)}`}
                    icon={<Gauge />}
                    hint="0–100, not a probability"
                    delta={delta(t.avg_risk_score, p.avg_risk_score, false, (d) => d.toFixed(1), days)}
                  />
                </>
              ) : (
                [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[108px] rounded-[10px]" />)
              )}
            </div>
            {insights && (
              <p className="-mt-3 text-[12px] text-ink-3">
                Insights keep each review’s outcome only, never its content, for {insights.stats_retention_days} days, so these
                numbers outlast the videos themselves.
              </p>
            )}

            <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
              <Section title="Reviews per day" description="Each column is one day, split by the verdict the review reached.">
                {insights ? (
                  t && t.reviews > 0 ? (
                    <VerdictColumns days={insights.by_day} label={`Reviews per day over the last ${days} days, by verdict`} />
                  ) : (
                    <EmptyNote>No completed reviews in the last {days} days.</EmptyNote>
                  )
                ) : (
                  <Skeleton className="h-56 w-full" />
                )}
              </Section>
              <Section title="Where issues come from" description="Open findings by area, across completed reviews.">
                {insights ? (
                  insights.by_group.some((g) => g.findings > 0) ? (
                    <BarList
                      label="Open findings by area"
                      unit="findings"
                      items={insights.by_group.map((g) => ({
                        key: g.group,
                        label: g.label,
                        value: g.findings,
                        note: `in ${g.reviews} review${g.reviews === 1 ? "" : "s"}`,
                      }))}
                    />
                  ) : (
                    <EmptyNote>No open findings in this period.</EmptyNote>
                  )
                ) : (
                  <Skeleton className="h-40 w-full" />
                )}
              </Section>
            </div>

            {insights && t && t.reviews > 0 && (
              <div className={cn("grid grid-cols-1 items-start gap-6", agency && insights.by_client.length ? "lg:grid-cols-3" : "lg:grid-cols-2")}>
                <Section title="By platform">
                  <BarList
                    label="Reviews by platform"
                    unit="reviews"
                    items={insights.by_platform.map((x) => ({ key: x.platform, label: x.label, value: x.reviews, note: readyNote(x) }))}
                  />
                </Section>
                <Section title="By market" description="A review can target several markets.">
                  <BarList label="Reviews by audience market" unit="reviews" items={insights.by_market.map((x) => ({ key: x.market, label: x.label, value: x.reviews }))} />
                </Section>
                {agency && insights.by_client.length > 0 && (
                  <Section title="By client">
                    <BarList
                      label="Reviews by client"
                      unit="reviews"
                      items={insights.by_client.map((x) => ({ key: x.client_label, label: x.client_label, value: x.reviews, note: readyNote(x) }))}
                    />
                  </Section>
                )}
              </div>
            )}
          </div>
        </>
      )}

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        {!firstRun && (
          <Section
            title="Recent reviews"
            actions={
              <ButtonLink href="/reviews" size="sm" variant="ghost" trailingIcon={<ArrowRight />}>
                All reviews
              </ButtonLink>
            }
            bodyClassName="p-0"
          >
            {!rows ? (
              <div className="space-y-3 p-5">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : (
              <ul className="divide-y divide-line">
                {rows.slice(0, 5).map((r) => (
                  <li key={r.id}>
                    <Link href={`/analyses/${r.id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-surface-2 focus-visible:outline-offset-[-2px]">
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium text-ink">{reviewTitle(r)}</div>
                        <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[12px] text-ink-3">
                          {fmtDate(r.created_at)}
                          {agency && r.client_label && <span>· {r.client_label}</span>}
                          <MarketChips markets={r.markets} />
                        </div>
                      </div>
                      {r.status === "completed" ? <VerdictBadge verdict={r.readiness_verdict} /> : <ReviewStatusBadge a={r} />}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        )}
        <Section title="Quick actions" className={firstRun ? "lg:col-span-2" : undefined}>
          <div className={cn("grid gap-2", firstRun && "sm:grid-cols-3")}>
            <QuickAction href={NEW_REVIEW_HREF} icon={<Plus />} title="Start a review" text="Upload a video or pick a post from your account." primary />
            <QuickAction href="/check" icon={<ScanText />} title="Check a caption" text="Instant disclosure and wording check, nothing stored." />
            <QuickAction href="/briefs?new=1" icon={<BriefcaseBusiness />} title="Add a brand brief" text="What a sponsor asked for, checked on every review." />
          </div>
        </Section>
      </div>
    </PageContainer>
  );
}

function readyNote(x: InsightSummary) {
  return x.ready_rate == null ? undefined : `${Math.round(x.ready_rate * 100)}% no issues`;
}

function EmptyNote({ children }: { children: ReactNode }) {
  return <p className="rounded-[8px] border border-dashed border-line-strong px-4 py-8 text-center text-[13px] text-ink-3">{children}</p>;
}

function QuickAction({ href, icon, title, text, primary }: { href: string; icon: ReactNode; title: string; text: string; primary?: boolean }) {
  return (
    <Link
      href={href}
      className={cn(
        "group flex items-start gap-3 rounded-[8px] border p-3 transition-colors duration-[120ms]",
        primary ? "border-accent bg-accent-soft hover:bg-accent-soft/70" : "border-line hover:bg-surface-2",
      )}
    >
      <span className={cn("mt-0.5 [&_svg]:size-5", primary ? "text-accent" : "text-ink-3")} aria-hidden>
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold text-ink">{title}</span>
        <span className="block text-[13px] text-ink-2">{text}</span>
      </span>
      <ArrowRight className="mt-1 size-4 text-ink-3 transition-transform duration-[120ms] group-hover:translate-x-0.5" aria-hidden />
    </Link>
  );
}

function FirstRun({ onboarded, briefCount }: { onboarded: boolean; briefCount: number | null }) {
  const steps = [
    { done: onboarded, title: "Set up your workspace", text: "Your audience markets and default platform.", href: "/settings", cta: "Open settings" },
    { done: (briefCount ?? 0) > 0, title: "Add a brand brief", text: "Optional. What a sponsor asked you to say, tag and avoid.", href: "/briefs?new=1", cta: "Add a brief" },
    { done: false, title: "Check a caption", text: "See the disclosure check in seconds, without uploading.", href: "/check", cta: "Check a caption" },
    { done: false, title: "Start your first review", text: "Upload a video to get a verdict and timestamped findings.", href: NEW_REVIEW_HREF, cta: "Start a review" },
  ];
  return (
    <Card>
      <EmptyState
        icon={<ListChecks />}
        title="Your first review is a few minutes away"
        description="Insights and trends appear here once you have completed reviews. Until then, these steps get you set up."
        className="pb-6"
      />
      <ol className="divide-y divide-line border-t border-line">
        {steps.map((s, i) => (
          <li key={s.title} className="flex flex-wrap items-center gap-4 px-5 py-4">
            <span
              className={cn(
                "flex size-7 shrink-0 items-center justify-center rounded-full border text-[12px] font-semibold",
                s.done ? "border-success-line bg-success-bg text-success-fg" : "border-line-strong text-ink-2",
              )}
              aria-hidden
            >
              {s.done ? <Check className="size-4" /> : i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <div className={cn("text-sm font-semibold", s.done ? "text-ink-3 line-through" : "text-ink")}>
                {s.title}
                {s.done && <span className="sr-only"> (done)</span>}
              </div>
              <div className="text-[13px] text-ink-3">{s.text}</div>
            </div>
            {!s.done && (
              <ButtonLink href={s.href} size="sm" variant={i === 3 ? "primary" : "secondary"}>
                {s.cta}
              </ButtonLink>
            )}
          </li>
        ))}
      </ol>
    </Card>
  );
}
