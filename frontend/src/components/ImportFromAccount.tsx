"use client";

import { SponsorshipFields, EMPTY_SPONSORSHIP } from "./SponsorshipFields";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, attachOwnerFile, type Connection, type ConnectionsResponse, type Language, type MediaItem } from "@/lib/api";
import { fmtDate, MODE_LABEL } from "@/lib/format";
import { CheckIcon } from "./icons";
import { Banner, Card, Skeleton } from "./ui";

const MODE_STYLE: Record<string, string> = {
  full_video: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  caption_thumbnail: "bg-amber-50 text-amber-800 ring-amber-200",
  metadata_only: "bg-sky-50 text-sky-800 ring-sky-200",
};

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
  const [language, setLanguage] = useState<Language>("en");
  const [clientLabel, setClientLabel] = useState("");
  const [sponsorship, setSponsorship] = useState(EMPTY_SPONSORSHIP);
  const [authorized, setAuthorized] = useState(false);
  const [ownerFile, setOwnerFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    api
      .connections()
      .then((d) => {
        setData(d);
        const first = d.instagram.connections[0] ?? d.youtube.connections[0];
        if (first) setConnId(first.id);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const all: Connection[] = data ? [...data.instagram.connections, ...data.youtube.connections] : [];
  const conn = all.find((c) => c.id === connId) ?? null;

  const loadMedia = useCallback(
    (id: string, after: string | null) => {
      api
        .media(id, after)
        .then((r) => {
          setMedia((prev) => (after && prev ? [...prev, ...r.items] : r.items));
          setCursor(r.next_cursor);
        })
        .catch((e: Error) => setMediaError(e.message));
    },
    [],
  );

  // Reset the picker whenever the selected account changes.
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  if (connId !== loadedFor) {
    setLoadedFor(connId);
    setMedia(null);
    setCursor(null);
    setSelected(null);
    setMediaError(null);
  }
  useEffect(() => {
    if (connId) loadMedia(connId, null);
  }, [connId, loadMedia]);

  async function submit() {
    if (!conn) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await api.importAnalysis({
        connection_id: conn.id,
        sponsorship: { ...sponsorship, sponsors: sponsorship.sponsors.map(s => s.trim()).filter(Boolean) },
        language,
        attach_owner_file: Boolean(ownerFile),
        ...(clientLabel.trim() ? { client_label: clientLabel.trim() } : {}),
        ...(link.trim() ? { url: link.trim() } : { media_id: selected ?? undefined }),
      });
      if (ownerFile) {
        try {
          await attachOwnerFile(res.id, ownerFile, () => {});
        } catch (e) {
          setOwnerFile(null);
          setSubmitting(false);
          router.push(`/analyses/${res.id}`);
          throw e;
        }
      }
      setOwnerFile(null);
      setLink("");
      setSelected(null);
      setAuthorized(false);
      setSubmitting(false);
      router.push(`/analyses/${res.id}`);
    } catch (e) {
      setSubmitError((e as Error).message);
      setSubmitting(false);
    }
  }

  if (error) return <Banner tone="danger" title="Could not load connected accounts">{error}</Banner>;
  if (!data) return <Skeleton className="h-64 w-full" />;
  if (all.length === 0)
    return (
      <Card className="flex flex-col items-center px-6 py-14 text-center">
        <h2 className="text-base font-semibold">No accounts connected</h2>
        <p className="mt-1 max-w-md text-sm text-slate-500">
          Connect your Instagram professional account or YouTube channel to analyse posts you&apos;ve already published or
          uploaded privately. Only your own content can be analysed.
        </p>
        <Link href="/connections" className="mt-5 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700">
          Connect an account
        </Link>
      </Card>
    );

  const canSubmit = conn && authorized && (link.trim() || selected) && !submitting;
  const isYouTube = conn?.platform === "youtube";

  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">Choose a post</h2>
          <select
            aria-label="Connected account"
            value={connId ?? ""}
            onChange={(e) => setConnId(e.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm"
          >
            {all.map((c) => (
              <option key={c.id} value={c.id}>
                {c.platform === "instagram" ? "Instagram" : "YouTube"} · {c.display_name}
              </option>
            ))}
          </select>
        </div>

        {isYouTube ? (
          <Banner tone="info" title="YouTube: metadata unless you attach the file">
            YouTube&apos;s API policies don&apos;t allow downloading video or audio. Without a file, the title, description, tags
            and hashtags{conn?.captions_enabled ? " and captions" : ""} are checked. Attach the original below to review
            frames, speech and audio, and to cross-check them against the post.
          </Banner>
        ) : (
          <p className="mt-2 text-[12px] text-slate-500">
            Reels are analysed in full when Instagram provides the file. It withholds the file for licensed audio — attach
            the original below so those Reels are still reviewed in full and cross-checked against the post.
          </p>
        )}

        <div className="scroll-thin mt-4 max-h-[460px] overflow-y-auto pr-1">
          {mediaError && <p className="text-sm text-red-600">{mediaError}</p>}
          {!media && !mediaError && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {[0, 1, 2].map((i) => <Skeleton key={i} className="aspect-[9/12] w-full" />)}
            </div>
          )}
          {media && media.length === 0 && <p className="text-sm text-slate-500">No videos found on this account.</p>}
          {media && media.length > 0 && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {media.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => {
                    setSelected(m.id);
                    setLink("");
                  }}
                  className={`group overflow-hidden rounded-lg border text-left transition ${
                    selected === m.id ? "border-brand-500 ring-2 ring-brand-500" : "border-slate-200 hover:border-slate-300"
                  }`}
                >
                  <div className="relative aspect-video bg-slate-100">
                    {m.thumbnail_url && (
                      // eslint-disable-next-line @next/next/no-img-element -- platform CDN thumbnail, displayed only
                      <img src={m.thumbnail_url} alt="" className="h-full w-full object-cover" loading="lazy" referrerPolicy="no-referrer" />
                    )}
                    {selected === m.id && (
                      <span className="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-brand-600 text-white">
                        <CheckIcon className="h-3 w-3" />
                      </span>
                    )}
                  </div>
                  <div className="space-y-1 p-2">
                    <div className="line-clamp-2 text-[12px] font-medium leading-snug">{m.title}</div>
                    <div className="flex flex-wrap items-center gap-1 text-[10px] text-slate-500">
                      {m.published_at && <span>{fmtDate(m.published_at)}</span>}
                      {m.privacy && <span className="rounded bg-slate-100 px-1">{m.privacy}</span>}
                      {m.duration_seconds != null && <span>{Math.round(m.duration_seconds)}s</span>}
                    </div>
                    {!isYouTube && (
                      <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ring-1 ${MODE_STYLE[m.expected_mode]}`}>
                        {MODE_LABEL[m.expected_mode]}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
          {cursor && connId && (
            <button
              type="button"
              onClick={() => {
                setMediaError(null);
                loadMedia(connId, cursor);
              }}
              className="mt-3 w-full rounded-lg border border-slate-200 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
            >
              Load more
            </button>
          )}
        </div>
      </Card>

      <Card className="space-y-5 p-5">
        <div>
          <label htmlFor="post-link" className="text-sm font-semibold">…or paste a link</label>
          <input
            id="post-link"
            value={link}
            onChange={(e) => {
              setLink(e.target.value);
              if (e.target.value) setSelected(null);
            }}
            placeholder={isYouTube ? "https://youtube.com/shorts/…" : "https://www.instagram.com/reel/…"}
            className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
          />
          <p className="mt-1 text-[11px] text-slate-500">The post must belong to {conn?.display_name}.</p>
        </div>

        <div>
          <label htmlFor="owner-file" className="text-sm font-semibold">Original video file</label>
          <input
            id="owner-file"
            type="file"
            accept=".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm"
            onChange={(e) => setOwnerFile(e.target.files?.[0] ?? null)}
            className="mt-2 block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border file:border-slate-200 file:bg-white file:px-3 file:py-1.5 file:text-sm file:font-medium"
          />
          <p className="mt-1 text-[11px] text-slate-500">
            Optional, and the way to review what is actually in the video. Use your export from YouTube Studio or
            Instagram&apos;s download-your-information tool. The platform copy is not downloaded, and songs are not identified.
            Files longer than 30 minutes are reviewed from the start.
          </p>
        </div>

        <div>
          <label htmlFor="import-client-label" className="text-sm font-semibold">
            Client / account (optional)
          </label>
          <input
            id="import-client-label"
            value={clientLabel}
            onChange={(e) => setClientLabel(e.target.value.slice(0, 100))}
            placeholder="e.g. FitFuel brand account"
            className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
          />
          <p className="mt-1 text-[11px] text-slate-500">
            Groups this post in the catalogue. A rights record saved for one client applies only when this label
            matches.
          </p>
        </div>

        <div>
          <h2 className="text-sm font-semibold">Spoken language</h2>
          <div className="mt-2 inline-flex rounded-lg bg-slate-100 p-1">
            {(
              [
                ["en", "English"],
                ["hi", "Hindi"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setLanguage(value)}
                className={`rounded-md px-4 py-1.5 text-sm font-medium transition ${
                  language === value ? "bg-white text-slate-900 shadow-sm" : "text-slate-600"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <SponsorshipFields value={sponsorship} onChange={setSponsorship} />
        <label className="flex cursor-pointer items-start gap-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
          <input
            type="checkbox"
            checked={authorized}
            onChange={(e) => setAuthorized(e.target.checked)}
            className="mt-0.5 h-4 w-4 accent-brand-600"
          />
          <span>
            I am authorized to analyse this post. I understand the result is automated guidance, not legal advice, and cannot
            guarantee how a platform will treat the content.
          </span>
        </label>

        {submitError && <Banner tone="danger" title="Import failed">{submitError}</Banner>}

        <button
          type="button"
          disabled={!canSubmit}
          onClick={submit}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          <CheckIcon className="h-4 w-4" /> {submitting ? "Importing…" : "Analyse post"}
        </button>
        <p className="text-[11px] text-slate-500">
          Manage accounts on the <Link href="/connections" className="font-medium text-brand-700 hover:underline">Connected accounts</Link> page.
        </p>
      </Card>
    </div>
  );
}
