"use client";

import { SponsorshipFields, EMPTY_SPONSORSHIP } from "./SponsorshipFields";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { api, uploadAnalysis, type Language, type Platform } from "@/lib/api";
import { fmtBytes } from "@/lib/format";
import { CheckIcon, UploadIcon } from "./icons";
import { Banner, Card } from "./ui";

const ACCEPT = ".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm";
// Defaults until /api/config answers; the server enforces its own limits either way.
const DEFAULT_LIMITS = { seconds: 1800, mb: 5120 };

function fmtLimitDuration(seconds: number) {
  return seconds >= 60 ? `${+(seconds / 60).toFixed(1)} min` : `${seconds}s`;
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
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [info, setInfo] = useState<LocalInfo | null>(null);
  const [platform, setPlatform] = useState<Platform>("youtube_shorts");
  const [language, setLanguage] = useState<Language>("en");
  const [caption, setCaption] = useState("");
  const [limits, setLimits] = useState(DEFAULT_LIMITS);
  const [hashtags, setHashtags] = useState("");
  const [clientLabel, setClientLabel] = useState("");
  const [sponsorship, setSponsorship] = useState(EMPTY_SPONSORSHIP);
  const [authorized, setAuthorized] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Revoke the last object URL on unmount.
  const previewRef = useRef<string | null>(null);
  useEffect(() => () => {
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
  }, []);

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

  const hashtagCount = hashtags.split(/[\s,]+/).filter((t) => t.replace(/^#/, "")).length;

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
        `File is larger than ${fmtLimitSize(limits.mb)}. Export or compress it at 1080p first ` +
          "(e.g. HandBrake's \"Fast 1080p30\" preset); analysis never uses more than 1080p.",
      );
      return;
    }
    setFile(f);
    setPreviewFor(f);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    pick(e.dataTransfer.files?.[0]);
  }

  const tooLong = info != null && info.duration > limits.seconds + 0.5;
  const canSubmit = file && authorized && !tooLong && progress === null;

  async function submit() {
    if (!file) return;
    setError(null);
    setProgress(0);
    const form = new FormData();
    form.append("file", file);
    form.append("platform", platform);
    form.append("language", language);
    form.append("caption", caption);
    form.append("sponsorship", JSON.stringify({ ...sponsorship, sponsors: sponsorship.sponsors.map(s => s.trim()).filter(Boolean) }));
    form.append("hashtags", hashtags);
    if (clientLabel.trim()) form.append("client_label", clientLabel.trim());
    try {
      const res = await uploadAnalysis(form, setProgress);
      // This route stays mounted (hidden) after navigation; reset it so a
      // later visit to "New analysis" starts clean.
      setFile(null);
      setPreviewFor(null);
      setInfo(null);
      setCaption("");
      setHashtags("");
      setClientLabel("");
      setSponsorship(EMPTY_SPONSORSHIP);
      setAuthorized(false);
      setProgress(null);
      router.push(`/analyses/${res.id}`);
    } catch (e) {
      setError((e as Error).message);
      setProgress(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        {/* Video */}
        <Card className="p-5">
          <h2 className="text-sm font-semibold">Video</h2>
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
              className={`mt-3 flex aspect-[9/12] w-full flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 text-center transition ${
                dragging ? "border-brand-500 bg-brand-50" : "border-slate-200 bg-slate-50 hover:border-slate-300"
              }`}
            >
              <span className="flex h-11 w-11 items-center justify-center rounded-full bg-white text-brand-600 shadow-sm ring-1 ring-slate-200">
                <UploadIcon className="h-5 w-5" />
              </span>
              <span className="mt-3 text-sm font-semibold text-slate-800">Drop a video or click to browse</span>
              <span className="mt-1 text-xs text-slate-500">MP4, MOV or WebM · up to {fmtLimitDuration(limits.seconds)} · max {fmtLimitSize(limits.mb)}</span>
            </button>
          ) : (
            <div className="mt-3 space-y-3">
              <div className="flex justify-center overflow-hidden rounded-xl bg-slate-900">
                {preview && (
                  <video
                    src={preview}
                    controls
                    className="max-h-[420px]"
                    onLoadedMetadata={(e) => {
                      const v = e.currentTarget;
                      setInfo({ duration: v.duration, width: v.videoWidth, height: v.videoHeight });
                    }}
                  />
                )}
              </div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 rounded-lg bg-slate-50 p-3 text-xs">
                <dt className="text-slate-500">File</dt>
                <dd className="truncate text-right font-medium" title={file.name}>{file.name}</dd>
                <dt className="text-slate-500">Size</dt>
                <dd className="text-right font-medium">{fmtBytes(file.size)}</dd>
                <dt className="text-slate-500">Duration</dt>
                <dd className={`text-right font-medium ${tooLong ? "text-red-600" : ""}`}>
                  {info ? `${info.duration.toFixed(1)}s` : "…"}
                </dd>
                <dt className="text-slate-500">Resolution</dt>
                <dd className="text-right font-medium">{info ? `${info.width}×${info.height}` : "…"}</dd>
              </dl>
              {tooLong && <p className="text-xs font-medium text-red-600">This video is longer than {fmtLimitDuration(limits.seconds)}. Trim it before uploading.</p>}
              <button
                type="button"
                onClick={() => {
                  setFile(null);
                  setPreviewFor(null);
                  setInfo(null);
                }}
                className="text-xs font-medium text-brand-700 hover:underline"
                disabled={progress !== null}
              >
                Choose a different file
              </button>
            </div>
          )}
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => pick(e.target.files?.[0])}
          />
        </Card>

        {/* Details */}
        <Card className="space-y-5 p-5">
          <div>
            <h2 className="text-sm font-semibold">Target platform</h2>
            <div className="mt-2 grid grid-cols-2 gap-2">
              {(
                [
                  ["youtube_shorts", "YouTube Shorts", "YouTube Community Guidelines & YPP"],
                  ["instagram_reels", "Instagram Reels", "Meta Community Standards & IG policies"],
                ] as const
              ).map(([value, label, sub]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setPlatform(value)}
                  className={`rounded-lg border px-3 py-2.5 text-left transition ${
                    platform === value ? "border-brand-500 bg-brand-50 ring-1 ring-brand-500" : "border-slate-200 hover:border-slate-300"
                  }`}
                >
                  <div className="text-sm font-semibold">{label}</div>
                  <div className="text-[11px] text-slate-500">{sub}</div>
                </button>
              ))}
            </div>
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

          <div>
            <div className="flex items-baseline justify-between">
              <label htmlFor="caption" className="text-sm font-semibold">Caption / description</label>
              <span className="text-[11px] text-slate-400">{caption.length}/5000</span>
            </div>
            <textarea
              id="caption"
              value={caption}
              onChange={(e) => setCaption(e.target.value.slice(0, 5000))}
              rows={4}
              placeholder="The caption you plan to publish"
              className="mt-2 w-full resize-y rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            />
          </div>

          <div>
            <div className="flex items-baseline justify-between">
              <label htmlFor="hashtags" className="text-sm font-semibold">Hashtags</label>
              <span className="text-[11px] text-slate-400">{hashtagCount} tags</span>
            </div>
            <input
              id="hashtags"
              value={hashtags}
              onChange={(e) => setHashtags(e.target.value)}
              placeholder="#fitness #morningroutine"
              className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            />
          </div>

          <div>
            <label htmlFor="client_label" className="text-sm font-semibold">Client / account (optional)</label>
            <input
              id="client_label"
              value={clientLabel}
              onChange={(e) => setClientLabel(e.target.value.slice(0, 100))}
              placeholder="e.g. FitFuel brand account"
              className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            />
            <p className="mt-1 text-[11px] text-slate-500">
              Groups this video in the catalogue, so footage reused under a different client is flagged.
            </p>
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
              I own this video or am authorized to have it analysed. I understand the result is automated guidance, not legal
              advice, and cannot guarantee how a platform will treat the content.
            </span>
          </label>

          {error && <Banner tone="danger" title="Upload failed">{error}</Banner>}

          {progress !== null ? (
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-medium text-slate-600">
                <span>{progress < 1 ? "Uploading…" : "Validating video…"}</span>
                <span>{Math.round(progress * 100)}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${progress * 100}%` }} />
              </div>
            </div>
          ) : (
            <button
              type="button"
              disabled={!canSubmit}
              onClick={submit}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              <CheckIcon className="h-4 w-4" /> Analyse video
            </button>
          )}
        </Card>
      </div>
    </div>
  );
}
