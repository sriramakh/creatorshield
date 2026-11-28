"use client";

import * as RadixPopover from "@radix-ui/react-popover";
import type { ComponentProps } from "react";
import { cn } from "@/lib/cn";

export const Popover = RadixPopover.Root;
export const PopoverTrigger = RadixPopover.Trigger;
export const PopoverClose = RadixPopover.Close;

export function PopoverContent({ className, align = "start", ...rest }: ComponentProps<typeof RadixPopover.Content>) {
  return (
    <RadixPopover.Portal>
      <RadixPopover.Content
        align={align}
        sideOffset={8}
        collisionPadding={12}
        className={cn(
          "anim-pop z-50 w-80 max-w-[calc(100vw-24px)] rounded-[10px] border border-line bg-surface p-4 text-sm text-ink shadow-[var(--shadow-pop)]",
          className,
        )}
        {...rest}
      />
    </RadixPopover.Portal>
  );
}
