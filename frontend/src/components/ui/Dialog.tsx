"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Button } from "./Button";
import { Callout } from "./Callout";

/** Modal dialog: focus trap, Esc closes, focus returns to the trigger (Radix). */
export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  size = "md",
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
}) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="anim-fade fixed inset-0 z-50 bg-overlay" />
        <RadixDialog.Content
          className={cn(
            "anim-pop fixed top-1/2 left-1/2 z-50 max-h-[calc(100dvh-32px)] w-[calc(100vw-32px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto",
            "rounded-[14px] border border-line bg-surface shadow-[var(--shadow-dialog)]",
            size === "sm" ? "max-w-md" : size === "md" ? "max-w-lg" : "max-w-2xl",
          )}
          {...(description ? {} : { "aria-describedby": undefined })}
        >
          <div className="px-5 pt-5 pr-14">
            <RadixDialog.Title className="text-[18px] leading-[26px] font-semibold text-ink">{title}</RadixDialog.Title>
            {description && <RadixDialog.Description className="mt-1 text-sm text-ink-2">{description}</RadixDialog.Description>}
          </div>
          {children && <div className="px-5 pt-4">{children}</div>}
          {footer && <div className="mt-5 flex flex-wrap justify-end gap-2 border-t border-line px-5 py-4">{footer}</div>}
          {!footer && <div className="h-5" />}
          {/* Last in DOM order so initial focus lands on the content or Cancel, not on Close. */}
          <RadixDialog.Close
            aria-label="Close"
            className="absolute top-4 right-4 inline-flex size-8 items-center justify-center rounded-[6px] text-ink-3 hover:bg-surface-3 hover:text-ink"
          >
            <X className="size-4" aria-hidden />
          </RadixDialog.Close>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

/**
 * Confirmation for destructive or consequential actions. `onConfirm` may be async; the
 * dialog shows progress, stays open with the server's message on failure, closes on success.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  tone = "danger",
  onConfirm,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  confirmLabel: string;
  tone?: "danger" | "primary";
  onConfirm: () => Promise<void> | void;
  children?: ReactNode;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function change(next: boolean) {
    if (busy) return;
    if (!next) setError(null);
    onOpenChange(next);
  }

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      setBusy(false);
      onOpenChange(false);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={change}
      size="sm"
      title={title}
      description={description}
      footer={
        <>
          <Button variant="secondary" onClick={() => change(false)} disabled={busy}>
            Cancel
          </Button>
          <Button variant={tone === "danger" ? "danger" : "primary"} onClick={confirm} loading={busy}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      {children}
      {error && (
        <Callout tone="danger" title="That did not work" className={children ? "mt-4" : undefined}>
          {error}
        </Callout>
      )}
    </Dialog>
  );
}
