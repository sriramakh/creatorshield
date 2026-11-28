import type { Confidence, FindingType, Severity } from "./api";

export const LANGUAGE_LABEL: Record<string, string> = { en: "English", hi: "Hindi" };

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

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

export type ReportSection = "community" | "disclosure" | "other";

const COMMUNITY_RULES = new Set(["YT-MON-AD-FRIENDLY", "YT-HASHTAGS"]);

/** Matches backend/app/reports/sections.py. Uses the API field when the server sent one. */
export function reportSection(f: {
  category: string;
  policy_rule_ids: string[];
  report_section?: string;
}): ReportSection {
  if (f.report_section === "community" || f.report_section === "disclosure" || f.report_section === "other") {
    return f.report_section;
  }
  if (f.category === "disclosure") return "disclosure";
  if (f.category === "community_guidelines" || f.category === "harmful_content") return "community";
  if (
    f.policy_rule_ids.some(
      (id) => COMMUNITY_RULES.has(id) || id.startsWith("YT-CG-") || id.startsWith("META-CS-"),
    )
  ) {
    return "community";
  }
  return "other";
}

/** Display title for a review: platform title, else the caption's first line. */
export function reviewTitle(a: { source_title?: string | null; caption?: string | null }): string {
  return a.source_title?.trim() || a.caption?.trim().split(/\r?\n/)[0] || "Untitled video";
}

export const SOURCE_LABEL: Record<string, string> = {
  upload: "Uploaded file",
  instagram: "Instagram import",
  youtube: "YouTube import",
};

export const MODE_LABEL: Record<string, string> = {
  full_video: "Full video review",
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
  if (seconds == null || !Number.isFinite(seconds)) return "—";
  // Round to tenths first so 59.97 s becomes 1:00.0, not 0:60.0.
  const tenths = Math.round(Math.max(0, seconds) * 10);
  const m = Math.floor(tenths / 600);
  const s = (tenths - m * 600) / 10;
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
