"use client";

import { LoaderCircle, Wand } from "lucide-react";
import type { QuickCheckRequest } from "@/lib/api";
import { useQuickCheck } from "@/lib/useQuickCheck";
import { Badge, Button, SeverityBadge, VerdictBadge } from "../ui";
import { MarketStatusRow } from "./Readiness";

/**
 * Live, advisory caption feedback under the caption field (debounced quick check). It never
 * blocks submitting; the full review re-checks everything.
 */
export function LiveCaptionFeedback({
  request,
  onApply,
}: {
  request: QuickCheckRequest | null;
  onApply: (caption: string) => void;
}) {
  const { result, error, pending } = useQuickCheck(request);
  if (!request) return null;
  const findings = (result?.findings ?? []).filter((f) => f.severity !== "info").slice(0, 3);
  return (
    <div className="space-y-2.5 rounded-[8px] border border-line bg-surface-2 px-3 py-2.5" aria-live="polite" aria-busy={pending}>
      <div className="flex flex-wrap items-center gap-2 text-[12px] text-ink-3">
        <span className="font-medium text-ink-2">Caption check</span>
        {result && <VerdictBadge verdict={result.readiness.verdict} />}
        {pending && (
          <span className="inline-flex items-center gap-1">
            <LoaderCircle className="size-3.5 animate-spin" aria-hidden /> Checking…
          </span>
        )}
        {!pending && !result && !error && <span>Checks as you type.</span>}
        <span className="ml-auto">Advisory, never blocks your review</span>
      </div>
      {error && <p className="text-[13px] text-ink-3">The caption check is unavailable right now ({error}). You can still start the review.</p>}
      {result && (
        <>
          <MarketStatusRow md={result.market_disclosure} needed={result.caption_fix.needed} />
          {findings.length > 0 && (
            <ul className="space-y-1">
              {findings.map((f) => (
                <li key={f.id} className="flex items-start gap-2 text-[13px] text-ink">
                  <SeverityBadge severity={f.severity} className="shrink-0" />
                  <span className="pt-0.5">{f.title}</span>
                </li>
              ))}
            </ul>
          )}
          {result.brief_check && result.brief_check.failed > 0 && (
            <p className="text-[13px] text-ink-2">
              <Badge tone="critical" className="mr-1.5">
                Brief
              </Badge>
              {result.brief_check.failed} brief requirement{result.brief_check.failed === 1 ? "" : "s"} not met in the caption.
            </p>
          )}
          {result.caption_fix.needed && (
            <div className="flex flex-wrap items-center gap-2 border-t border-line pt-2">
              <Button size="sm" leadingIcon={<Wand />} onClick={() => onApply(result.caption_fix.suggested_caption)}>
                Use suggested caption
              </Button>
              <span className="min-w-0 flex-1 truncate text-[12px] text-ink-3" title={result.caption_fix.suggested_caption}>
                {result.caption_fix.suggested_caption}
              </span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
