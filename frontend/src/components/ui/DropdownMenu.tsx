"use client";

import * as Menu from "@radix-ui/react-dropdown-menu";
import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/cn";

export const DropdownMenu = Menu.Root;
export const DropdownMenuTrigger = Menu.Trigger;

export function DropdownMenuContent({ className, align = "end", ...rest }: ComponentProps<typeof Menu.Content>) {
  return (
    <Menu.Portal>
      <Menu.Content
        align={align}
        sideOffset={6}
        collisionPadding={8}
        className={cn(
          "anim-pop z-50 min-w-52 rounded-[10px] border border-line bg-surface p-1 shadow-[var(--shadow-pop)]",
          className,
        )}
        {...rest}
      />
    </Menu.Portal>
  );
}

const ITEM =
  "flex h-8 w-full cursor-default items-center gap-2.5 rounded-[6px] px-2 text-sm text-ink outline-none select-none " +
  "data-[highlighted]:bg-surface-3 data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&_svg]:size-4 [&_svg]:text-ink-3";

export function DropdownMenuItem({
  icon,
  tone,
  className,
  children,
  ...rest
}: ComponentProps<typeof Menu.Item> & { icon?: ReactNode; tone?: "danger" }) {
  return (
    <Menu.Item className={cn(ITEM, tone === "danger" && "text-critical-fg [&_svg]:text-critical-fg", className)} {...rest}>
      {icon}
      {children}
    </Menu.Item>
  );
}

/** A menu item that is a link (download, new tab). */
export function DropdownMenuLink({
  icon,
  href,
  children,
  external,
  download,
}: {
  icon?: ReactNode;
  href: string;
  children: ReactNode;
  external?: boolean;
  download?: boolean;
}) {
  return (
    <Menu.Item asChild className={ITEM}>
      <a href={href} {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})} {...(download ? { download: "" } : {})}>
        {icon}
        {children}
      </a>
    </Menu.Item>
  );
}

export function DropdownMenuSeparator() {
  return <Menu.Separator className="my-1 h-px bg-line" />;
}

export function DropdownMenuLabel({ children }: { children: ReactNode }) {
  return (
    <Menu.Label className="px-2 pt-1.5 pb-1 text-[11px] leading-4 font-semibold tracking-[0.06em] text-ink-3 uppercase">
      {children}
    </Menu.Label>
  );
}
