export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type Platform = "youtube_shorts" | "instagram_reels";
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

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  } catch {
    throw new ApiError("Cannot reach the CreatorShield API. Is the backend running?", 0);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  config: () => request<PublicConfig>("/api/config"),
  policies: () => request<PolicyKB>("/api/policies"),
  list: () => request<AnalysisSummary[]>("/api/analyses"),
  get: (id: string) => request<Analysis>(`/api/analyses/${id}`),
  rerun: (id: string) => request<{ id: string }>(`/api/analyses/${id}/rerun`, { method: "POST" }),
  remove: (id: string) => request<void>(`/api/analyses/${id}`, { method: "DELETE" }),
  videoUrl: (id: string) => `${API_URL}/api/analyses/${id}/video`,
  frameUrl: (id: string, frameId: string) => `${API_URL}/api/analyses/${id}/frames/${frameId}.jpg`,
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
    request<{ deleted_analyses: number }>(`/api/connections/${id}`, { method: "DELETE" }),
  media: (id: string, cursor?: string | null) =>
    request<{ items: MediaItem[]; next_cursor: string | null }>(
      `/api/connections/${id}/media${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`,
    ),
  importAnalysis: (body: {
    connection_id: string;
    url?: string;
    media_id?: string;
    language: Language;
    client_label?: string;
    attach_owner_file?: boolean;
    sponsorship?: import("@/components/SponsorshipFields").Sponsorship;
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
): Promise<{ id: string; status: string }> {
  const form = new FormData();
  form.append("file", file);
  return postAnalysisFile(`/api/analyses/${id}/owner-file`, form, onProgress);
}

/** Upload with progress reporting (fetch has no upload progress events). */
export function uploadAnalysis(
  form: FormData,
  onProgress: (fraction: number) => void,
): Promise<{ id: string; status: string }> {
  return postAnalysisFile("/api/analyses", form, onProgress);
}

/** Fingerprint a past post into the catalogue; the file is discarded server-side. */
export function addToCatalogue(form: FormData, onProgress: (fraction: number) => void): Promise<CatalogueAddResult> {
  return postForm<CatalogueAddResult>("/api/catalogue", form, onProgress);
}

async function postAnalysisFile(
  path: string,
  form: FormData,
  onProgress: (fraction: number) => void,
): Promise<{ id: string; status: string }> {
  const body = await postForm<{ id?: string; status?: string }>(path, form, onProgress);
  if (!body?.id) throw new ApiError("Upload failed (unexpected response)", 0);
  return { id: body.id, status: body.status ?? "queued" };
}

function postForm<T>(path: string, form: FormData, onProgress: (fraction: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}${path}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
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
        const detail = (body as { detail?: unknown } | null)?.detail;
        reject(new ApiError(typeof detail === "string" ? detail : `Upload failed (${xhr.status})`, xhr.status));
      }
    };
    xhr.onerror = () => reject(new ApiError("Cannot reach the CreatorShield API.", 0));
    xhr.send(form);
  });
}
