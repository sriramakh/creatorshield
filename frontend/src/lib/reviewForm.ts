import type { Language, MarketId, Platform, Sponsorship } from "./api";

export const LANGUAGE_OPTIONS: { value: Language; label: string }[] = [
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
];

/** Hand-off from the caption check page ("Start a full review with this caption"). */
export const REVIEW_DRAFT_KEY = "cs-review-draft";
export interface ReviewDraft {
  platform: Platform;
  markets: MarketId[];
  caption: string;
  hashtags: string;
  sponsorship: Sponsorship;
  brief_id: string;
}

export function parseHashtags(raw: string) {
  return raw
    .split(/[\s,]+/)
    .map((t) => t.replace(/^#/, "").trim())
    .filter(Boolean);
}
