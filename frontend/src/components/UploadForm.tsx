"use client";

import { useRouter } from "next/navigation";
import { Camera, CircleCheck, Upload, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { api, errorMessage, isAbortError, uploadAnalysis, type Language, type MarketId, type Platform, type QuickCheckRequest } from "@/lib/api";
import { LANGUAGE_OPTIONS, parseHashtags, REVIEW_DRAFT_KEY, type ReviewDraft } from "@/lib/reviewForm";
import { useWorkspace } from "@/lib/workspace";
import { BriefPicker } from "./creator/BriefPicker";
import { LiveCaptionFeedback } from "./creator/LiveCaptionFeedback";
import { MarketPicker } from "./creator/MarketPicker";
import { cn } from "@/lib/cn";
import { fmtBytes } from "@/lib/format";
import { EMPTY_SPONSORSHIP, SponsorshipFields, cleanSponsorship, sponsorshipProblem } from "./SponsorshipFields";
import {
  Button,
  Callout,
  Card,
  Checkbox,
  Field,
  Input,
  Progress,
  RadioCards,
  Section,
  SegmentedControl,
  Skeleton,
  Textarea,
  useToast,
} from "./ui";

const ACCEPT = ".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm";
// Defaults until /api/config answers; the server enforces its own limits either way.
const DEFAULT_LIMITS = { seconds: 1800, mb: 5120 };
// Fallbacks until /api/config answers (config.limits is the source of truth).
const DEFAULT_TEXT_LIMITS = { caption: 5000, hashtags: 100 };

function fmtLimitDuration(seconds: number) {
  return seconds >= 60 ? `${+(seconds / 60).toFixed(1)} min` : `${seconds} s`;
}

function fmtLimitSize(mb: number) {
  return mb >= 1024 ? `${+(mb / 1024).toFixed(1)} GB` : `${mb} MB`;
}

interface LocalInfo {
  duration: number;
  width: number;
  height: number;
}

export function UploadForm() {
  const router = useRouter();
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [info, setInfo] = useState<LocalInfo | null>(null);
  const { settings, platforms, config, agency } = useWorkspace();
  const [platform, setPlatform] = useState<Platform>("");
  const [language, setLanguage] = useState<Language>("en");
  const [markets, setMarkets] = useState<MarketId[]>([]);
  const [briefId, setBriefId] = useState("");
  const [defaultsFor, setDefaultsFor] = useState<object | null>(null);
  const [caption, setCaption] = useState("");
  const [limits, setLimits] = useState(DEFAULT_LIMITS);
  const [hashtags, setHashtags] = useState("");
  const [clientLabel, setClientLabel] = useState("");
  const [sponsorship, setSponsorship] = useState(EMPTY_SPONSORSHIP);
  const [authorized, setAuthorized] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Revoke the last object URL and stop an upload in flight on unmount.
  const previewRef = useRef<string | null>(null);
  useEffect(
    () => () => {
      if (previewRef.current) URL.revokeObjectURL(previewRef.current);
      abortRef.current?.abort();
    },
    [],
  );

  function setPreviewFor(f: File | null) {
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    previewRef.current = f ? URL.createObjectURL(f) : null;
    setPreview(previewRef.current);
  }

  useEffect(() => {
    api
      .config()
      .then((c) => setLimits({ seconds: c.max_duration_seconds, mb: c.max_upload_mb }))
      .catch(() => {});
  }, []);

  const MAX_CAPTION = config?.limits.caption_max ?? DEFAULT_TEXT_LIMITS.caption;
  const MAX_HASHTAGS = config?.limits.hashtags_max ?? DEFAULT_TEXT_LIMITS.hashtags;
  const tagList = parseHashtags(hashtags);
  const hashtagCount = tagList.length;

  // Workspace defaults (and a caption-check hand-off) apply once settings arrive.
  if (settings && defaultsFor !== settings) {
    setDefaultsFor(settings);
    if (defaultsFor === null) {
      let draft: ReviewDraft | null = null;
      try {
        const raw = sessionStorage.getItem(REVIEW_DRAFT_KEY);
        if (raw) {
          draft = JSON.parse(raw) as ReviewDraft;
          sessionStorage.removeItem(REVIEW_DRAFT_KEY);
        }
      } catch {
        draft = null;
      }
      setPlatform(draft?.platform || settings.default_platform);
      setMarkets(draft?.markets?.length ? draft.markets : settings.default_markets);
      setLanguage(settings.default_language);
      if (draft) {
        setCaption(draft.caption);
        setHashtags(draft.hashtags);
        setSponsorship(draft.sponsorship);
        setBriefId(draft.brief_id);
      }
    }
  }

  const sponsorshipKey = JSON.stringify(cleanSponsorship(sponsorship));
  const quickRequest = useMemo<QuickCheckRequest | null>(() => {
    if (!platform || !markets.length || (!caption.trim() && !hashtags.trim())) return null;
    return {
      platform,
      markets,
      caption,
      hashtags: parseHashtags(hashtags),
      sponsorship: JSON.parse(sponsorshipKey),
      ...(briefId ? { brief_id: briefId } : {}),
    };
  }, [platform, markets, caption, hashtags, briefId, sponsorshipKey]);

  function applySuggested(next: string) {
    const previous = caption;
    setCaption(next.slice(0, MAX_CAPTION));
    toast({
      tone: "success",
      title: "Suggested caption applied",
      description: "Edit it so it is true for your arrangement.",
      action: { label: "Undo", onClick: () => setCaption(previous) },
    });
  }

  function pick(f: File | undefined) {
    setError(null);
    setInfo(null);
    if (!f) return;
    const ext = f.name.toLowerCase().split(".").pop();
    if (!["mp4", "mov", "webm"].includes(ext ?? "")) {
      setError("Only MP4, MOV and WebM videos are supported.");
      return;
    }
    if (f.size > limits.mb * 1024 * 1024) {
      setError(
        `This file is larger than ${fmtLimitSize(limits.mb)}. Export or compress it at 1080p first ` +
          "(for example HandBrake's “Fast 1080p30” preset). Reviews never use more than 1080p.",
      );
      return;
    }
    setFile(f);
    setPreviewFor(f);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (progress === null) pick(e.dataTransfer.files?.[0]);
  }

  const uploading = progress !== null;
  const tooLong = info != null && info.duration > limits.seconds + 0.5;
  const tooManyTags = hashtagCount > MAX_HASHTAGS;
  const sponsorError = sponsorshipProblem(sponsorship);
  const missing = !file
    ? "Choose a video to review."
    : !markets.length
      ? "Choose at least one audience market."
      : !authorized
        ? "Confirm that you may have this video reviewed."
        : null;
  const canSubmit = file && platform && markets.length && authorized && !tooLong && !tooManyTags && !sponsorError && !uploading;

  function reset() {
    setFile(null);
    setPreviewFor(null);
    setInfo(null);
    setCaption("");
    setHashtags("");
    setClientLabel("");
    setSponsorship(EMPTY_SPONSORSHIP);
    setBriefId("");
    setAuthorized(false);
    setProgress(null);
  }

  async function submit() {
    if (!file) return;
    setError(null);
    setProgress(0);
    const form = new FormData();
    form.append("file", file);
    form.append("platform", platform);
    form.append("language", language);
    form.append("caption", caption);
    form.append("sponsorship", JSON.stringify(cleanSponsorship(sponsorship)));
    form.append("hashtags", hashtags);
    form.append("markets", markets.join(","));
    if (briefId) form.append("brief_id", briefId);
    if (agency && clientLabel.trim()) form.append("client_label", clientLabel.trim());
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const res = await uploadAnalysis(form, setProgress, controller.signal);
      // This route stays mounted (hidden) after navigation; reset it so a later visit starts clean.
      reset();
      router.push(`/analyses/${res.id}`);
    } catch (e) {
      setProgress(null);
      if (isAbortError(e)) {
        toast({ tone: "info", title: "Upload cancelled", description: "Nothing was sent for review." });
      } else {
        setError(errorMessage(e));
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <Section
        title="Video"
        description={`MP4, MOV or WebM · up to ${fmtLimitDuration(limits.seconds)} · max ${fmtLimitSize(limits.mb)}`}
        className="lg:sticky lg:top-[80px]"
      >
        {!file ? (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={cn(
              "flex aspect-[4/3] w-full flex-col items-center justify-center rounded-[10px] border-2 border-dashed px-6 text-center transition-colors duration-[120ms] lg:aspect-auto lg:h-[380px]",
              dragging ? "border-accent bg-accent-soft" : "border-line-strong bg-surface-2 hover:border-ink-3",
            )}
          >
            <span className="flex size-11 items-center justify-center rounded-full border border-line bg-surface text-accent">
              <Upload className="size-5" aria-hidden />
            </span>
            <span className="mt-3 text-sm font-semibold text-ink">Choose a video or drop it here</span>
            <span className="mt-1 text-[13px] text-ink-3">The file you plan to publish, before you post it.</span>
          </button>
        ) : (
          <div className="space-y-3">
            <div className="flex justify-center overflow-hidden rounded-[10px] bg-[#0b1220]">
              {preview && (
                <video
                  src={preview}
                  controls
                  playsInline
                  className="max-h-[420px]"
                  onLoadedMetadata={(e) => {
                    const v = e.currentTarget;
                    setInfo({ duration: v.duration, width: v.videoWidth, height: v.videoHeight });
                  }}
                />
              )}
            </div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-[8px] border border-line bg-surface-2 px-3 py-2.5 text-[13px]">
              <dt className="text-ink-3">File</dt>
              <dd className="truncate text-right font-medium" title={file.name}>
                {file.name}
              </dd>
              <dt className="text-ink-3">Size</dt>
              <dd className="tabular text-right">{fmtBytes(file.size)}</dd>
              <dt className="text-ink-3">Duration</dt>
              <dd className={cn("tabular text-right", tooLong && "font-semibold text-critical-fg")}>
                {info ? `${info.duration.toFixed(1)}s` : "…"}
              </dd>
              <dt className="text-ink-3">Resolution</dt>
              <dd className="tabular text-right">{info ? `${info.width}×${info.height}` : "…"}</dd>
            </dl>
            {tooLong && (
              <Callout tone="danger" title="This video is too long">
                Reviews accept up to {fmtLimitDuration(limits.seconds)}. Trim it before uploading.
              </Callout>
            )}
            <Button
              variant="ghost"
              size="sm"
              leadingIcon={<Camera />}
              disabled={uploading}
              onClick={() => {
                setFile(null);
                setPreviewFor(null);
                setInfo(null);
                inputRef.current?.click();
              }}
            >
              Choose a different file
            </Button>
          </div>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          tabIndex={-1}
          aria-hidden
          onChange={(e) => {
            pick(e.target.files?.[0]);
            // The chosen File is kept in state; clearing the input lets the same file be picked again.
            e.target.value = "";
          }}
        />
      </Section>

      <div className="min-w-0 space-y-6">
        <Section title="Where it will be posted" description="Findings cite the rules for this platform and these audience markets.">
          <div className="space-y-5">
            {platforms.length ? (
              <RadioCards
                label="Target platform"
                value={platform}
                onChange={setPlatform}
                options={platforms.map((p) => ({ value: p.id, title: p.label, description: p.description }))}
                className="sm:grid-cols-3"
              />
            ) : (
              <Skeleton className="h-20 w-full rounded-[10px]" />
            )}
            <div className="space-y-1.5">
              <div className="text-[13px] font-medium text-ink">Audience markets</div>
              <MarketPicker value={markets} onChange={setMarkets} />
            </div>
            <div className="space-y-1.5">
              <div className="text-[13px] font-medium text-ink" id="upload-language">
                Spoken language
              </div>
              <SegmentedControl label="Spoken language" value={language} onChange={setLanguage} options={LANGUAGE_OPTIONS} />
            </div>
          </div>
        </Section>

        <Section title="Caption and hashtags" description="Disclosure checks read the opening of the caption, so paste it exactly as you will post it.">
          <div className="space-y-4">
            <Field label="Caption" counter={{ value: caption.length, max: MAX_CAPTION }}>
              {(p) => (
                <Textarea
                  {...p}
                  value={caption}
                  onChange={(e) => setCaption(e.target.value.slice(0, MAX_CAPTION))}
                  rows={4}
                  placeholder="The caption you plan to publish"
                />
              )}
            </Field>
            <Field
              label="Hashtags"
              counter={{ value: hashtagCount, max: MAX_HASHTAGS, unit: "tags" }}
              error={tooManyTags ? `At most ${MAX_HASHTAGS} hashtags are accepted.` : null}
            >
              {(p) => <Input {...p} value={hashtags} onChange={(e) => setHashtags(e.target.value)} placeholder="#fitness #morningroutine" />}
            </Field>
            <LiveCaptionFeedback request={quickRequest} onApply={applySuggested} />
          </div>
        </Section>

        <Section title={agency ? "Sponsorship, brief and client" : "Sponsorship and brief"}>
          <div className="space-y-4">
            <SponsorshipFields value={sponsorship} onChange={setSponsorship} />
            <BriefPicker value={briefId} onChange={(id) => setBriefId(id)} />
            {agency && (
            <Field
              label="Client or account"
              hint="Optional. Groups this video in the catalogue, so footage reused under a different client is flagged."
            >
              {(p) => (
                <Input
                  {...p}
                  value={clientLabel}
                  onChange={(e) => setClientLabel(e.target.value.slice(0, 100))}
                  placeholder="e.g. FitFuel brand account"
                />
              )}
            </Field>
            )}
          </div>
        </Section>

        <Card className="space-y-4 p-5">
          <Checkbox
            checked={authorized}
            onChange={(e) => setAuthorized(e.target.checked)}
            label="I own this video or am authorised to have it reviewed."
            description="The result is automated guidance, not legal advice, and cannot guarantee how a platform will treat the content."
          />
          {error && (
            <Callout tone="danger" title="Upload failed">
              {error}
            </Callout>
          )}
          {uploading ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3 text-[13px]">
                <span className="font-medium text-ink">{progress < 1 ? "Uploading…" : "Checking the video…"}</span>
                <span className="tabular text-ink-3">
                  {file && progress < 1 ? `${fmtBytes(file.size * progress)} of ${fmtBytes(file.size)}` : `${Math.round(progress * 100)}%`}
                </span>
              </div>
              <Progress value={progress < 1 ? progress * 100 : null} label="Upload progress" />
              <div className="flex justify-end">
                <Button size="sm" variant="ghost" leadingIcon={<X />} onClick={() => abortRef.current?.abort()}>
                  Cancel upload
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-[13px] text-ink-3">{missing ?? "Ready. The review usually takes about a minute per minute of video."}</p>
              <Button variant="primary" size="lg" leadingIcon={<CircleCheck />} disabled={!canSubmit} onClick={submit}>
                Start review
              </Button>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
