"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, errorMessage, type MarketInfo, type PlatformInfo, type PublicConfig, type WorkspaceSettings } from "./api";
import { reloadSystemConfig, useSystemConfig } from "./useSystemConfig";

/**
 * Workspace context: /api/config (shared cache) and /api/settings, fetched once per page
 * load. Platform and market pickers, labels and agency mode all read from here.
 */
interface Workspace {
  config: PublicConfig | null;
  settings: WorkspaceSettings | null;
  settingsError: string | null;
  /** True once settings have loaded and the workspace is in agency mode. */
  agency: boolean;
  platforms: PlatformInfo[];
  markets: MarketInfo[];
  platformLabel: (id: string | null | undefined) => string;
  marketLabel: (id: string) => string;
  market: (id: string) => MarketInfo | undefined;
  /** PUT a partial update; resolves with the saved settings (throws ApiError on failure). */
  updateSettings: (patch: Partial<WorkspaceSettings>) => Promise<WorkspaceSettings>;
  reload: () => void;
}

const Ctx = createContext<Workspace | null>(null);

/** Fallback labels while /api/config loads (the API stays the source of truth). */
const FALLBACK_LABEL: Record<string, string> = {
  youtube_shorts: "YouTube Shorts",
  youtube_video: "YouTube video",
  instagram_reels: "Instagram Reels",
};

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { config } = useSystemConfig();
  const [settings, setSettings] = useState<WorkspaceSettings | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);

  const loadSettings = useCallback(() => {
    api
      .settings()
      .then((s) => {
        setSettings(s);
        setSettingsError(null);
      })
      .catch((e: unknown) => setSettingsError(errorMessage(e)));
  }, []);
  useEffect(loadSettings, [loadSettings]);

  const updateSettings = useCallback(async (patch: Partial<WorkspaceSettings>) => {
    const saved = await api.updateSettings(patch);
    setSettings(saved);
    return saved;
  }, []);

  const value = useMemo<Workspace>(() => {
    const platforms = config?.platforms ?? [];
    const markets = config?.markets ?? [];
    return {
      config,
      settings,
      settingsError,
      agency: settings?.mode === "agency",
      platforms,
      markets,
      platformLabel: (id) => (id ? (platforms.find((p) => p.id === id)?.label ?? FALLBACK_LABEL[id] ?? id) : "—"),
      marketLabel: (id) => markets.find((m) => m.id === id)?.label ?? id,
      market: (id) => markets.find((m) => m.id === id),
      updateSettings,
      reload: () => {
        reloadSystemConfig();
        loadSettings();
      },
    };
  }, [config, settings, settingsError, updateSettings, loadSettings]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWorkspace(): Workspace {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useWorkspace must be used inside <WorkspaceProvider>");
  return ctx;
}
