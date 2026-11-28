"use client";

import { useSyncExternalStore } from "react";
import { SIDEBAR_KEY, THEME_KEY } from "./theme-script";

export type ThemeChoice = "light" | "dark" | "system";
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((l) => l());

function readChoice(): ThemeChoice {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

function systemDark() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyTheme(choice: ThemeChoice) {
  const dark = choice === "dark" || (choice === "system" && systemDark());
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

export function setTheme(choice: ThemeChoice) {
  try {
    if (choice === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, choice);
  } catch {
    /* storage unavailable: the choice lasts for this page only */
  }
  applyTheme(choice);
  notify();
}

export function toggleTheme() {
  setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const onSystem = () => {
    if (readChoice() === "system") applyTheme("system");
    listener();
  };
  media.addEventListener("change", onSystem);
  return () => {
    listeners.delete(listener);
    media.removeEventListener("change", onSystem);
  };
}

/** The stored choice ("system" when none). */
export function useThemeChoice(): ThemeChoice {
  return useSyncExternalStore(subscribe, readChoice, () => "system");
}

/** The theme actually shown. */
export function useResolvedTheme(): "light" | "dark" {
  return useSyncExternalStore(
    subscribe,
    () => (document.documentElement.dataset.theme === "dark" ? "dark" : "light"),
    () => "light",
  );
}

// ---------------------------------------------------------------- sidebar width

export function useSidebarCollapsed(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => document.documentElement.dataset.sidebar === "collapsed",
    () => false,
  );
}

export function setSidebarCollapsed(collapsed: boolean) {
  document.documentElement.dataset.sidebar = collapsed ? "collapsed" : "expanded";
  try {
    localStorage.setItem(SIDEBAR_KEY, collapsed ? "collapsed" : "expanded");
  } catch {
    /* not persisted */
  }
  notify();
}
