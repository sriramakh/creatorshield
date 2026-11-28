"use client";

import { CircleCheck, CircleExclamationPoint, Info, X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export type ToastTone = "success" | "error" | "info";

export interface ToastInput {
  tone?: ToastTone;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  /** Milliseconds; default 5000. Errors with an action stay until dismissed. */
  duration?: number;
}

interface ToastItem extends ToastInput {
  id: number;
}

const ToastContext = createContext<((t: ToastInput) => void) | null>(null);

/** Show a toast for the result of an action. */
export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const next = useRef(1);
  const dismiss = useCallback((id: number) => setItems((all) => all.filter((t) => t.id !== id)), []);
  const push = useCallback((t: ToastInput) => {
    const id = next.current++;
    setItems((all) => [...all.slice(-3), { ...t, id }]);
  }, []);
  const value = useMemo(() => push, [push]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        role="region"
        aria-label="Notifications"
        className="pointer-events-none fixed inset-x-0 bottom-[calc(72px+env(safe-area-inset-bottom))] z-[60] flex flex-col items-center gap-2 px-4 md:right-6 md:bottom-6 md:left-auto md:items-end md:px-0"
      >
        {items.map((t) => (
          <ToastView key={t.id} toast={t} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

const ICON = { success: CircleCheck, error: CircleExclamationPoint, info: Info };
const ICON_CLASS = { success: "text-success-fg", error: "text-critical-fg", info: "text-low-fg" };

function ToastView({ toast, onDismiss: dismissById }: { toast: ToastItem; onDismiss: (id: number) => void }) {
  const { id } = toast;
  const onDismiss = useCallback(() => dismissById(id), [dismissById, id]);
  const tone = toast.tone ?? "info";
  const [paused, setPaused] = useState(false);
  const sticky = tone === "error" && Boolean(toast.action);
  useEffect(() => {
    if (paused || sticky) return;
    const t = setTimeout(onDismiss, toast.duration ?? 5000);
    return () => clearTimeout(t);
  }, [paused, sticky, toast.duration, onDismiss]);
  const Icon = ICON[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      className="anim-toast pointer-events-auto flex w-full max-w-sm gap-3 rounded-[10px] border border-line bg-surface p-3 pr-2 shadow-[var(--shadow-pop)]"
    >
      <Icon className={cn("mt-0.5 size-4 shrink-0", ICON_CLASS[tone])} strokeWidth={2} aria-hidden />
      <div className="min-w-0 flex-1 text-sm">
        <div className="font-semibold text-ink">{toast.title}</div>
        {toast.description && <div className="mt-0.5 text-[13px] text-ink-2">{toast.description}</div>}
        {toast.action && (
          <button
            type="button"
            onClick={() => {
              toast.action?.onClick();
              onDismiss();
            }}
            className="mt-1.5 text-[13px] font-semibold text-accent hover:underline"
          >
            {toast.action.label}
          </button>
        )}
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss notification"
        className="inline-flex size-7 shrink-0 items-center justify-center rounded-[6px] text-ink-3 hover:bg-surface-3 hover:text-ink"
      >
        <X className="size-4" aria-hidden />
      </button>
    </div>
  );
}
