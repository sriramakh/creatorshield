"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/** Right-side panel for create/edit forms (or a left sheet for mobile navigation). */
export function Drawer({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  side = "right",
  titleHidden = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  side?: "left" | "right";
  titleHidden?: boolean;
}) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="anim-fade fixed inset-0 z-50 bg-overlay" />
        <RadixDialog.Content
          className={cn(
            "anim-drawer fixed inset-y-0 z-50 flex w-[min(440px,100vw)] flex-col border-line bg-surface shadow-[var(--shadow-dialog)]",
            side === "right" ? "right-0 border-l" : "left-0 w-[min(300px,85vw)] border-r",
          )}
          {...(description ? {} : { "aria-describedby": undefined })}
        >
          <div className={cn("flex min-h-14 items-start gap-4 border-b border-line py-4 pr-14 pl-5", titleHidden && "border-b-0 pb-0")}>
            <div className={cn("min-w-0", titleHidden && "sr-only")}>
              <RadixDialog.Title className="text-[18px] leading-[26px] font-semibold text-ink">{title}</RadixDialog.Title>
              {description && <RadixDialog.Description className="mt-0.5 text-[13px] text-ink-3">{description}</RadixDialog.Description>}
            </div>
          </div>
          <div className="scroll-thin flex-1 overflow-y-auto px-5 py-5">{children}</div>
          {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-4">{footer}</div>}
          {/* Last in DOM order so initial focus lands on the first field, not on Close. */}
          <RadixDialog.Close
            aria-label="Close"
            className="absolute top-3.5 right-4 inline-flex size-8 items-center justify-center rounded-[6px] text-ink-3 hover:bg-surface-3 hover:text-ink"
          >
            <X className="size-4" aria-hidden />
          </RadixDialog.Close>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
