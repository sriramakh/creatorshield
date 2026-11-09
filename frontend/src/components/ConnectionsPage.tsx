"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { api, type Connection, type ConnectedPlatform, type ConnectionsResponse } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { CheckIcon } from "./icons";
import { Banner, Card, Skeleton } from "./ui";

const CALLBACK_MESSAGES: Record<string, string> = {
  denied: "Access was not granted, so nothing was connected.",
  state: "The sign-in link expired or was already used. Please try connecting again.",
  not_configured: "This platform is not configured on the server yet.",
  failed: "The platform did not complete the sign-in. Please try again.",
};

const PLATFORM_INFO: Record<
  ConnectedPlatform,
  { name: string; badge: string; gets: ReactNode; requires: string; setup: string[] }
> = {
  instagram: {
    name: "Instagram",
    badge: "bg-gradient-to-br from-fuchsia-500 via-rose-500 to-amber-400",
    gets: (
      <>
        <strong>Full video analysis</strong> of your own Reels. Instagram withholds the video file for Reels that use
        licensed audio (including its audio library) or are copyright-flagged — those get a{" "}
        <strong>caption + thumbnail</strong> review instead. Attach the original file on the report to review the
        frames, speech and audio, and to cross-check them against the post.
      </>
    ),
    requires: "An Instagram professional account (Creator or Business).",
    setup: [
      "Create an app at developers.facebook.com and add the “Instagram” product (API setup with Instagram login).",
      "Add the redirect URI below to “Valid OAuth Redirect URIs” (exact match).",
      "Add your Instagram account as an app tester (development mode) and accept the invite in Instagram.",
      "Put INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET in backend/.env and restart.",
    ],
  },
  youtube: {
    name: "YouTube",
    badge: "bg-red-600",
    gets: (
      <>
        <strong>Metadata audit</strong> of your own videos — title, description, tags and hashtags, including private
        drafts uploaded for review. YouTube&apos;s API policies don&apos;t allow downloading video or audio, so frames and
        speech are <strong>not</strong> analysed. Attach the original file on the report for a full review
        cross-checked against the video&apos;s title, description and captions.
      </>
    ),
    requires: "A Google account with a YouTube channel.",
    setup: [
      "In Google Cloud Console, enable “YouTube Data API v3”.",
      "Configure the OAuth consent screen (Testing mode; add yourself as a test user).",
      "Create an OAuth client of type “Web application” with the redirect URI below.",
      "Put GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in backend/.env and restart.",
    ],
  },
};

export function ConnectionsPage() {
  const params = useSearchParams();
  const [data, setData] = useState<ConnectionsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.connections().then(setData).catch((e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  const connected = params.get("connected");
  const callbackError = params.get("error");

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Connected accounts</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-500">
          Connect your own accounts to analyse posts you have already published (or uploaded privately). CreatorShield uses
          only the platforms&apos; official APIs, never scrapes, and can only analyse content owned by the connected account.
          Disconnecting deletes the stored access and every analysis imported through that account.
        </p>
      </div>

      {connected && (
        <Banner tone="info" title={`${PLATFORM_INFO[connected as ConnectedPlatform]?.name ?? connected} connected`}>
          You can now analyse your posts from <strong>New analysis → From your account</strong>.
        </Banner>
      )}
      {callbackError && (
        <Banner tone="danger" title="Connection not completed">
          {CALLBACK_MESSAGES[callbackError] ?? CALLBACK_MESSAGES.failed}
        </Banner>
      )}
      {error && <Banner tone="danger" title="Could not load connections">{error}</Banner>}
      {data && !data.encryption_configured && (
        <Banner tone="warning" title="Token encryption key missing">
          Set TOKEN_ENCRYPTION_KEY in backend/.env (scripts/dev.sh generates one) before connecting accounts.
        </Banner>
      )}

      {!data && !error && <Skeleton className="h-64 w-full" />}
      {data && (
        <div className="grid gap-6 md:grid-cols-2">
          {(["instagram", "youtube"] as const).map((p) => (
            <PlatformCard
              key={p}
              platform={p}
              configured={data[p].configured}
              redirectUri={data[p].redirect_uri}
              connections={data[p].connections}
              captionsScope={p === "youtube" ? data.youtube.captions_scope : undefined}
              onChange={load}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function PlatformCard({
  platform,
  configured,
  redirectUri,
  connections,
  captionsScope,
  onChange,
}: {
  platform: ConnectedPlatform;
  configured: boolean;
  redirectUri: string;
  connections: Connection[];
  captionsScope?: boolean;
  onChange: () => void;
}) {
  const info = PLATFORM_INFO[platform];
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function connect() {
    setBusy(true);
    setErr(null);
    try {
      const { authorization_url } = await api.authorize(platform);
      window.location.assign(authorization_url);
    } catch (e) {
      setErr((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <Card className="flex flex-col p-5" label={`${info.name} account`}>
      <div className="flex items-center gap-3">
        <span className={`flex h-10 w-10 items-center justify-center rounded-xl text-sm font-bold text-white ${info.badge}`}>
          {info.name[0]}
        </span>
        <div>
          <h2 className="font-semibold">{info.name}</h2>
          <p className="text-xs text-slate-500">{info.requires}</p>
        </div>
      </div>
      <p className="mt-4 text-[13px] leading-relaxed text-slate-600">{info.gets}</p>
      {platform === "youtube" && (
        <p className="mt-2 text-[12px] text-slate-500">
          Captions: {captionsScope ? "requested (needs the broader “manage your YouTube account” permission)" : "off — enable with YOUTUBE_CAPTIONS_SCOPE=true (requests a broader permission)"}.
        </p>
      )}

      <div className="mt-5 flex-1 space-y-2">
        {connections.map((c) => (
          <ConnectedRow key={c.id} c={c} onChange={onChange} />
        ))}
      </div>

      {err && <p className="mt-3 text-xs text-red-600">{err}</p>}

      {configured ? (
        <button
          type="button"
          onClick={connect}
          disabled={busy}
          className="mt-5 inline-flex items-center justify-center rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:bg-slate-300"
        >
          {busy ? "Redirecting…" : connections.length ? `Connect another ${info.name} account` : `Connect ${info.name}`}
        </button>
      ) : (
        <details className="mt-5 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3 text-[12px] text-slate-600">
          <summary className="cursor-pointer font-semibold text-slate-800">Setup required — show steps</summary>
          <ol className="mt-2 list-decimal space-y-1 pl-4">
            {info.setup.map((s) => <li key={s}>{s}</li>)}
          </ol>
          <div className="mt-2">
            Redirect URI: <code className="break-all rounded bg-white px-1 py-0.5 font-mono text-[11px]">{redirectUri}</code>
          </div>
        </details>
      )}
    </Card>
  );
}

function ConnectedRow({ c, onChange }: { c: Connection; onChange: () => void }) {
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-emerald-50 px-3 py-2">
      <div className="flex items-center gap-2 text-sm">
        <CheckIcon className="h-4 w-4 text-emerald-600" />
        <span className="font-semibold">{c.display_name}</span>
        <span className="text-[11px] text-slate-500">since {fmtDate(c.created_at)}</span>
        {c.platform === "youtube" && c.captions_enabled && (
          <span className="rounded bg-white px-1.5 text-[10px] font-medium text-slate-600">captions</span>
        )}
      </div>
      {confirm ? (
        <span className="flex items-center gap-1 text-xs">
          <span className="text-red-800">Disconnect and delete its imported analyses?</span>
          <button
            type="button"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              await api.disconnect(c.id).catch(() => {});
              onChange();
            }}
            className="rounded bg-red-600 px-2 py-1 font-semibold text-white hover:bg-red-700"
          >
            Disconnect
          </button>
          <button type="button" onClick={() => setConfirm(false)} className="px-1 text-slate-600">
            Cancel
          </button>
        </span>
      ) : (
        <button type="button" onClick={() => setConfirm(true)} className="text-xs font-medium text-slate-600 hover:text-red-700">
          Disconnect
        </button>
      )}
    </div>
  );
}
