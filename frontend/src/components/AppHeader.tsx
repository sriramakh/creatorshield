"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import { ShieldIcon } from "./icons";

const NAV = [
  { href: "/", label: "Analyses" },
  { href: "/connections", label: "Connected accounts" },
  { href: "/rights", label: "Rights ledger" },
  { href: "/catalogue", label: "Catalogue" },
  { href: "/policies", label: "Policy library" },
];

function isActive(href: string, pathname: string | null) {
  if (!pathname) return false;
  if (href === "/") return pathname === "/" || (pathname.startsWith("/analyses/") && pathname !== "/analyses/new");
  return pathname.startsWith(href);
}

function NavLinks({ pathname }: { pathname: string | null }) {
  return (
    <nav className="scroll-thin hidden min-w-0 items-center gap-1 overflow-x-auto sm:flex">
      {NAV.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className={`whitespace-nowrap rounded-md px-2.5 py-2 text-sm font-medium transition lg:px-3 ${
            isActive(item.href, pathname) ? "bg-slate-100 text-slate-900" : "text-slate-600 hover:text-slate-900"
          }`}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}

// usePathname() is request-time data; under Cache Components it must sit inside
// <Suspense> so the header can still be part of the prerendered shell.
function ActiveNavLinks() {
  return <NavLinks pathname={usePathname()} />;
}

export function AppHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-6 lg:gap-8">
          <Link href="/" className="flex flex-none items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
              <ShieldIcon className="h-4.5 w-4.5" />
            </span>
            <span className="text-[15px] font-semibold tracking-tight">
              Creator<span className="text-brand-600">Shield</span> AI
            </span>
          </Link>
          <Suspense fallback={<NavLinks pathname={null} />}>
            <ActiveNavLinks />
          </Suspense>
        </div>
        <Link
          href="/analyses/new"
          className="inline-flex flex-none items-center gap-1.5 whitespace-nowrap rounded-lg bg-brand-600 px-3.5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700"
        >
          <span className="text-base leading-none">+</span> New analysis
        </Link>
      </div>
    </header>
  );
}
