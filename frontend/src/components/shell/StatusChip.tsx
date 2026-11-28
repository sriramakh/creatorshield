"use client";

import { aiLimitation, reloadSystemConfig, useSystemConfig } from "@/lib/useSystemConfig";
import { cn } from "@/lib/cn";
import { Button, Popover, PopoverContent, PopoverTrigger, StatusDot, type StatusTone } from "../ui";

function summary(state: ReturnType<typeof useSystemConfig>): { tone: StatusTone; label: string; detail: string } {
  if (!state.loaded) return { tone: "info", label: "Checking status", detail: "" };
  if (state.status === 401) return { tone: "critical", label: "Sign-in needed", detail: "" };
  if (state.error || !state.config) return { tone: "critical", label: "API unreachable", detail: state.error ?? "" };
  const limit = aiLimitation(state.config);
  if (limit === "mock") return { tone: "medium", label: "Mock AI", detail: "" };
  if (limit === "rules_only") return { tone: "medium", label: "Rules only", detail: "" };
  return { tone: "success", label: "AI review on", detail: "" };
}

/** Persistent system-status chip with a popover explaining mock mode and missing AI. */
export function StatusChip({ compact = false, className }: { compact?: boolean; className?: string }) {
  const state = useSystemConfig();
  const s = summary(state);
  const c = state.config;
  return (
    <Popover>
      <PopoverTrigger
        aria-label={`System status: ${s.label}`}
        className={cn(
          "inline-flex h-8 max-w-full items-center gap-2 rounded-[6px] border border-line bg-surface px-2.5 text-[13px] font-medium text-ink-2 hover:bg-surface-2 hover:text-ink",
          compact && "w-8 justify-center px-0",
          className,
        )}
      >
        <StatusDot tone={s.tone} pulse={!state.loaded} />
        {!compact && <span className="truncate">{s.label}</span>}
      </PopoverTrigger>
      <PopoverContent side="top" align="start" className="w-80">
        <div className="flex items-center gap-2">
          <StatusDot tone={s.tone} />
          <h2 className="text-[15px] font-semibold">{s.label}</h2>
        </div>
        {state.error && (
          <>
            <p className="mt-2 text-[13px] text-ink-2">{state.error}</p>
            <Button size="sm" className="mt-3" onClick={reloadSystemConfig}>
              Check again
            </Button>
          </>
        )}
        {c && (
          <>
            <p className="mt-2 text-[13px] text-ink-2">
              {c.mock_mode
                ? "No AI model is called. AI findings are placeholders and are labelled MOCK. Rule-based checks are real."
                : !c.ai_credentials_present
                  ? `No API key is set for ${c.ai_provider}, so reviews include rule-based checks only.`
                  : "Reviews combine rule-based checks with an AI policy review."}
            </p>
            <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 border-t border-line pt-3 text-[13px]">
              <dt className="text-ink-3">AI provider</dt>
              <dd className="truncate text-right text-ink">
                {c.ai_provider}
                {c.ai_model && c.ai_model !== c.ai_provider ? ` · ${c.ai_model}` : ""}
              </dd>
              <dt className="text-ink-3">Speech to text</dt>
              <dd className="truncate text-right text-ink">
                {c.stt_provider}
                {c.whisper_model ? ` · ${c.whisper_model}` : ""}
              </dd>
              <dt className="text-ink-3">On-screen text</dt>
              <dd className="text-right text-ink">{c.ocr_enabled ? "On" : "Off"}</dd>
              <dt className="text-ink-3">Media kept for</dt>
              <dd className="text-right text-ink">{c.delete_media_after_analysis ? "Deleted after review" : `${c.retention_hours} hours`}</dd>
              <dt className="text-ink-3">Paid lookups</dt>
              <dd className="text-right text-ink">
                {c.music_id_configured || c.web_detection_configured ? `On · $${c.paid_lookups_monthly_budget_usd}/month cap` : "Off"}
              </dd>
            </dl>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}
