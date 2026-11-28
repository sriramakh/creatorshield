"use client";

import { useSyncExternalStore } from "react";
import { api, ApiError, errorMessage, type PublicConfig } from "./api";

/** /api/config, fetched once per page load and shared by every component that needs it. */
type State = { config: PublicConfig | null; error: string | null; status: number | null; loaded: boolean };

let state: State = { config: null, error: null, status: null, loaded: false };
let started = false;
const listeners = new Set<() => void>();
const SERVER: State = { config: null, error: null, status: null, loaded: false };

function set(next: State) {
  state = next;
  listeners.forEach((l) => l());
}

function load() {
  api
    .config()
    .then((config) => set({ config, error: null, status: null, loaded: true }))
    .catch((e: unknown) =>
      set({ config: null, error: errorMessage(e), status: e instanceof ApiError ? e.status : 0, loaded: true }),
    );
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (!started) {
    started = true;
    load();
  }
  return () => {
    listeners.delete(listener);
  };
}

export function reloadSystemConfig() {
  load();
}

export function useSystemConfig(): State {
  return useSyncExternalStore(
    subscribe,
    () => state,
    () => SERVER,
  );
}

/** Is AI review limited (mock or no credentials)? Used for the inline Callout on affected screens. */
export function aiLimitation(config: PublicConfig | null): "mock" | "rules_only" | null {
  if (!config) return null;
  if (config.mock_mode) return "mock";
  if (!config.ai_credentials_present) return "rules_only";
  return null;
}
