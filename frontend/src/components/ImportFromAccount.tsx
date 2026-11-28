"use client";

import { useRouter } from "next/navigation";
import { CircleCheck, ImageOff, Link2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  attachOwnerFile,
  errorMessage,
  isAbortError,
  safeUrl,
  type Connection,
  type ConnectionsResponse,
  type Language,
  type MarketId,
  type MediaItem,
} from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { BriefPicker } from "./creator/BriefPicker";
import { MarketPicker } from "./creator/MarketPicker";
import { cn } from "@/lib/cn";
import { fmtBytes, fmtDate, MODE_LABEL } from "@/lib/format";
import { EMPTY_SPONSORSHIP, SponsorshipFields, cleanSponsorship, sponsorshipProblem } from "./SponsorshipFields";
import {
  Badge,
  Button,
  ButtonLink,
  Callout,
  Card,
  Checkbox,
  EmptyState,
  ErrorNotice,
  Field,
  FilePicker,
  Input,
  Progress,
  Section,
  SegmentedControl,
  Select,
  Skeleton,
} from "./ui";
import { LANGUAGE_OPTIONS } from "@/lib/reviewForm";

// backend/app/schemas.py ImportRequest.url
const MAX_LINK = 500;
const ACCEPT = ".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm";

const MODE_TONE = { full_video: "success", caption_thumbnail: "medium", metadata_only: "low", cross_checked: "success" } as const;

export function ImportFromAccount() {
  const router = useRouter();
  const [data, setData] = useState<ConnectionsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connId, setConnId] = useState<string | null>(null);
  const [media, setMedia] = useState<MediaItem[] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [mediaError, setMediaError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [link, setLink] = useState("");
  const { settings, agency } = useWorkspace();
  const [language, setLanguage] = useState<Language>("en");
  const [markets, setMarkets] = useState<MarketId[]>([]);
  const [briefId, setBriefId] = useState("");
  const [defaultsApplied, setDefaultsApplied] = useState(false);
  if (settings && !defaultsApplied) {
    setDefaultsApplied(true);
    setMarkets(settings.default_markets);
    setLanguage(settings.default_language);
  }
  const [clientLabel, setClientLabel] = useState("");
  const [sponsorship, setSponsorship] = useState(EMPTY_SPONSORSHIP);
  const [authorized, setAuthorized] = useState(false);
  const [ownerFile, setOwnerFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const mediaRequest = useRef<AbortController | null>(null);

  useEffect(() => {
    api
      .connections()
      .then((d) => {
        setData(d);
        const first = d.instagram.connections[0] ?? d.youtube.connections[0];
        if (first) setConnId(first.id);
      })
      .catch((e: unknown) => setError(errorMessage(e)));
  }, []);

  const all: Connection[] = data ? [...data.instagram.connections, ...data.youtube.connections] : [];
  const conn = all.find((c) => c.id === connId) ?? null;

  // One media request at a time; switching account aborts it, and a late answer for a
  // previous account is ignored so its posts can never be listed under another account.
  const loadMedia = useCallback((id: string, after: string | null) => {
    mediaRequest.current?.abort();
    const controller = new AbortController();
    mediaRequest.current = controller;
    api
      .media(id, after, controller.signal)
      .then((r) => {
        if (controller.signal.aborted) return;
        setMedia((prev) => {
          if (!after || !prev) return r.items;
          const seen = new Set(prev.map((m) => m.id));
          return [...prev, ...r.items.filter((m) => !seen.has(m.id))];
        });
        setCursor(r.next_cursor);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted || isAbortError(e)) return;
        setMediaError(errorMessage(e));
      })
      .finally(() => {
        if (mediaRequest.current !== controller) return;
        mediaRequest.current = null;
        setLoadingMore(false);
      });
  }, []);

  // Reset the picker whenever the selected account changes.
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  if (connId !== loadedFor) {
    setLoadedFor(connId);
    setMedia(null);
    setCursor(null);
    setSelected(null);
    setMediaError(null);
    setLoadingMore(false);
  }
  useEffect(() => {
    if (connId) loadMedia(connId, null);
    return () => mediaRequest.current?.abort();
  }, [connId, loadMedia]);

  // This route stays mounted (hidden) after navigation: clear the form, including the
  // chosen file, so a later visit never shows a file that will not be sent.
  function resetForm() {
    setOwnerFile(null);
    setLink("");
    setSelected(null);
    setAuthorized(false);
    setSubmitting(false);
    setUploadProgress(null);
  }

  async function submit() {
    if (!conn) return;
    setSubmitting(true);
    setSubmitError(null);
    setUploadProgress(null);
    let createdId: string | null = null;
    try {
      const res = await api.importAnalysis({
        connection_id: conn.id,
        sponsorship: cleanSponsorship(sponsorship),
        language,
        markets,
        ...(briefId ? { brief_id: briefId } : {}),
        attach_owner_file: Boolean(ownerFile),
        ...(agency && clientLabel.trim() ? { client_label: clientLabel.trim() } : {}),
        ...(link.trim() ? { url: link.trim() } : { media_id: selected ?? undefined }),
      });
      createdId = res.id;
      if (ownerFile) {
        setUploadProgress(0);
        await attachOwnerFile(res.id, ownerFile, setUploadProgress);
      }
      resetForm();
      router.push(`/analyses/${res.id}`);
    } catch (e) {
      if (createdId) {
        // The post was imported but the file did not arrive: the review page asks for it again.
        resetForm();
        router.push(`/analyses/${createdId}`);
        return;
      }
      setSubmitError(errorMessage(e));
      setSubmitting(false);
      setUploadProgress(null);
    }
  }

  if (error) return <ErrorNotice title="Could not load connected accounts" message={error} />;
  if (!data) return <Skeleton className="h-80 w-full rounded-[10px]" />;
  if (all.length === 0)
    return (
      <Card>
        <EmptyState
          icon={<Link2 />}
          title="No accounts connected"
          description="Connect an Instagram professional account or a YouTube channel to review posts you have already published or uploaded privately. Only your own content can be reviewed."
          action={
            <ButtonLink href="/connections" variant="primary">
              Connect an account
            </ButtonLink>
          }
        />
      </Card>
    );

  const sponsorError = sponsorshipProblem(sponsorship);
  const isYouTube = conn?.platform === "youtube";
  const missing = !(link.trim() || selected)
    ? "Choose a post or paste a link."
    : !markets.length
      ? "Choose at least one audience market."
    : !authorized
      ? "Confirm that you may have this post reviewed."
      : null;
  const canSubmit = conn && !missing && !sponsorError && !submitting;

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
      <Section
        title="Choose a post"
        actions={
          <Select aria-label="Connected account" value={connId ?? ""} onChange={(e) => setConnId(e.target.value)} className="w-64 max-w-full">
            {all.map((c) => (
              <option key={c.id} value={c.id}>
                {c.platform === "instagram" ? "Instagram" : "YouTube"} · {c.display_name}
              </option>
            ))}
          </Select>
        }
      >
        <div className="space-y-4">
          {isYouTube ? (
            <Callout tone="info" title="YouTube: metadata unless you attach the file">
              YouTube’s API policies do not allow downloading video or audio. Without a file, the title, description, tags
              and hashtags{conn?.captions_enabled ? " and captions" : ""} are checked. Attach the original to review frames,
              speech and audio and cross-check them against the post.
            </Callout>
          ) : (
            <p className="text-[13px] text-ink-3">
              Reels are reviewed in full when Instagram provides the file. It withholds the file for licensed audio, so attach
              the original to review those in full and cross-check them against the post.
            </p>
          )}

          <div className="scroll-thin max-h-[520px] overflow-y-auto pr-1">
            {mediaError && <ErrorNotice title="Could not list posts" message={mediaError} onRetry={() => connId && loadMedia(connId, null)} />}
            {!media && !mediaError && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="aspect-[4/5] w-full rounded-[10px]" />
                ))}
              </div>
            )}
            {media && media.length === 0 && <p className="py-6 text-center text-sm text-ink-3">No videos found on this account.</p>}
            {media && media.length > 0 && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {media.map((m) => {
                  const thumb = safeUrl(m.thumbnail_url);
                  const on = selected === m.id;
                  return (
                    <button
                      key={m.id}
                      type="button"
                      aria-pressed={on}
                      onClick={() => {
                        setSelected(m.id);
                        setLink("");
                      }}
                      className={cn(
                        "group overflow-hidden rounded-[10px] border bg-surface text-left transition-colors duration-[120ms]",
                        on ? "border-accent ring-2 ring-accent" : "border-line hover:border-line-strong",
                      )}
                    >
                      <div className="relative aspect-video bg-surface-3">
                        {thumb ? (
                          // eslint-disable-next-line @next/next/no-img-element -- platform CDN thumbnail, displayed only
                          <img src={thumb} alt="" className="h-full w-full object-cover" loading="lazy" referrerPolicy="no-referrer" />
                        ) : (
                          <ImageOff className="absolute top-1/2 left-1/2 size-5 -translate-x-1/2 -translate-y-1/2 text-ink-3" aria-hidden />
                        )}
                        {on && <CircleCheck className="absolute top-1.5 right-1.5 size-5 rounded-full bg-surface text-accent" aria-hidden />}
                      </div>
                      <div className="space-y-1.5 p-2.5">
                        <div className="line-clamp-2 text-[13px] leading-[18px] font-medium text-ink">{m.title}</div>
                        <div className="flex flex-wrap items-center gap-x-1.5 text-[11px] text-ink-3">
                          {m.published_at && <span>{fmtDate(m.published_at)}</span>}
                          {m.privacy && <span>· {m.privacy}</span>}
                          {m.duration_seconds != null && <span className="tabular">· {Math.round(m.duration_seconds)}s</span>}
                        </div>
                        {!isYouTube && (
                          <Badge tone={MODE_TONE[m.expected_mode] ?? "neutral"} className="h-5 text-[11px]">
                            {MODE_LABEL[m.expected_mode]}
                          </Badge>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
            {cursor && connId && (
              <Button
                className="mt-3 w-full"
                size="sm"
                loading={loadingMore}
                onClick={() => {
                  setMediaError(null);
                  setLoadingMore(true);
                  loadMedia(connId, cursor);
                }}
              >
                Load more
              </Button>
            )}
          </div>

          <Field label="Or paste a link" hint={`The post must belong to ${conn?.display_name ?? "the selected account"}.`}>
            {(p) => (
              <Input
                {...p}
                value={link}
                maxLength={MAX_LINK}
                onChange={(e) => {
                  setLink(e.target.value.slice(0, MAX_LINK));
                  if (e.target.value) setSelected(null);
                }}
                placeholder={isYouTube ? "https://youtube.com/shorts/…" : "https://www.instagram.com/reel/…"}
              />
            )}
          </Field>
        </div>
      </Section>

      <div className="min-w-0 space-y-6">
        <Section title="Review settings">
          <div className="space-y-4">
            <Field
              label="Original video file"
              hint="Optional, and the way to review what is actually in the video. Use your export from YouTube Studio or Instagram’s download tool. The platform copy is not downloaded and songs are not identified. Files longer than 30 minutes are reviewed from the start."
            >
              {(p) => (
                <FilePicker {...p} accept={ACCEPT} disabled={submitting} files={ownerFile ? [ownerFile] : []} onFiles={(f) => setOwnerFile(f[0] ?? null)} />
              )}
            </Field>
            <div className="space-y-1.5">
              <div className="text-[13px] font-medium text-ink">Audience markets</div>
              <MarketPicker value={markets} onChange={setMarkets} />
            </div>
            <div className="space-y-1.5">
              <div className="text-[13px] font-medium text-ink">Spoken language</div>
              <SegmentedControl label="Spoken language" value={language} onChange={setLanguage} options={LANGUAGE_OPTIONS} />
            </div>
            {agency && (
            <Field label="Client or account" hint="Optional. A rights record saved for one client applies only when this label matches.">
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
        <Section title="Sponsorship and brief">
          <div className="space-y-4">
            <SponsorshipFields value={sponsorship} onChange={setSponsorship} />
            <BriefPicker value={briefId} onChange={(id) => setBriefId(id)} />
          </div>
        </Section>
        <Card className="space-y-4 p-5">
          <Checkbox
            checked={authorized}
            onChange={(e) => setAuthorized(e.target.checked)}
            label="I am authorised to have this post reviewed."
            description="The result is automated guidance, not legal advice, and cannot guarantee how a platform will treat the content."
          />
          {submitError && (
            <Callout tone="danger" title="Import failed">
              {submitError}
            </Callout>
          )}
          {uploadProgress !== null && (
            <div className="space-y-2">
              <div className="flex justify-between text-[13px]">
                <span className="font-medium">{uploadProgress < 1 ? "Uploading your file…" : "Checking the video…"}</span>
                {ownerFile && uploadProgress < 1 && (
                  <span className="tabular text-ink-3">
                    {fmtBytes(ownerFile.size * uploadProgress)} of {fmtBytes(ownerFile.size)}
                  </span>
                )}
              </div>
              <Progress value={uploadProgress < 1 ? uploadProgress * 100 : null} label="Upload progress" />
            </div>
          )}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-[13px] text-ink-3">{missing ?? "Ready to import and review."}</p>
            <Button variant="primary" size="lg" leadingIcon={<CircleCheck />} disabled={!canSubmit} loading={submitting} onClick={submit}>
              {submitting ? "Importing…" : "Start review"}
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
