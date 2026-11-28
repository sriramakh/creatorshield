"use client";

import { useSearchParams } from "next/navigation";
import { CircleCheck, Plug, Unplug } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { api, errorMessage, safeUrl, type Connection, type ConnectedPlatform, type ConnectionsResponse } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { PageContainer } from "./shell/AppShell";
import { Badge, Button, Callout, ConfirmDialog, CopyButton, ErrorNotice, PageHeader, Skeleton, useToast } from "./ui";

const CALLBACK_MESSAGES: Record<string, string> = {
  denied: "Access was not granted, so nothing was connected.",
  state: "The sign-in link expired or was already used. Connect again.",
  not_configured: "This platform is not configured on the server yet.",
  failed: "The platform did not complete the sign-in. Try again.",
};

const PLATFORM_INFO: Record<
  ConnectedPlatform,
  { name: string; mark: string; gets: ReactNode; requires: string; setup: string[] }
> = {
  instagram: {
    name: "Instagram",
    mark: "bg-gradient-to-br from-fuchsia-500 via-rose-500 to-amber-400",
    gets: (
      <>
        <strong className="font-semibold text-ink">Full video review</strong> of your own Reels. Instagram withholds the file
        for Reels with licensed audio (including its audio library) or copyright flags; those get a caption and thumbnail review
        instead. Attach the original on the report to review frames, speech and audio and cross-check them against the post.
      </>
    ),
    requires: "An Instagram professional account (Creator or Business).",
    setup: [
      "Create an app at developers.facebook.com and add the “Instagram” product (API setup with Instagram login).",
      "Add the redirect URI below to “Valid OAuth Redirect URIs” (exact match).",
      "Add your Instagram account as an app tester (development mode) and accept the invite in Instagram.",
      "Set INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET on the server and restart it.",
    ],
  },
  youtube: {
    name: "YouTube",
    mark: "bg-[#e62117]",
    gets: (
      <>
        <strong className="font-semibold text-ink">Metadata audit</strong> of your own videos: title, description, tags and
        hashtags, including private drafts. YouTube’s API policies do not allow downloading video or audio, so frames and speech
        are not reviewed. Attach the original on the report for a full review cross-checked against the title, description and
        captions.
      </>
    ),
    requires: "A Google account with a YouTube channel.",
    setup: [
      "In Google Cloud Console, enable “YouTube Data API v3”.",
      "Configure the OAuth consent screen (Testing mode; add yourself as a test user).",
      "Create an OAuth client of type “Web application” with the redirect URI below.",
      "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET on the server and restart it.",
    ],
  },
};

/** Platform sign-in pages are always https. Plain http is accepted only on this machine
 *  (local development and the fake-platform end-to-end test). */
function isSignInAddress(url: string): boolean {
  try {
    const u = new URL(url);
    if (u.protocol === "https:") return true;
    return u.protocol === "http:" && (u.hostname === "127.0.0.1" || u.hostname === "localhost");
  } catch {
    return false;
  }
}

export function ConnectionsPage() {
  const params = useSearchParams();
  const [data, setData] = useState<ConnectionsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .connections()
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e: unknown) => setError(errorMessage(e)));
  }, []);
  useEffect(load, [load]);

  const connected = params.get("connected");
  const callbackError = params.get("error");

  return (
    <PageContainer className="max-w-5xl space-y-6">
      <PageHeader
        title="Connected accounts"
        description="Connect your own accounts to review posts you have already published or uploaded privately. Only official APIs are used, nothing is scraped, and only content owned by the connected account can be reviewed. Disconnecting deletes the stored access and every review imported through that account."
      />

      {connected && (
        <Callout tone="success" title={`${PLATFORM_INFO[connected as ConnectedPlatform]?.name ?? connected} connected`}>
          You can now review your posts from New review → From your account.
        </Callout>
      )}
      {callbackError && (
        <Callout tone="danger" title="The connection was not completed">
          {CALLBACK_MESSAGES[callbackError] ?? CALLBACK_MESSAGES.failed}
        </Callout>
      )}
      {error && <ErrorNotice title="Could not load connected accounts" message={error} onRetry={load} />}
      {data && !data.encryption_configured && (
        <Callout tone="warning" title="Token encryption key missing">
          Set TOKEN_ENCRYPTION_KEY on the server before connecting accounts.
        </Callout>
      )}

      {!data && !error && (
        <div className="grid gap-6 md:grid-cols-2">
          <Skeleton className="h-72 w-full rounded-[10px]" />
          <Skeleton className="h-72 w-full rounded-[10px]" />
        </div>
      )}
      {data && (
        <div className="grid items-start gap-6 md:grid-cols-2">
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
    </PageContainer>
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
      const target = safeUrl(authorization_url);
      if (!target || !isSignInAddress(target)) throw new Error("The server returned an invalid sign-in address.");
      window.location.assign(target);
    } catch (e) {
      setErr(errorMessage(e));
      setBusy(false);
    }
  }

  return (
    <section aria-label={`${info.name} account`} className="flex flex-col rounded-[10px] border border-line bg-surface">
      <div className="flex items-center gap-3 border-b border-line px-5 py-4">
        <span className={`flex size-10 items-center justify-center rounded-[10px] text-sm font-bold text-white ${info.mark}`} aria-hidden>
          {info.name[0]}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[15px] font-semibold">{info.name}</h2>
          <p className="text-[13px] text-ink-3">{info.requires}</p>
        </div>
        {configured ? (
          <Badge tone={connections.length ? "success" : "neutral"} icon={connections.length ? CircleCheck : undefined}>
            {connections.length ? `${connections.length} connected` : "Not connected"}
          </Badge>
        ) : (
          <Badge tone="medium">Setup required</Badge>
        )}
      </div>
      <div className="flex-1 space-y-4 p-5">
        <p className="text-[13px] leading-5 text-ink-2">{info.gets}</p>
        {platform === "youtube" && (
          <p className="text-[13px] text-ink-3">
            Captions:{" "}
            {captionsScope
              ? "requested (needs the broader “manage your YouTube account” permission)."
              : "off. Enable with YOUTUBE_CAPTIONS_SCOPE=true (requests a broader permission)."}
          </p>
        )}
        {connections.length > 0 && (
          <ul className="divide-y divide-line rounded-[8px] border border-line">
            {connections.map((c) => (
              <ConnectedRow key={c.id} c={c} onChange={onChange} />
            ))}
          </ul>
        )}
        {err && (
          <Callout tone="danger" title="Could not start the connection">
            {err}
          </Callout>
        )}
        {!configured && (
          <details className="rounded-[8px] border border-dashed border-line-strong bg-surface-2 p-3 text-[13px] text-ink-2">
            <summary className="cursor-pointer font-semibold text-ink">How to set it up</summary>
            <ol className="mt-2 list-decimal space-y-1 pl-4">
              {info.setup.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
            <div className="mt-3 flex items-center gap-2">
              <span className="text-ink-3">Redirect URI</span>
              <code className="min-w-0 flex-1 truncate rounded-[4px] bg-surface px-1.5 py-0.5 font-mono text-[12px]">{redirectUri}</code>
              <CopyButton value={redirectUri} label="Copy redirect URI" />
            </div>
          </details>
        )}
      </div>
      {configured && (
        <div className="border-t border-line px-5 py-4">
          <Button variant={connections.length ? "secondary" : "primary"} leadingIcon={<Plug />} loading={busy} onClick={connect}>
            {busy ? "Redirecting…" : connections.length ? `Connect another ${info.name} account` : `Connect ${info.name}`}
          </Button>
        </div>
      )}
    </section>
  );
}

function ConnectedRow({ c, onChange }: { c: Connection; onChange: () => void }) {
  const toast = useToast();
  const [confirm, setConfirm] = useState(false);
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5">
      <div className="flex min-w-0 items-center gap-2 text-sm">
        <CircleCheck className="size-4 shrink-0 text-success-fg" aria-hidden />
        <span className="truncate font-semibold">{c.display_name}</span>
        <span className="text-[12px] text-ink-3">since {fmtDate(c.created_at)}</span>
        {c.platform === "youtube" && c.captions_enabled && <Badge>captions</Badge>}
      </div>
      <Button size="sm" variant="ghost" leadingIcon={<Unplug />} onClick={() => setConfirm(true)}>
        Disconnect
      </Button>
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={`Disconnect ${c.display_name}?`}
        description="The stored access is revoked and every review imported through this account is deleted. This cannot be undone."
        confirmLabel="Disconnect"
        onConfirm={async () => {
          const res = await api.disconnect(c.id);
          const deleted = res?.deleted_analyses ? `${res.deleted_analyses} imported review${res.deleted_analyses === 1 ? " was" : "s were"} deleted. ` : "";
          if (res?.revoked === false) {
            const where =
              c.platform === "youtube"
                ? "Remove CreatorShield’s access at myaccount.google.com → Security → Your connections to third-party apps."
                : "Remove the app in Instagram → Settings → Apps and websites.";
            toast({
              tone: "error",
              title: `${c.display_name} was disconnected here, but access was not revoked`,
              description: `${deleted}${res.revoke_error ? `${res.revoke_error} ` : ""}${where}`,
              duration: 15000,
            });
          } else {
            toast({ tone: "success", title: `${c.display_name} disconnected`, description: deleted || undefined });
          }
          onChange();
        }}
      />
    </li>
  );
}
