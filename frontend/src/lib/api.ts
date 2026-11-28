export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** A platform ID from /api/config `platforms` (never hard-code the list). */
export type Platform = string;
/** An audience-market ID from /api/config `markets`, e.g. "IN". */
export type MarketId = string;
export type ReadinessVerdict = "ready" | "review" | "fix_first";
export type Language = "en" | "hi";
export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type FindingType =
  | "observed_evidence"
  | "suspected_violation"
  | "licensing_uncertainty"
  | "cannot_check";
export type Confidence = "low" | "medium" | "high";
export type RiskLevel = "low" | "moderate" | "elevated" | "high";
export type Source = "upload" | "instagram" | "youtube";
export type AnalysisMode = "full_video" | "caption_thumbnail" | "metadata_only" | "cross_checked";
export type ConnectedPlatform = "instagram" | "youtube";

/** Declared commercial relationship (backend/app/schemas.py SponsorshipInput). */
export type SponsorshipRelationship = "unknown" | "none" | "paid" | "gifted" | "affiliate" | "employment" | "other";
export interface Sponsorship {
  relationship: SponsorshipRelationship;
  sponsors: string[];
}
/** Limits enforced by SponsorshipInput: at most 10 names, each 1–100 characters. */
export const SPONSOR_LIMITS = { maxSponsors: 10, maxNameLength: 100 } as const;

export interface PolicyRef {
  id: string;
  platform: string;
  title: string;
  official_title: string;
  official_url: string;
  verified_on: string;
}

export interface Evidence {
  source: string;
  ref_id: string;
  detail: string;
  timestamp: number | null;
  url?: string;
}

export interface Finding {
  id: string;
  source: "ai" | "deterministic" | "combined" | "provenance";
  category: string;
  category_label: string;
  finding_type: FindingType;
  severity: Severity;
  confidence: Confidence;
  title: string;
  explanation: string;
  suggested_action: string;
  start_seconds: number | null;
  end_seconds: number | null;
  evidence: Evidence[];
  policy_rule_ids: string[];
  policies: PolicyRef[];
  context_exception: string | null;
  requires_human_review: boolean;
  validation_notes: string[];
  /** covered = the rights ledger covers it; duplicate = a provenance finding reports it. Not counted in risk. */
  rights_status: "covered" | "duplicate" | null;
  rights_note: string | null;
  /** Set by the API. Disclosure stays separate from community-guideline flags. */
  report_section?: "community" | "disclosure" | "other" | "brief";
}

export interface TranscriptSegment {
  id: string;
  start: number;
  end: number;
  text: string;
}

export interface Extraction {
  transcript: {
    provider: string;
    model: string | null;
    language: string | null;
    language_probability: number | null;
    segments: TranscriptSegment[];
  };
  audio: {
    sound_intervals: [number, number][];
    non_speech_sound_intervals: [number, number][];
    non_speech_seconds: number;
  } | null;
  frames: { id: string; timestamp: number; reason: string; file: string }[];
  ocr: { id: string; frame_id: string; timestamp: number; text: string; mean_confidence: number }[];
  warnings: string[];
  cross_check?: {
    duration_status: string;
    caption_track_status: string;
    thumbnail_text_status: string;
    platform_withheld_media: boolean;
    file_matches_post?: "yes" | "partial" | "no" | "unknown";
    lines: { label: string; status: "ok" | "warn" | "bad" | "muted"; detail: string }[];
  } | null;
}

export interface AnalysisSummary {
  id: string;
  created_at: string;
  expires_at: string;
  status: "queued" | "processing" | "completed" | "failed" | "awaiting_file";
  stage: string;
  progress: number;
  platform: Platform;
  language: Language;
  caption: string;
  duration_seconds: number | null;
  risk_level: RiskLevel | null;
  risk_score: number | null;
  mock_mode: boolean;
  finding_count: number;
  source: Source;
  analysis_mode: AnalysisMode;
  source_title: string | null;
  client_label: string | null;
  markets: MarketId[];
  /** Present on completed reviews. */
  readiness_verdict: ReadinessVerdict | null;
}

export interface Analysis extends AnalysisSummary {
  updated_at: string;
  source_url: string | null;
  source_media_id: string | null;
  connection_id: string | null;
  error_message: string | null;
  hashtags: string[];
  file_ext: string;
  content_type: string;
  size_bytes: number;
  media_deleted: boolean;
  media_info: {
    duration_seconds: number;
    width: number;
    height: number;
    fps: number | null;
    video_codec: string;
    has_audio: boolean;
    audio_codec: string | null;
    // Set when a large upload was analysed from a smaller working copy.
    working_copy?: boolean;
    original_sha256?: string;
    original?: { width: number; height: number; video_codec: string; fps: number | null; bit_rate: number | null };
  } | null;
  extraction: Extraction | null;
  ai_provider: string | null;
  ai_model: string | null;
  ai_status: "completed" | "mock" | "skipped" | "failed" | null;
  ai_status_detail: string | null;
  policy_kb_version: string | null;
  summary: string | null;
  context_assessment: string | null;
  limitations: string[];
  findings: Finding[];
  owner_supplied_media: boolean;
  provenance: Provenance | null;
  /** Declared at upload/import; null for analyses created before declarations existed. */
  sponsorship?: Sponsorship | null;
  brief: BriefInput | null;
  brief_check: BriefCheck | null;
  readiness: Readiness | null;
  caption_fix: CaptionFix | null;
  market_disclosure: MarketDisclosure | null;
}

// ---------------------------------------------------------------------------- creator features

export interface ChecklistItem {
  key: "disclosure" | "community" | "claims" | "rights" | "brief" | "coverage" | "ai_review" | string;
  label: string;
  status: "pass" | "warn" | "fail" | "unknown";
  detail: string;
  finding_ids: string[];
}

export interface Readiness {
  verdict: ReadinessVerdict;
  headline: string;
  blockers: number;
  warnings: number;
  checklist: ChecklistItem[];
}

export type DisclosureStatus = "clear" | "buried" | "unclear" | "none";

export interface CaptionFix {
  needed: boolean;
  suggested_caption: string;
  suggested_hashtags: string[];
  label: string | null;
  changes: string[];
  note: string;
  /** Status of the ORIGINAL caption per market. */
  markets: Record<MarketId, DisclosureStatus>;
}

export interface MarketDisclosure {
  labels: {
    text: string;
    kind: string;
    kind_label: string;
    opening: boolean;
    denied: boolean;
    clear_in: MarketId[];
    unclear_in: MarketId[];
  }[];
  by_market: Record<MarketId, { status: DisclosureStatus; regulator: string; clear_labels: string[]; unclear_labels: string[] }>;
}

export interface BriefInput {
  name: string;
  brand: string;
  must_say: string[];
  must_not_say: string[];
  required_hashtags: string[];
  required_mentions: string[];
  competitors: string[];
  required_disclosure: string | null;
  notes: string;
}

export interface Brief extends BriefInput {
  id: string;
  created_at: string;
  updated_at: string;
}

export type BriefItemKind = "must_say" | "must_not_say" | "required_hashtag" | "required_mention" | "competitor" | "required_disclosure";

export interface BriefCheck {
  brand: string;
  name: string;
  scope: "video" | "caption_only";
  items: {
    kind: BriefItemKind;
    text: string;
    status: "met" | "missing" | "violated" | "unverified";
    where: { source: string; ref_id: string; timestamp: number | null }[];
  }[];
  met: number;
  total: number;
  failed: number;
  unverified: number;
}

export interface QuickCheckRequest {
  platform: Platform;
  markets: MarketId[];
  caption: string;
  hashtags: string[];
  sponsorship?: Sponsorship;
  brief_id?: string;
  brief?: BriefInput;
}

export interface QuickCheckResponse {
  platform: Platform;
  markets: MarketId[];
  findings: Finding[];
  readiness: Readiness;
  risk_score: number;
  risk_level: RiskLevel;
  caption_fix: CaptionFix;
  market_disclosure: MarketDisclosure;
  brief_check: BriefCheck | null;
  not_checked: string[];
  policy_kb_version: string;
}

export type WorkspaceMode = "creator" | "agency";

export interface WorkspaceSettings {
  mode: WorkspaceMode;
  display_name: string;
  default_platform: Platform;
  default_markets: MarketId[];
  default_language: Language;
  onboarded: boolean;
}

export interface InsightSummary {
  reviews: number;
  ready: number;
  review: number;
  fix_first: number;
  ready_rate: number | null;
  avg_risk_score: number | null;
  open_findings: number;
}

export interface Insights {
  window_days: number;
  generated_at: string;
  stats_retention_days: number;
  totals: InsightSummary;
  previous: InsightSummary;
  by_day: (InsightSummary & { date: string })[];
  by_group: { group: string; label: string; findings: number; reviews: number }[];
  by_severity: Record<Severity, number>;
  by_platform: (InsightSummary & { platform: Platform; label: string })[];
  by_market: { market: MarketId; label: string; reviews: number }[];
  by_client: (InsightSummary & { client_label: string })[];
}

export interface Health {
  status: "ok" | "degraded";
  checks: Record<string, string | { version: string; rules: number }>;
}

export type RightsArea = "handle" | "broadcaster" | "brand" | "catalogue" | "music" | "web" | "youtube";
export type RightsStatus =
  | "own"
  | "covered"
  | "expired"
  | "not_started"
  | "missing"
  | "info"
  | "review";

export interface RightsLine {
  area: RightsArea;
  subject: string;
  status: RightsStatus;
  detail: string;
  records: {
    record_id: string;
    kind: string;
    kind_label: string;
    counterparty: string;
    reference: string;
    valid_from: string | null;
    valid_until: string | null;
    status: string;
    has_proof: boolean;
  }[];
  start_seconds: number | null;
  end_seconds: number | null;
  match?: { kind: string; analysis_id: string | null; fingerprint_id: string; source: string };
}

export interface CatalogueMatch {
  kind: "identical_file" | "same_clip" | "same_footage" | "mirrored_footage" | "same_audio";
  query_start: number;
  query_end: number;
  ref_start: number;
  ref_end: number;
  video_coverage: number;
  audio_coverage: number;
  owner_label: string;
  same_owner: boolean;
  unlabelled: boolean;
  source: "analysis" | "catalogue";
  title: string | null;
  analysis_id: string | null;
  fingerprint_id: string;
  indexed_at: string | null;
}

export interface LookupBlock {
  provider: string;
  status: string;
  detail: string | null;
  is_mock: boolean;
}

export interface MusicClip {
  start: number;
  end: number;
  matched: boolean;
  title?: string;
  artist?: string;
  label?: string | null;
  album?: string | null;
  song_link?: string | null;
  cached?: boolean;
  error?: string;
}

export interface WebFrame {
  frame_id: string;
  timestamp: number | null;
  pages: { url: string; title: string; domain: string; full_match: boolean }[];
  full_matches: string[];
  partial_matches: string[];
  best_guess: string[];
  cached?: boolean;
  error?: string;
}

export interface MusicBlock extends LookupBlock {
  clips?: MusicClip[];
}

export interface WebBlock extends LookupBlock {
  frames?: WebFrame[];
}

export interface YouTubeResult {
  video_id: string;
  url: string;
  title: string;
  channel_title: string;
  published_at: string | null;
  thumbnail_url: string | null;
  own_channel: boolean;
  visual_distance: number | null;
  visual_match: "strong" | "possible" | "none" | "unknown";
  matched_at: number | null;
}

export interface YouTubeBlock {
  status: string;
  detail?: string | null;
  query?: string;
  searched_at?: string;
  results?: YouTubeResult[];
  strong_matches?: number;
}

export interface Provenance {
  cues?: {
    handles: { handle: string; ref_id: string; timestamp: number | null; text: string }[];
    broadcasters: { name: string; ref_id: string; timestamp: number | null; text: string }[];
  };
  fingerprint?: { sha256: string; frames_hashed: number; audio_items: number };
  catalogue?: { entries_checked: number; owner_label?: string; matches: CatalogueMatch[]; skipped?: boolean };
  music?: MusicBlock;
  web?: WebBlock;
  youtube?: YouTubeBlock;
  rights?: RightsLine[];
  rights_checked_at?: string;
  warnings?: string[];
}

export type RightsKind = "own_channel" | "creator_permission" | "music_license" | "footage_license" | "brand_agreement";

export interface RightsRecord {
  id: string;
  created_at: string;
  kind: RightsKind;
  kind_label: string;
  counterparty: string;
  match_terms: string[];
  platforms: ConnectedPlatform[];
  client_label: string | null;
  valid_from: string | null;
  valid_until: string | null;
  reference: string;
  notes: string;
  has_proof: boolean;
  status: "active" | "expired" | "not_started";
}

export interface CatalogueEntry {
  id: string;
  created_at: string;
  expires_at: string;
  source: "analysis" | "catalogue";
  analysis_id: string | null;
  owner_label: string;
  platform: Platform | null;
  title: string | null;
  duration_seconds: number;
  frames_hashed: number;
  has_audio: boolean;
}

export interface CatalogueAddResult {
  duplicate: boolean;
  entry: CatalogueEntry;
  truncated?: boolean;
}

export interface YouTubeSuggest {
  query: string;
  units_per_search: number;
  units_used_today: number;
  daily_unit_cap: number;
}

export interface ProvenanceStatus {
  music_id: { provider: string; configured: boolean; auto: boolean; est_cost_per_call_usd: number };
  web_detection: { provider: string; configured: boolean; auto: boolean; est_cost_per_image_usd: number; max_frames: number };
  youtube_search: { available: boolean; units_per_search: number; units_used_today: number; daily_unit_cap: number };
  budget: {
    month_start: string;
    budget_usd: number;
    spent_usd: number;
    remaining_usd: number;
    by_service: Record<string, { calls: number; est_cost_usd: number }>;
  };
  catalogue: { entries: number; retention_days: number };
}

export interface PlatformInfo {
  id: Platform;
  label: string;
  short_label: string;
  family: string;
  description: string;
  short_form: boolean;
}

export interface MarketInfo {
  id: MarketId;
  label: string;
  regulator: string;
  summary: string;
  /** The policy-library platform that holds this market's rules (e.g. "us_advisory"). */
  kb_platform: string;
}

export interface Limits {
  caption_max: number;
  hashtags_max: number;
  sponsors_max: number;
  sponsor_name_max: number;
  brief_items_max: number;
  brief_item_max: number;
}

export interface PublicConfig {
  ai_provider: string;
  ai_model: string;
  ai_credentials_present: boolean;
  mock_mode: boolean;
  stt_provider: string;
  whisper_model: string | null;
  ocr_enabled: boolean;
  max_upload_mb: number;
  max_duration_seconds: number;
  retention_hours: number;
  delete_media_after_analysis: boolean;
  instagram_configured: boolean;
  youtube_configured: boolean;
  youtube_captions_scope: boolean;
  import_max_seconds: number;
  music_id_provider: "none" | "audd" | "mock";
  music_id_configured: boolean;
  web_detection_provider: "none" | "google" | "mock";
  web_detection_configured: boolean;
  youtube_search_available: boolean;
  paid_lookups_monthly_budget_usd: number;
  catalogue_max_seconds: number;
  platforms: PlatformInfo[];
  markets: MarketInfo[];
  default_markets: MarketId[];
  limits: Limits;
}

export interface Connection {
  id: string;
  platform: ConnectedPlatform;
  display_name: string;
  external_id: string;
  account_meta: Record<string, string | null>;
  scopes: string[];
  token_expires_at: string | null;
  created_at: string;
  captions_enabled: boolean;
}

export interface ConnectionsResponse {
  encryption_configured: boolean;
  instagram: { configured: boolean; redirect_uri: string; connections: Connection[] };
  youtube: { configured: boolean; redirect_uri: string; captions_scope: boolean; connections: Connection[] };
}

export interface MediaItem {
  id: string;
  title: string;
  caption: string;
  permalink: string | null;
  thumbnail_url: string | null;
  published_at: string | null;
  media_type: string;
  duration_seconds: number | null;
  privacy: string | null;
  expected_mode: AnalysisMode;
}

export interface PolicyRule {
  id: string;
  platform: string;
  category: string;
  title: string;
  official_title: string;
  official_url: string;
  verified_on: string;
  key_points: string[];
  quote: string | null;
}

export interface PolicyKB {
  version: string;
  verified_on: string;
  notes: string;
  rules: PolicyRule[];
}

/** A failed API call. `status` is 0 for network failures; `detail` is the raw FastAPI detail. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;
  /** From a Retry-After header (seconds), when the server sent one. */
  readonly retryAfterMs: number | null;
  constructor(message: string, status: number, detail?: unknown, retryAfterMs: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail ?? message;
    this.retryAfterMs = retryAfterMs;
  }
}

export function isAbortError(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

/** Network failures, timeouts, rate limits and server errors are worth retrying later. */
export function isRetryable(e: unknown): boolean {
  if (!(e instanceof ApiError)) return true;
  return e.status === 0 || e.status === 408 || e.status === 429 || e.status >= 500;
}

export function errorMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}

const LOCATION_PREFIXES = new Set(["body", "query", "path", "form", "header"]);

/** Turn a FastAPI `detail` (string, or a list of validation errors) into a readable sentence. */
export function formatApiDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (!item || typeof item !== "object") return null;
        const { loc, msg } = item as { loc?: unknown; msg?: unknown };
        const text = typeof msg === "string" ? msg.replace(/^Value error,\s*/i, "") : null;
        if (!text) return null;
        const field = Array.isArray(loc)
          ? loc
              .filter((p, i) => !(i === 0 && typeof p === "string" && LOCATION_PREFIXES.has(p)))
              .map((p) => (typeof p === "number" ? `#${p + 1}` : String(p).replace(/_/g, " ")))
              .join(" ")
          : "";
        return field ? `${field}: ${text}` : text;
      })
      .filter((p): p is string => Boolean(p));
    if (parts.length) return parts.join("; ");
  }
  return fallback;
}

// ---------------------------------------------------------------------------- sign-in state
// The pilot deployment protects the API with HTTP Basic auth. A 401 means the browser's
// stored login was rejected (for example after a password rotation); every 401 is reported
// here so the app can show one sign-in notice instead of a generic error on each page.

const authListeners = new Set<() => void>();
let authRequired = false;

function reportAuthRequired() {
  if (authRequired) return;
  authRequired = true;
  authListeners.forEach((listener) => listener());
}

export function subscribeAuthRequired(listener: () => void): () => void {
  authListeners.add(listener);
  return () => {
    authListeners.delete(listener);
  };
}

export function isAuthRequired(): boolean {
  return authRequired;
}

// ---------------------------------------------------------------------------- URLs

/**
 * Only http(s) URLs and same-origin paths may be rendered into href/src. Anything else
 * (javascript:, data:, protocol-relative //host) from the API or a third party is dropped.
 */
export function safeUrl(url: string | null | undefined): string | undefined {
  if (typeof url !== "string") return undefined;
  const value = url.trim();
  if (!value) return undefined;
  if (value.startsWith("/")) {
    return value.startsWith("//") || value.startsWith("/\\") ? undefined : value;
  }
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : undefined;
  } catch {
    return undefined;
  }
}

const YOUTUBE_ID = /^[A-Za-z0-9_-]{11}$/;
export function safeYouTubeId(id: string | null | undefined): string | null {
  return id && YOUTUBE_ID.test(id) ? id : null;
}

// ---------------------------------------------------------------------------- requests

function failure(status: number, statusText: string, body: unknown, retryAfter: string | null): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  const fallback = status === 401 ? "Sign in to continue." : statusText || `Request failed (${status})`;
  if (status === 401) reportAuthRequired();
  const seconds = retryAfter ? Number(retryAfter) : NaN;
  return new ApiError(
    formatApiDetail(detail, fallback),
    status,
    detail,
    Number.isFinite(seconds) && seconds > 0 ? Math.min(seconds, 600) * 1000 : null,
  );
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  } catch (e) {
    if (isAbortError(e)) throw e;
    throw new ApiError("Cannot reach the CreatorShield API. Check your connection and that the backend is running.", 0);
  }
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      /* non-JSON error body */
    }
    throw failure(res.status, res.statusText, body, res.headers.get("Retry-After"));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const enc = encodeURIComponent;

const json = (body: unknown, method = "POST"): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  settings: () => request<WorkspaceSettings>("/api/settings"),
  updateSettings: (patch: Partial<WorkspaceSettings>) => request<WorkspaceSettings>("/api/settings", json(patch, "PUT")),
  briefs: () => request<Brief[]>("/api/briefs"),
  createBrief: (b: BriefInput) => request<Brief>("/api/briefs", json(b)),
  updateBrief: (id: string, b: BriefInput) => request<Brief>(`/api/briefs/${enc(id)}`, json(b, "PUT")),
  deleteBrief: (id: string) => request<void>(`/api/briefs/${enc(id)}`, { method: "DELETE" }),
  quickCheck: (body: QuickCheckRequest, signal?: AbortSignal) =>
    request<QuickCheckResponse>("/api/quick-check", { ...json(body), signal }),
  insights: (days: number, signal?: AbortSignal) => request<Insights>(`/api/insights?days=${days}`, { signal }),
  health: () => request<Health>("/api/health"),
  config: () => request<PublicConfig>("/api/config"),
  policies: () => request<PolicyKB>("/api/policies"),
  list: (signal?: AbortSignal) => request<AnalysisSummary[]>("/api/analyses", { signal }),
  get: (id: string, signal?: AbortSignal) => request<Analysis>(`/api/analyses/${enc(id)}`, { signal }),
  rerun: (id: string) => request<{ id: string }>(`/api/analyses/${enc(id)}/rerun`, { method: "POST" }),
  remove: (id: string) => request<void>(`/api/analyses/${enc(id)}`, { method: "DELETE" }),
  videoUrl: (id: string) => `${API_URL}/api/analyses/${id}/video`,
  frameUrl: (id: string, frameId: string) => `${API_URL}/api/analyses/${enc(id)}/frames/${enc(frameId)}.jpg`,
  reportHtmlUrl: (id: string, download = false) =>
    `${API_URL}/api/analyses/${id}/report.html${download ? "?download=true" : ""}`,
  reportJsonUrl: (id: string) => `${API_URL}/api/analyses/${id}/report.json`,
  evidencePackUrl: (id: string) => `${API_URL}/api/analyses/${id}/evidence-pack.zip`,
  lookupWeb: (id: string) => request<WebBlock>(`/api/analyses/${id}/lookups/web`, { method: "POST" }),
  lookupMusic: (id: string) => request<MusicBlock>(`/api/analyses/${id}/lookups/music`, { method: "POST" }),
  youtubeSuggest: (id: string) => request<YouTubeSuggest>(`/api/analyses/${id}/lookups/youtube/suggest`),
  lookupYouTube: (id: string, query: string) =>
    request<YouTubeBlock>(`/api/analyses/${id}/lookups/youtube`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    }),
  recheckRights: (id: string) =>
    request<{ rights: RightsLine[] }>(`/api/analyses/${id}/recheck-rights`, { method: "POST" }),
  provenanceStatus: () => request<ProvenanceStatus>("/api/provenance/status"),
  rights: () => request<RightsRecord[]>("/api/rights"),
  addRight: (form: FormData) => request<RightsRecord>("/api/rights", { method: "POST", body: form }),
  removeRight: (id: string) => request<void>(`/api/rights/${id}`, { method: "DELETE" }),
  proofUrl: (id: string) => `${API_URL}/api/rights/${id}/proof`,
  catalogue: () => request<CatalogueEntry[]>("/api/catalogue"),
  removeCatalogueEntry: (id: string) => request<void>(`/api/catalogue/${id}`, { method: "DELETE" }),
  connections: () => request<ConnectionsResponse>("/api/connections"),
  authorize: (platform: ConnectedPlatform) =>
    request<{ authorization_url: string }>(`/api/connections/${platform}/authorize`, { method: "POST" }),
  disconnect: (id: string) =>
    request<{ deleted_analyses: number; revoked: boolean | null; revoke_error: string | null }>(`/api/connections/${enc(id)}`, {
      method: "DELETE",
    }),
  media: (id: string, cursor?: string | null, signal?: AbortSignal) =>
    request<{ items: MediaItem[]; next_cursor: string | null }>(
      `/api/connections/${enc(id)}/media${cursor ? `?cursor=${enc(cursor)}` : ""}`,
      { signal },
    ),
  importAnalysis: (body: {
    connection_id: string;
    url?: string;
    media_id?: string;
    language: Language;
    client_label?: string;
    attach_owner_file?: boolean;
    sponsorship?: Sponsorship;
    markets?: MarketId[];
    brief_id?: string;
  }) =>
    request<{ id: string; status: string }>("/api/analyses/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};

/** Attach the creator's own file to an imported post and cross-check it. */
export function attachOwnerFile(
  id: string,
  file: File,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<{ id: string; status: string }> {
  const form = new FormData();
  form.append("file", file);
  return postAnalysisFile(`/api/analyses/${enc(id)}/owner-file`, form, onProgress, signal);
}

/** Upload with progress reporting (fetch has no upload progress events). */
export function uploadAnalysis(
  form: FormData,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<{ id: string; status: string }> {
  return postAnalysisFile("/api/analyses", form, onProgress, signal);
}

/** Fingerprint a past post into the catalogue; the file is discarded server-side. */
export function addToCatalogue(
  form: FormData,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<CatalogueAddResult> {
  return postForm<CatalogueAddResult>("/api/catalogue", form, onProgress, signal);
}

async function postAnalysisFile(
  path: string,
  form: FormData,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<{ id: string; status: string }> {
  const body = await postForm<{ id?: string; status?: string }>(path, form, onProgress, signal);
  if (!body?.id) throw new ApiError("Upload failed (unexpected response)", 0);
  return { id: body.id, status: body.status ?? "queued" };
}

/** Multipart POST with upload progress (fetch has none). Aborting rejects with an AbortError. */
function postForm<T>(
  path: string,
  form: FormData,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const aborted = () => new DOMException("The upload was cancelled.", "AbortError");
    if (signal?.aborted) {
      reject(aborted());
      return;
    }
    const xhr = new XMLHttpRequest();
    signal?.addEventListener("abort", () => xhr.abort(), { once: true });
    xhr.onabort = () => reject(aborted());
    xhr.open("POST", `${API_URL}${path}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && e.total > 0) onProgress(e.loaded / e.total);
    };
    // The body is fully sent; the server is now validating it.
    xhr.upload.onload = () => onProgress(1);
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* ignore */
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as T);
      } else {
        reject(failure(xhr.status, `Upload failed (${xhr.status})`, body, xhr.getResponseHeader("Retry-After")));
      }
    };
    xhr.onerror = () => reject(new ApiError("Cannot reach the CreatorShield API. Check your connection and try again.", 0));
    xhr.send(form);
  });
}
