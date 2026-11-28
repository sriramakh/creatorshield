"use client";

import { aiLimitation, useSystemConfig } from "@/lib/useSystemConfig";
import { Callout } from "./ui";

/** The one inline notice for screens whose results depend on the AI review. */
export function AiLimitCallout({ className }: { className?: string }) {
  const { config } = useSystemConfig();
  const limit = aiLimitation(config);
  if (!limit || !config) return null;
  return limit === "mock" ? (
    <Callout tone="warning" title="Mock AI is on" className={className}>
      AI findings in new reviews are placeholders labelled MOCK. Rule-based checks are real.
    </Callout>
  ) : (
    <Callout tone="warning" title="AI review is not configured" className={className}>
      No API key is set for {config.ai_provider}, so new reviews include rule-based checks only.
    </Callout>
  );
}
