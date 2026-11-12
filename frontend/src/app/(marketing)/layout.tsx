import Link from "next/link";
import { ShieldIcon } from "@/components/icons";

const NAV = [
  { href: "#why", label: "Why it matters" },
  { href: "#stories", label: "Cautionary tales" },
  { href: "#features", label: "Features" },
  { href: "#use-cases", label: "Who it's for" },
  { href: "#faq", label: "FAQ" },
];

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <header className="sticky top-0 z-40 border-b border-white/10 bg-slate-950/80 text-white backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <Link href="/" className="flex flex-none items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500 text-white shadow-lg shadow-indigo-500/40">
              <ShieldIcon className="h-4.5 w-4.5" />
            </span>
            <span className="text-[15px] font-semibold tracking-tight">
              Creator<span className="text-indigo-300">Shield</span> AI
            </span>
          </Link>
          <nav aria-label="Sections" className="hidden items-center gap-1 md:flex">
            {NAV.map((n) => (
              <a key={n.href} href={n.href} className="rounded-md px-3 py-2 text-sm text-slate-300 transition hover:text-white">
                {n.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Link
              href="/dashboard"
              className="hidden rounded-lg px-3 py-2 text-sm font-medium text-slate-300 transition hover:text-white sm:inline-flex"
            >
              Dashboard
            </Link>
            <Link
              href="/analyses/new"
              className="inline-flex items-center rounded-lg bg-white px-3.5 py-2 text-sm font-semibold text-slate-900 transition hover:bg-indigo-100"
            >
              Review a video
            </Link>
          </div>
        </div>
      </header>
      <main className="flex-1">{children}</main>
      <footer className="bg-slate-950 text-slate-400">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-10 text-xs sm:px-6 md:flex-row md:items-center md:justify-between lg:px-8">
          <p className="max-w-2xl leading-relaxed">
            CreatorShield AI provides automated, heuristic guidance only. It is not legal advice, is not affiliated with
            YouTube, Google, Instagram or Meta, and cannot guarantee any platform enforcement outcome.
          </p>
          <div className="flex gap-4">
            <Link href="/policies" className="hover:text-white">
              Policy library
            </Link>
            <a href="#sources" className="hover:text-white">
              Sources
            </a>
            <Link href="/dashboard" className="hover:text-white">
              Dashboard
            </Link>
          </div>
        </div>
      </footer>
    </>
  );
}
