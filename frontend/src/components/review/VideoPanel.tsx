"use client";

import { ImageOff, VideoOff } from "lucide-react";
import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";
import { api, safeYouTubeId, type Analysis, type Finding } from "@/lib/api";
import { cn } from "@/lib/cn";
import { fmtTime, SEVERITY_ORDER } from "@/lib/format";
import { SOLID } from "../ui";

export interface VideoHandle {
  seek: (t: number) => void;
}

/** The player (file, YouTube embed or thumbnail), a findings timeline and the sampled frames. */
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
    analysis.source === "youtube" && analysis.analysis_mode !== "cross_checked" ? safeYouTubeId(analysis.source_media_id) : null;
  const thumbnailOnly = analysis.analysis_mode === "caption_thumbnail";

  function seekTo(t: number) {
    const clamped = Math.max(0, duration ? Math.min(t, duration) : t);
    if (youtubeId && ytRef.current?.contentWindow) {
      // Official IFrame Player API commands (requires enablejsapi=1).
      const send = (func: string, args: unknown[] = []) =>
        ytRef.current?.contentWindow?.postMessage(JSON.stringify({ event: "command", func, args }), "https://www.youtube-nocookie.com");
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
  const frames = analysis.extraction?.frames ?? [];

  return (
    <div className="space-y-4">
      <div className="flex justify-center overflow-hidden rounded-[8px] bg-[#0b1220]">
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
          frames[0] ? (
            // eslint-disable-next-line @next/next/no-img-element -- stored thumbnail served by the API
            <img src={api.frameUrl(analysis.id, frames[0].id)} alt="Post thumbnail" className="max-h-[520px] w-auto" />
          ) : (
            <Placeholder icon={<ImageOff />} text="Instagram did not provide the video or a thumbnail." />
          )
        ) : analysis.media_deleted ? (
          <Placeholder icon={<VideoOff />} text="The video was deleted under the retention settings. The report is kept." />
        ) : (
          <video
            ref={videoRef}
            src={api.videoUrl(analysis.id)}
            controls
            playsInline
            preload="metadata"
            className="max-h-[min(520px,60vh)] w-auto"
            onTimeUpdate={(e) => setCurrent(e.currentTarget.currentTime)}
          />
        )}
      </div>

      {duration > 0 && (
        <div>
          <div className="mb-1.5 flex justify-between text-[12px] text-ink-3">
            <span className="font-medium text-ink-2">Findings timeline</span>
            <span className="tabular">
              {fmtTime(current)} / {fmtTime(duration)}
            </span>
          </div>
          <div className="relative h-8 rounded-[6px] bg-surface-3" role="group" aria-label="Findings timeline">
            <div className="absolute inset-y-0 left-0 rounded-l-[6px] bg-line-strong/50" style={{ width: `${Math.min(100, (current / duration) * 100)}%` }} />
            {timed.map((f) => {
              const left = (f.start_seconds! / duration) * 100;
              const width = f.end_seconds != null ? Math.max(((f.end_seconds - f.start_seconds!) / duration) * 100, 1.4) : 1.4;
              return (
                <button
                  key={f.id}
                  type="button"
                  title={`${fmtTime(f.start_seconds)} · ${f.title}`}
                  aria-label={`Go to ${f.severity} finding at ${fmtTime(f.start_seconds)}: ${f.title}`}
                  onClick={() => {
                    onMarkerClick(f);
                    seekTo(f.start_seconds!);
                  }}
                  className={cn(
                    "absolute top-2 h-4 rounded-[3px] opacity-85 ring-1 ring-surface transition-[opacity,transform] duration-[120ms] hover:scale-y-125 hover:opacity-100",
                    SOLID[f.severity],
                  )}
                  style={{ left: `${Math.min(left, 98.6)}%`, width: `${Math.min(width, 100 - left)}%` }}
                />
              );
            })}
          </div>
        </div>
      )}

      {!thumbnailOnly && frames.length > 0 && (
        <div>
          <div className="mb-1.5 text-[12px] font-medium text-ink-2">Sampled frames</div>
          <div className="scroll-thin flex gap-1.5 overflow-x-auto pb-1">
            {frames.map((fr) => (
              <button
                key={fr.id}
                type="button"
                onClick={() => {
                  const v = videoRef.current;
                  if (v) v.currentTime = fr.timestamp;
                }}
                className="relative flex-none overflow-hidden rounded-[6px] ring-1 ring-line hover:ring-accent"
                title={`${fr.id} · ${fmtTime(fr.timestamp)} · ${fr.reason.replace("_", " ")}`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element -- served by the API, not optimisable */}
                <img src={api.frameUrl(analysis.id, fr.id)} alt={`Frame ${fr.id} at ${fmtTime(fr.timestamp)}`} className="h-16 w-9 object-cover" loading="lazy" />
                <span className="tabular absolute inset-x-0 bottom-0 bg-black/65 text-center text-[9px] font-medium text-white">{fmtTime(fr.timestamp)}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Placeholder({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex aspect-[9/14] w-full flex-col items-center justify-center gap-2 p-6 text-center text-sm text-white/70 [&_svg]:size-6">
      {icon}
      {text}
    </div>
  );
}
