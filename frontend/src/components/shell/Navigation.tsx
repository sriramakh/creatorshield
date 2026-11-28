"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import { cn } from "@/lib/cn";
import { NAV, NAV_GROUPS, isNavActive, type NavItem } from "@/lib/nav";
import { Tooltip } from "../ui";

interface ListProps {
  /** "sidebar" hides labels when <html data-sidebar="collapsed"> (CSS, so there is no flash). */
  variant: "sidebar" | "sheet";
  /** Current collapsed state, used only to add tooltips. */
  collapsed: boolean;
  onNavigate?: () => void;
}

function NavLink({ item, active, variant, collapsed, onNavigate }: ListProps & { item: NavItem; active: boolean }) {
  const side = variant === "sidebar";
  const Icon = item.icon;
  const link = (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex h-9 items-center gap-3 rounded-[6px] px-2.5 text-sm transition-colors duration-[120ms]",
        active ? "bg-surface-3 font-medium text-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
        side && "md:collapsed:justify-center md:collapsed:px-0",
      )}
    >
      {active && <span aria-hidden className="absolute top-2 bottom-2 left-0 w-[3px] rounded-r-full bg-accent" />}
      <Icon className={cn("size-5 shrink-0", active ? "text-accent" : "text-ink-3 group-hover:text-ink-2")} strokeWidth={1.75} aria-hidden />
      <span className={cn("truncate", side && "md:collapsed:sr-only")}>{item.label}</span>
    </Link>
  );
  return side && collapsed ? (
    <Tooltip content={item.label} side="right">
      {link}
    </Tooltip>
  ) : (
    link
  );
}

function NavList({ pathname, ...props }: ListProps & { pathname: string | null }) {
  const side = props.variant === "sidebar";
  return (
    <div className="space-y-5">
      {NAV_GROUPS.map((group) => {
        const items = NAV.filter((n) => n.group === group);
        if (!items.length) return null;
        return (
          <div key={group}>
            <div
              className={cn(
                "px-2.5 pb-1.5 text-[11px] leading-4 font-semibold tracking-[0.06em] text-ink-3 uppercase",
                side && "md:collapsed:sr-only",
              )}
            >
              {group}
            </div>
            {side && <div aria-hidden className="mx-3 mb-2 hidden h-px bg-line md:collapsed:block" />}
            <ul className="space-y-0.5">
              {items.map((item) => (
                <li key={item.href}>
                  <NavLink item={item} active={isNavActive(item, pathname)} {...props} />
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

function ActiveNavList(props: ListProps) {
  return <NavList pathname={usePathname()} {...props} />;
}

/** Grouped navigation from src/lib/nav.ts. usePathname is request data, so it sits in Suspense. */
export function Navigation(props: ListProps) {
  return (
    <nav aria-label="Main">
      <Suspense fallback={<NavList pathname={null} {...props} />}>
        <ActiveNavList {...props} />
      </Suspense>
    </nav>
  );
}
