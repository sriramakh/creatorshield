"use client";

import * as RadixTabs from "@radix-ui/react-tabs";
import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/cn";

/** Tabs with roving focus and arrow keys (Radix). */
export const Tabs = RadixTabs.Root;

export function TabsList({ className, ...rest }: ComponentProps<typeof RadixTabs.List>) {
  return (
    <RadixTabs.List
      className={cn("scroll-thin flex gap-1 overflow-x-auto overflow-y-hidden shadow-[inset_0_-1px_0_var(--line)]", className)}
      {...rest}
    />
  );
}

export function TabsTrigger({
  className,
  count,
  children,
  ...rest
}: ComponentProps<typeof RadixTabs.Trigger> & { count?: number; children: ReactNode }) {
  return (
    <RadixTabs.Trigger
      className={cn(
        "relative inline-flex h-10 shrink-0 items-center gap-2 px-3 text-sm font-medium whitespace-nowrap text-ink-3",
        "transition-colors duration-[120ms] hover:text-ink data-[state=active]:text-ink data-[state=active]:shadow-[inset_0_-2px_0_var(--accent)]",
        "focus-visible:outline-offset-[-2px]",
        className,
      )}
      {...rest}
    >
      {children}
      {count != null && (
        <span className="tabular rounded-full bg-surface-3 px-1.5 text-[11px] leading-4 font-semibold text-ink-2">{count}</span>
      )}
    </RadixTabs.Trigger>
  );
}

export function TabsContent({ className, ...rest }: ComponentProps<typeof RadixTabs.Content>) {
  return <RadixTabs.Content className={cn("pt-5 focus-visible:outline-offset-4", className)} {...rest} />;
}
