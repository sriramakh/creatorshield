"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, errorMessage, isAbortError, isRetryable } from "./api";

/** Why polling stopped for good: the resource is gone (404/410) or the login was rejected (401). */
export type PollStop = "gone" | "auth";

export interface PollOptions<T> {
  /** Delay between successful polls. */
  intervalMs: number;
  /** Keep polling after this response? A resource that is not polled is still loaded once. */
  shouldPoll: (data: T) => boolean;
  /** Upper bound for the back-off delay after failures. */
  maxBackoffMs?: number;
}

export interface PolledResource<T> {
  /** Latest successful response. Kept when a later request fails. */
  data: T | null;
  /** Latest failure, cleared by the next success or by dismissError(). */
  error: ApiError | null;
  /** True when the failed request will be retried automatically (with back-off). */
  autoRetry: boolean;
  stopped: PollStop | null;
  /** Fetch now (cancelling any request in flight) and resume polling if needed. */
  reload: () => void;
  dismissError: () => void;
}

/**
 * Load a resource and poll it while `shouldPoll` says so.
 *
 * - never more than one request in flight; responses from superseded requests are ignored
 * - stops on 404/410 ("gone") and 401 ("auth")
 * - exponential back-off with jitter on network errors, 429 and 5xx (honouring Retry-After)
 * - no polling while the tab is hidden; polls straight away when it becomes visible again
 */
export function usePolledResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  options: PollOptions<T>,
): PolledResource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [autoRetry, setAutoRetry] = useState(false);
  const [stopped, setStopped] = useState<PollStop | null>(null);

  const fetcherRef = useRef(fetcher);
  const optionsRef = useRef(options);
  useEffect(() => {
    fetcherRef.current = fetcher;
    optionsRef.current = options;
  });

  const dataRef = useRef<T | null>(null);
  const seqRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dueWhileHiddenRef = useRef(false);
  const failuresRef = useRef(0);
  const stoppedRef = useRef<PollStop | null>(null);
  const runRef = useRef<() => void>(() => {});

  const clearTimer = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
  }, []);

  const schedule = useCallback(
    (delayMs: number) => {
      clearTimer();
      timerRef.current = setTimeout(() => {
        timerRef.current = null;
        if (typeof document !== "undefined" && document.hidden) {
          dueWhileHiddenRef.current = true;
          return;
        }
        runRef.current();
      }, delayMs);
    },
    [clearTimer],
  );

  const run = useCallback(() => {
    if (stoppedRef.current || controllerRef.current) return;
    clearTimer();
    dueWhileHiddenRef.current = false;
    const controller = new AbortController();
    controllerRef.current = controller;
    const id = ++seqRef.current;

    fetcherRef.current(controller.signal).then(
      (value) => {
        if (id !== seqRef.current) return;
        controllerRef.current = null;
        failuresRef.current = 0;
        dataRef.current = value;
        setData(value);
        setError(null);
        setAutoRetry(false);
        if (optionsRef.current.shouldPoll(value)) schedule(optionsRef.current.intervalMs);
      },
      (e: unknown) => {
        if (id !== seqRef.current) return;
        controllerRef.current = null;
        if (isAbortError(e)) return;
        const err = e instanceof ApiError ? e : new ApiError(errorMessage(e), 0);
        if (err.status === 404 || err.status === 410 || err.status === 401) {
          stoppedRef.current = err.status === 401 ? "auth" : "gone";
          setStopped(stoppedRef.current);
          return;
        }
        // Retry by itself only while there is nothing to show yet or the resource is still
        // changing; a failed refresh of a finished resource waits for the user.
        const current = dataRef.current;
        const retry = isRetryable(err) && (current === null || optionsRef.current.shouldPoll(current));
        setError(err);
        setAutoRetry(retry);
        if (!retry) return;
        failuresRef.current += 1;
        const { intervalMs, maxBackoffMs = 60_000 } = optionsRef.current;
        const cap = Math.min(maxBackoffMs, intervalMs * 2 ** failuresRef.current);
        const jittered = cap / 2 + Math.random() * (cap / 2);
        schedule(Math.max(jittered, err.retryAfterMs ?? 0));
      },
    );
  }, [clearTimer, schedule]);

  useEffect(() => {
    runRef.current = run;
  }, [run]);

  useEffect(() => {
    run();
    const onVisibility = () => {
      if (document.hidden) {
        // Pause: a poll that comes due while hidden runs when the tab is shown again.
        if (timerRef.current) {
          clearTimer();
          dueWhileHiddenRef.current = true;
        }
      } else if (dueWhileHiddenRef.current) {
        runRef.current();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      clearTimer();
      seqRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, [run, clearTimer]);

  const reload = useCallback(() => {
    seqRef.current += 1;
    controllerRef.current?.abort();
    controllerRef.current = null;
    failuresRef.current = 0;
    if (stoppedRef.current === "auth") {
      stoppedRef.current = null;
      setStopped(null);
    }
    runRef.current();
  }, []);

  const dismissError = useCallback(() => {
    setError(null);
    setAutoRetry(false);
  }, []);

  return { data, error, autoRetry, stopped, reload, dismissError };
}
