"use client";

import { useRouter } from "next/navigation";
import { ArrowRight, LoaderCircle, ScanText } from "lucide-react";
import { useMemo, useState } from "react";
import type { MarketId, Platform, QuickCheckRequest } from "@/lib/api";
import { NEW_REVIEW_HREF } from "@/lib/nav";
import { useQuickCheck } from "@/lib/useQuickCheck";
import { useWorkspace } from "@/lib/workspace";
import { BriefCheckTable } from "./creator/BriefCheckTable";
import { BriefPicker } from "./creator/BriefPicker";
import { CaptionFixPanel } from "./creator/CaptionFixPanel";
import { MarketPicker } from "./creator/MarketPicker";
import { MarketLabelTable, ReadinessPanel } from "./creator/Readiness";
import { FindingCard } from "./review/FindingCard";
import { PageContainer } from "./shell/AppShell";
import { EMPTY_SPONSORSHIP, SponsorshipFields, cleanSponsorship, sponsorshipProblem } from "./SponsorshipFields";
import { parseHashtags, REVIEW_DRAFT_KEY, type ReviewDraft } from "@/lib/reviewForm";
import { Button, Callout, Card, EmptyState, ErrorNotice, Field, Input, PageHeader, Section, Select, Textarea, useToast } from "./ui";

const noop = () => {};

/** Instant, rule-based caption check: nothing is stored. */
export function CaptionCheckPage() {
  const router = useRouter();
  const toast = useToast();
  const { settings, platforms, config } = useWorkspace();
  const [platform, setPlatform] = useState<Platform>("");
  const [markets, setMarkets] = useState<MarketId[]>([]);
  const [caption, setCaption] = useState("");
  const [hashtags, setHashtags] = useState("");
  const [sponsorship, setSponsorship] = useState(EMPTY_SPONSORSHIP);
  const [briefId, setBriefId] = useState("");
  const [defaultsApplied, setDefaultsApplied] = useState(false);
  if (settings && !defaultsApplied) {
    setDefaultsApplied(true);
    setPlatform(settings.default_platform);
    setMarkets(settings.default_markets);
  }

  const maxCaption = config?.limits.caption_max ?? 5000;
  const maxTags = config?.limits.hashtags_max ?? 100;
  const tags = parseHashtags(hashtags);
  const sponsorshipKey = JSON.stringify(cleanSponsorship(sponsorship));
  const sponsorError = sponsorshipProblem(sponsorship);
  const request = useMemo<QuickCheckRequest | null>(() => {
    if (!platform || !markets.length || (!caption.trim() && !hashtags.trim()) || sponsorError) return null;
    return {
      platform,
      markets,
      caption,
      hashtags: parseHashtags(hashtags),
      sponsorship: JSON.parse(sponsorshipKey),
      ...(briefId ? { brief_id: briefId } : {}),
    };
  }, [platform, markets, caption, hashtags, briefId, sponsorshipKey, sponsorError]);
  const { result, error, pending } = useQuickCheck(request);

  function replaceCaption() {
    if (!result) return;
    const previous = caption;
    setCaption(result.caption_fix.suggested_caption.slice(0, maxCaption));
    toast({
      tone: "success",
      title: "Caption replaced",
      description: "Edit it so it is true for your arrangement.",
      action: { label: "Undo", onClick: () => setCaption(previous) },
    });
  }

  function startReview() {
    const draft: ReviewDraft = {
      platform,
      markets,
      caption,
      hashtags,
      sponsorship: cleanSponsorship(sponsorship),
      brief_id: briefId,
    };
    try {
      sessionStorage.setItem(REVIEW_DRAFT_KEY, JSON.stringify(draft));
    } catch {
      /* storage blocked: the form opens empty */
    }
    router.push(NEW_REVIEW_HREF);
  }

  const findings = (result?.findings ?? []).slice().sort((a, b) => ["critical", "high", "medium", "low", "info"].indexOf(a.severity) - ["critical", "high", "medium", "low", "info"].indexOf(b.severity));

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        title="Caption check"
        description="An instant, rule-based check of a caption and hashtags against platform rules and your markets’ disclosure guidance. Nothing is stored."
      />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <Section title="Your caption" className="lg:sticky lg:top-[80px]">
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Platform">
                {(p) => (
                  <Select {...p} value={platform} onChange={(e) => setPlatform(e.target.value)} disabled={!platforms.length}>
                    {platforms.map((pl) => (
                      <option key={pl.id} value={pl.id}>
                        {pl.label}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            </div>
            <div className="space-y-1.5">
              <div className="text-[13px] font-medium text-ink">Audience markets</div>
              <MarketPicker value={markets} onChange={setMarkets} />
            </div>
            <Field label="Caption" counter={{ value: caption.length, max: maxCaption }}>
              {(p) => (
                <Textarea
                  {...p}
                  rows={6}
                  value={caption}
                  onChange={(e) => setCaption(e.target.value.slice(0, maxCaption))}
                  placeholder="Paste the caption exactly as you will post it"
                />
              )}
            </Field>
            <Field label="Hashtags" counter={{ value: tags.length, max: maxTags, unit: "tags" }} error={tags.length > maxTags ? `At most ${maxTags} hashtags are accepted.` : null}>
              {(p) => <Input {...p} value={hashtags} onChange={(e) => setHashtags(e.target.value)} placeholder="#skincare #morningroutine" />}
            </Field>
            <SponsorshipFields value={sponsorship} onChange={setSponsorship} />
            <BriefPicker value={briefId} onChange={(id) => setBriefId(id)} />
            <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
              <Button trailingIcon={<ArrowRight />} onClick={startReview} disabled={!platform || !markets.length}>
                Start a full review with this caption
              </Button>
              <span className="text-[12px] text-ink-3">The full review also reads speech, on-screen text and audio.</span>
            </div>
          </div>
        </Section>

        <div className="min-w-0 space-y-5" aria-live="polite" aria-busy={pending}>
          {!request ? (
            <Card>
              <EmptyState
                icon={<ScanText />}
                title="Type or paste a caption"
                description="You get a verdict, the disclosure status in each selected market, any flagged wording with the official rule behind it, and a suggested caption when the disclosure is not clear. Rule-based and instant; the video itself is not checked."
              />
            </Card>
          ) : (
            <>
              {error && <ErrorNotice title="The caption check did not run" message={error} />}
              {!result && !error && (
                <Card className="flex items-center gap-2 p-5 text-sm text-ink-3">
                  <LoaderCircle className="size-4 animate-spin" aria-hidden /> Checking…
                </Card>
              )}
              {result && (
                <div className={pending ? "space-y-5 opacity-70 transition-opacity" : "space-y-5 transition-opacity"}>
                  <ReadinessPanel
                    compact
                    readiness={result.readiness}
                    onRow={(item) => document.getElementById(`finding-${item.finding_ids[0]}`)?.scrollIntoView({ behavior: "smooth", block: "center" })}
                  />
                  {result.caption_fix.needed && (
                    <Section title="Suggested caption" description="A clearer opening disclosure for the selected markets.">
                      <CaptionFixPanel fix={result.caption_fix} original={caption} onReplace={replaceCaption} />
                    </Section>
                  )}
                  <Section title="Disclosure by market">
                    <MarketLabelTable md={result.market_disclosure} />
                  </Section>
                  {result.brief_check && (
                    <Section title="Brand brief">
                      <BriefCheckTable check={result.brief_check} />
                    </Section>
                  )}
                  <section aria-labelledby="check-findings" className="space-y-3">
                    <h2 id="check-findings" className="text-[15px] font-semibold">
                      Findings <span className="tabular font-normal text-ink-3">({findings.length})</span>
                    </h2>
                    {findings.length === 0 ? (
                      <p className="rounded-[10px] border border-dashed border-line-strong px-4 py-3 text-[13px] text-ink-3">
                        No issues found by these checks in the caption and hashtags.
                      </p>
                    ) : (
                      findings.map((f) => <FindingCard key={f.id} finding={f} onSeek={noop} />)
                    )}
                  </section>
                  <Callout tone="info" title="Not checked here">
                    <ul className="list-disc space-y-0.5 pl-4">
                      {result.not_checked.map((n) => (
                        <li key={n}>{n}</li>
                      ))}
                    </ul>
                  </Callout>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
