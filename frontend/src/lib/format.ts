import type { Confidence, FindingType, Platform, RiskLevel, Severity } from "./api";

export const PLATFORM_LABEL: Record<Platform, string> = {
  youtube_shorts: "YouTube Shorts",
  instagram_reels: "Instagram Reels",
};

export const LANGUAGE_LABEL: Record<string, string> = { en: "English", hi: "Hindi" };

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

export const SEVERITY_STYLE: Record<Severity, { badge: string; bar: string; dot: string }> = {
  critical: { badge: "bg-red-700 text-white", bar: "border-l-red-700", dot: "bg-red-700" },
  high: { badge: "bg-red-500 text-white", bar: "border-l-red-500", dot: "bg-red-500" },
  medium: { badge: "bg-amber-500 text-white", bar: "border-l-amber-500", dot: "bg-amber-500" },
  low: { badge: "bg-sky-600 text-white", bar: "border-l-sky-600", dot: "bg-sky-600" },
  info: { badge: "bg-slate-400 text-white", bar: "border-l-slate-300", dot: "bg-slate-400" },
};

export const TYPE_LABEL: Record<FindingType, string> = {
  observed_evidence: "Observed evidence",
  suspected_violation: "Suspected issue",
  licensing_uncertainty: "Licensing uncertainty",
  cannot_check: "Cannot be checked",
};

export const TYPE_HELP: Record<FindingType, string> = {
  observed_evidence: "Directly visible or audible in the cited moment.",
  suspected_violation: "A judgement that may change with context the system cannot see.",
  licensing_uncertainty: "Rights or permission status cannot be determined from the video.",
  cannot_check: "A check this system is not able to perform.",
};

export const CONFIDENCE_LEVEL: Record<Confidence, number> = { low: 1, medium: 2, high: 3 };

export const RISK_STYLE: Record<RiskLevel, { text: string; bg: string; ring: string; label: string }> = {
  low: { text: "text-emerald-700", bg: "bg-emerald-50", ring: "ring-emerald-200", label: "Low" },
  moderate: { text: "text-amber-700", bg: "bg-amber-50", ring: "ring-amber-200", label: "Moderate" },
  elevated: { text: "text-orange-700", bg: "bg-orange-50", ring: "ring-orange-200", label: "Elevated" },
  high: { text: "text-red-700", bg: "bg-red-50", ring: "ring-red-200", label: "High" },
};

export const SOURCE_LABEL: Record<string, string> = {
  upload: "Uploaded file",
  instagram: "Instagram import",
  youtube: "YouTube import",
};

export const MODE_LABEL: Record<string, string> = {
  full_video: "Full video analysis",
  caption_thumbnail: "Caption + thumbnail only",
  metadata_only: "Metadata + captions only",
  cross_checked: "Full review, cross-checked",
};

export const STAGE_LABEL: Record<string, string> = {
  queued: "Queued",
  awaiting_file: "Waiting for your file",
  fetching_source: "Fetching from platform",
  optimizing_video: "Making a smaller working copy",
  extracting: "Preparing video",
  extracting_audio: "Extracting audio",
  transcribing: "Transcribing speech",
  sampling_frames: "Sampling key frames",
  reading_on_screen_text: "Reading on-screen text",
  provenance: "Provenance & rights checks",
  rule_checks: "Running rule checks",
  ai_review: "AI policy review",
  finalizing: "Finalizing report",
  completed: "Completed",
  failed: "Failed",
};

export function fmtTime(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds - m * 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
}

export function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

/** 42.3s under a minute, otherwise m:ss (or h:mm:ss). */
export function fmtLength(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const s = Math.round(seconds);
  const hms = [Math.floor(s / 3600), Math.floor((s % 3600) / 60), s % 60];
  const [h, m, sec] = hms.map((v) => String(v).padStart(2, "0"));
  return s >= 3600 ? `${+h}:${m}:${sec}` : `${+m}:${sec}`;
}

export function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Calendar date (YYYY-MM-DD or ISO) without shifting across time zones. */
export function fmtDay(iso: string): string {
  const d = iso.length === 10 ? new Date(`${iso}T00:00:00Z`) : new Date(iso);
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    ...(iso.length === 10 ? { timeZone: "UTC" } : {}),
  });
}

export function fmtUsd(value: number): string {
  return `$${value < 0.01 && value > 0 ? value.toFixed(3) : value.toFixed(2)}`;
}
