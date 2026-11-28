"use client";

import { Plus, Search, Upload } from "lucide-react";
import { useMemo, useState } from "react";
import { api, type AnalysisSummary, type ReadinessVerdict } from "@/lib/api";
import { fmtDate, fmtLength, LANGUAGE_LABEL, reviewTitle, SOURCE_LABEL } from "@/lib/format";
import { NEW_REVIEW_HREF } from "@/lib/nav";
import { usePolledResource } from "@/lib/usePolledResource";
import { useWorkspace } from "@/lib/workspace";
import { isInFlight, ReviewStatusBadge } from "./review/ReviewStatus";
import { PageContainer } from "./shell/AppShell";
import {
  Badge,
  Button,
  ButtonLink,
  Card,
  DataTable,
  EmptyState,
  ErrorNotice,
  Input,
  PageHeader,
  Select,
  VERDICT,
  VerdictBadge,
  type Column,
} from "./ui";

// Poll while anything is in flight.
const anyInFlight = (rows: AnalysisSummary[]) => rows.some(isInFlight);

type StatusFilter = "all" | "in_progress" | "completed" | "failed" | "awaiting_file";
const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All statuses" },
  { value: "completed", label: "Completed" },
  { value: "in_progress", label: "In progress" },
  { value: "awaiting_file", label: "Needs your file" },
  { value: "failed", label: "Failed" },
];

function matchesStatus(r: AnalysisSummary, f: StatusFilter) {
  if (f === "all") return true;
  if (f === "in_progress") return isInFlight(r);
  return r.status === f;
}

const VERDICT_ORDER: Record<ReadinessVerdict, number> = { fix_first: 3, review: 2, ready: 1 };

export function MarketChips({ markets }: { markets: string[] | undefined }) {
  const { marketLabel } = useWorkspace();
  if (!markets?.length) return <span className="text-ink-3">—</span>;
  return (
    <span className="inline-flex flex-wrap gap-1">
      {markets.map((m) => (
        <Badge key={m} title={marketLabel(m)} className="h-5 px-1.5 font-mono text-[11px]">
          {m}
        </Badge>
      ))}
    </span>
  );
}

/** The full list of reviews: search, filters, sortable columns, stacked cards on mobile. */
export function ReviewsPage() {
  const { agency, platforms, markets, platformLabel } = useWorkspace();
  const { data: rows, error, autoRetry, stopped, reload, dismissError } = usePolledResource(api.list, {
    intervalMs: 2500,
    shouldPoll: anyInFlight,
  });
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [platform, setPlatform] = useState("all");
  const [verdict, setVerdict] = useState<ReadinessVerdict | "all">("all");
  const [market, setMarket] = useState("all");
  const [client, setClient] = useState("all");

  const clients = useMemo(
    () => [...new Set((rows ?? []).map((r) => r.client_label).filter((c): c is string => !!c))].sort((a, b) => a.localeCompare(b)),
    [rows],
  );

  const filtered = useMemo(() => {
    if (!rows) return null;
    const q = query.trim().toLowerCase();
    return rows.filter(
      (r) =>
        matchesStatus(r, status) &&
        (platform === "all" || r.platform === platform) &&
        (verdict === "all" || r.readiness_verdict === verdict) &&
        (market === "all" || r.markets?.includes(market)) &&
        (!agency || client === "all" || r.client_label === client) &&
        (!q || `${reviewTitle(r)} ${r.caption} ${agency ? (r.client_label ?? "") : ""}`.toLowerCase().includes(q)),
    );
  }, [rows, query, status, platform, verdict, market, client, agency]);
  const filtering = query.trim() !== "" || status !== "all" || platform !== "all" || verdict !== "all" || market !== "all" || client !== "all";

  function clear() {
    setQuery("");
    setStatus("all");
    setPlatform("all");
    setVerdict("all");
    setMarket("all");
    setClient("all");
  }

  const columns: Column<AnalysisSummary>[] = [
    {
      key: "video",
      header: "Video",
      primary: true,
      sortValue: (r) => reviewTitle(r).toLowerCase(),
      cell: (r) => (
        <div className="min-w-0 max-w-[380px]">
          <div className="truncate font-medium text-ink">{reviewTitle(r)}</div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-[12px] text-ink-3">
            {agency && r.client_label && (
              <>
                <span className="font-medium text-ink-2">{r.client_label}</span>
                <span aria-hidden>·</span>
              </>
            )}
            {r.source !== "upload" && (
              <>
                <span>
                  {SOURCE_LABEL[r.source]}
                  {r.analysis_mode === "cross_checked" ? ", cross-checked" : r.analysis_mode !== "full_video" ? ", limited" : ""}
                </span>
                <span aria-hidden>·</span>
              </>
            )}
            {r.duration_seconds != null && (
              <>
                <span className="tabular">{fmtLength(r.duration_seconds)}</span>
                <span aria-hidden>·</span>
              </>
            )}
            <span>{LANGUAGE_LABEL[r.language] ?? r.language}</span>
            {r.mock_mode && (
              <Badge tone="medium" className="ml-1 h-[18px] px-1 text-[11px]">
                MOCK
              </Badge>
            )}
          </div>
        </div>
      ),
    },
    { key: "platform", header: "Platform", cell: (r) => <span className="whitespace-nowrap text-ink-2">{platformLabel(r.platform)}</span>, sortValue: (r) => r.platform },
    { key: "markets", header: "Markets", cell: (r) => <MarketChips markets={r.markets} /> },
    {
      key: "verdict",
      header: "Verdict",
      cell: (r) => (r.status === "completed" ? <VerdictBadge verdict={r.readiness_verdict} /> : <ReviewStatusBadge a={r} />),
      sortValue: (r) => (r.readiness_verdict ? VERDICT_ORDER[r.readiness_verdict] : 0),
    },
    {
      key: "findings",
      header: "Findings",
      align: "right",
      cell: (r) => <span className="tabular text-ink-2">{r.status === "completed" ? r.finding_count : "—"}</span>,
      sortValue: (r) => (r.status === "completed" ? r.finding_count : -1),
    },
    {
      key: "created",
      header: "Created",
      align: "right",
      cell: (r) => <span className="tabular whitespace-nowrap text-[13px] text-ink-3">{fmtDate(r.created_at)}</span>,
      sortValue: (r) => r.created_at,
    },
  ];

  const empty = filtering ? (
    <EmptyState
      icon={<Search />}
      title="No reviews match these filters"
      description="Try a different search or clear the filters."
      action={<Button onClick={clear}>Clear filters</Button>}
    />
  ) : (
    <EmptyState
      icon={<Upload />}
      title="No reviews yet"
      description="Upload a video, up to 30 minutes, to get a verdict and a timestamped report with official policy references."
      action={
        <ButtonLink href={NEW_REVIEW_HREF} variant="primary" leadingIcon={<Plus />}>
          Start a review
        </ButtonLink>
      }
    />
  );

  return (
    <PageContainer className="space-y-6">
      <PageHeader title="Reviews" description={agency ? "Every review across your clients." : "Every video you have reviewed."} />
      {error && (
        <ErrorNotice
          title={rows ? "Could not refresh the list" : "Could not load reviews"}
          message={error.message}
          note={autoRetry ? "Retrying automatically…" : rows ? "Showing the last list that loaded." : undefined}
          onRetry={reload}
          onDismiss={rows ? dismissError : undefined}
        />
      )}
      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
          <div className="relative w-full lg:w-64">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
            <Input
              type="search"
              aria-label="Search reviews"
              placeholder={agency ? "Search title, caption or client" : "Search title or caption"}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-8"
            />
          </div>
          <Select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value as StatusFilter)} className="w-[calc(50%-4px)] sm:w-40">
            {STATUS_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </Select>
          <Select aria-label="Filter by verdict" value={verdict} onChange={(e) => setVerdict(e.target.value as ReadinessVerdict | "all")} className="w-[calc(50%-4px)] sm:w-40">
            <option value="all">All verdicts</option>
            {(Object.keys(VERDICT) as ReadinessVerdict[]).map((v) => (
              <option key={v} value={v}>
                {VERDICT[v].label}
              </option>
            ))}
          </Select>
          <Select aria-label="Filter by platform" value={platform} onChange={(e) => setPlatform(e.target.value)} className="w-[calc(50%-4px)] sm:w-40">
            <option value="all">All platforms</option>
            {platforms.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </Select>
          <Select aria-label="Filter by market" value={market} onChange={(e) => setMarket(e.target.value)} className="w-[calc(50%-4px)] sm:w-40">
            <option value="all">All markets</option>
            {markets.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </Select>
          {agency && (
            <Select aria-label="Filter by client" value={client} onChange={(e) => setClient(e.target.value)} className="w-full sm:w-44">
              <option value="all">All clients</option>
              {clients.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          )}
          {filtering && (
            <Button variant="ghost" size="sm" onClick={clear}>
              Clear
            </Button>
          )}
        </div>
        {stopped === "auth" && !rows ? (
          <p className="p-6 text-sm text-ink-2">Sign in to see your reviews.</p>
        ) : (
          <DataTable
            caption="Reviews"
            columns={columns}
            rows={filtered}
            loading={!rows && !error}
            rowKey={(r) => r.id}
            rowHref={(r) => `/analyses/${r.id}`}
            empty={empty}
            card={(r) => (
              <div className="space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 font-medium text-ink">
                    <div className="truncate">{reviewTitle(r)}</div>
                    <div className="mt-0.5 text-[12px] font-normal text-ink-3">
                      {platformLabel(r.platform)} · {fmtDate(r.created_at)}
                      {agency && r.client_label ? ` · ${r.client_label}` : ""}
                    </div>
                  </div>
                  {r.status === "completed" && <span className="tabular shrink-0 text-[12px] text-ink-3">{r.finding_count} findings</span>}
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  {r.status === "completed" ? <VerdictBadge verdict={r.readiness_verdict} /> : <ReviewStatusBadge a={r} />}
                  <MarketChips markets={r.markets} />
                  {r.mock_mode && <Badge tone="medium">MOCK</Badge>}
                </div>
              </div>
            )}
          />
        )}
      </Card>
    </PageContainer>
  );
}
