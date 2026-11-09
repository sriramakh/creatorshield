"use client";

import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";
import { api, type Analysis, type Finding } from "@/lib/api";
import { fmtTime, SEVERITY_ORDER, SEVERITY_STYLE } from "@/lib/format";

export interface VideoHandle {
  seek: (t: number) => void;
}

export function VideoPanel({
  analysis,
  findings,
  onMarkerClick,
  ref,
}: {
  analysis: Analysis;
  findings: Finding[];
  onMarkerClick: (f: Finding) => void;
  ref: Ref<VideoHandle>;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const ytRef = useRef<HTMLIFrameElement>(null);
  const [current, setCurrent] = useState(0);
  const duration = analysis.duration_seconds ?? 0;
  const youtubeId =
    analysis.source === "youtube" && analysis.analysis_mode !== "cross_checked"
      ? analysis.source_media_id
      : null;
  const thumbnailOnly = analysis.analysis_mode === "caption_thumbnail";

  function seekTo(t: number) {
    const clamped = Math.max(0, duration ? Math.min(t, duration) : t);
    if (youtubeId && ytRef.current?.contentWindow) {
      // Official IFrame Player API commands (requires enablejsapi=1).
      const send = (func: string, args: unknown[] = []) =>
        ytRef.current?.contentWindow?.postMessage(JSON.stringify({ event: "command", func, args }), "*");
      send("seekTo", [clamped, true]);
      send("playVideo");
      setCurrent(clamped);
      ytRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
      return;
    }
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = clamped;
    v.play().catch(() => {});
    v.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  useImperativeHandle(ref, () => ({ seek: seekTo }));

  // Routes stay mounted (hidden) after navigation; stop playback when hidden.
  useEffect(() => {
    const v = videoRef.current;
    return () => v?.pause();
  }, []);

  const timed = findings
    .filter((f) => f.start_seconds != null && f.finding_type !== "cannot_check")
    .sort((a, b) => SEVERITY_ORDER.indexOf(b.severity) - SEVERITY_ORDER.indexOf(a.severity));

  return (
    <div className="space-y-3">
      <div className="flex justify-center overflow-hidden rounded-xl bg-slate-950">
        {youtubeId ? (
          <iframe
            ref={ytRef}
            title="YouTube player"
            src={`https://www.youtube-nocookie.com/embed/${youtubeId}?enablejsapi=1&playsinline=1&rel=0`}
            allow="encrypted-media; picture-in-picture"
            allowFullScreen
            className="aspect-[9/14] w-full"
          />
        ) : thumbnailOnly ? (
          analysis.extraction?.frames?.[0] ? (
            // eslint-disable-next-line @next/next/no-img-element -- stored thumbnail served by the API
            <img src={api.frameUrl(analysis.id, analysis.extraction.frames[0].id)} alt="Post thumbnail" className="max-h-[520px] w-auto" />
          ) : (
            <div className="flex aspect-[9/14] w-full items-center justify-center p-6 text-center text-sm text-slate-400">
              Instagram did not provide the video or a thumbnail.
            </div>
          )
        ) : analysis.media_deleted ? (
          <div className="flex aspect-[9/14] w-full items-center justify-center p-6 text-center text-sm text-slate-400">
            Video deleted per retention settings.
          </div>
        ) : (
          <video
            ref={videoRef}
            src={api.videoUrl(analysis.id)}
            controls
            playsInline
            preload="metadata"
            className="max-h-[520px] w-auto"
            onTimeUpdate={(e) => setCurrent(e.currentTarget.currentTime)}
          />
        )}
      </div>

      {duration > 0 && (
        <div>
          <div className="mb-1 flex justify-between text-[11px] font-medium text-slate-500">
            <span>Findings timeline</span>
            <span className="tabular-nums">{fmtTime(current)} / {fmtTime(duration)}</span>
          </div>
          <div className="relative h-7 rounded-md bg-slate-100">
            <div className="absolute inset-y-0 left-0 rounded-l-md bg-slate-200/70" style={{ width: `${(current / duration) * 100}%` }} />
            {timed.map((f) => {
              const left = (f.start_seconds! / duration) * 100;
              const width = f.end_seconds != null ? Math.max(((f.end_seconds - f.start_seconds!) / duration) * 100, 1.2) : 1.2;
              return (
                <button
                  key={f.id}
                  type="button"
                  title={`${fmtTime(f.start_seconds)} · ${f.title}`}
                  onClick={() => {
                    onMarkerClick(f);
                    seekTo(f.start_seconds!);
                  }}
                  className={`absolute top-1.5 h-4 rounded-sm opacity-80 ring-1 ring-white transition hover:opacity-100 ${SEVERITY_STYLE[f.severity].dot}`}
                  style={{ left: `${Math.min(left, 98.8)}%`, width: `${Math.min(width, 100 - left)}%` }}
                />
              );
            })}
          </div>
        </div>
      )}

      {!thumbnailOnly && analysis.extraction?.frames && analysis.extraction.frames.length > 0 && (
        <div>
          <div className="mb-1 text-[11px] font-medium text-slate-500">Sampled frames</div>
          <div className="scroll-thin flex gap-1.5 overflow-x-auto pb-1">
            {analysis.extraction.frames.map((fr) => (
              <button
                key={fr.id}
                type="button"
                onClick={() => {
                  const v = videoRef.current;
                  if (v) v.currentTime = fr.timestamp;
                }}
                className="group relative flex-none overflow-hidden rounded-md ring-1 ring-slate-200 hover:ring-brand-500"
                title={`${fr.id} · ${fmtTime(fr.timestamp)} · ${fr.reason.replace("_", " ")}`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element -- served by the API, not optimisable */}
                <img src={api.frameUrl(analysis.id, fr.id)} alt={`Frame ${fr.id}`} className="h-16 w-9 object-cover" loading="lazy" />
                <span className="absolute inset-x-0 bottom-0 bg-black/60 text-center text-[9px] font-medium text-white">
                  {fmtTime(fr.timestamp)}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
