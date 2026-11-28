"use client";

import { useEffect, useRef, useState } from "react";
import { api, errorMessage, isAbortError, type QuickCheckRequest, type QuickCheckResponse } from "./api";

/**
 * Debounced POST /api/quick-check. Each change waits `delay` ms; a newer request aborts the
 * one in flight, so a stale answer never replaces a fresh one. `null` skips checking.
 */
export function useQuickCheck(request: QuickCheckRequest | null, delay = 400) {
  const [result, setResult] = useState<QuickCheckResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const key = request ? JSON.stringify(request) : null;
  const lastKey = useRef<string | null>(null);

  useEffect(() => {
    if (!key) return;
    if (key === lastKey.current) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setPending(true);
      api
        .quickCheck(JSON.parse(key) as QuickCheckRequest, controller.signal)
        .then((r) => {
          lastKey.current = key;
          setResult(r);
          setError(null);
        })
        .catch((e: unknown) => {
          if (controller.signal.aborted || isAbortError(e)) return;
          setError(errorMessage(e));
        })
        .finally(() => {
          if (!controller.signal.aborted) setPending(false);
        });
    }, delay);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [key, delay]);

  return { result: key ? result : null, error: key ? error : null, pending: key ? pending : false };
}
