"use client";

import { useEffect, useState } from "react";
import { api, type PublicConfig } from "@/lib/api";
import { Banner } from "./ui";

/** Shows a prominent notice when AI review is unavailable or in mock mode. */
export function SystemStatusBanner() {
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.config().then(setConfig).catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <Banner tone="danger" title="Backend unavailable">{error}</Banner>;
  if (!config) return null;
  if (config.mock_mode)
    return (
      <Banner tone="mock" title="MOCK MODE is enabled">
        AI findings are placeholders generated without calling an AI model. Rule-based checks are real. Set{" "}
        <code className="font-mono">AI_PROVIDER=anthropic</code> for a real review.
      </Banner>
    );
  if (!config.ai_credentials_present)
    return (
      <Banner tone="warning" title="AI review is not configured">
        No API key is set for <strong>{config.ai_provider}</strong>, so analyses include rule-based checks only. Add the key to{" "}
        <code className="font-mono">backend/.env</code> and restart the backend and worker.
      </Banner>
    );
  return null;
}
