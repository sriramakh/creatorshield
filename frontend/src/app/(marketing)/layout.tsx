import Link from "next/link";
import { BrandMark } from "@/components/shell/BrandMark";
import { ThemeMenu } from "@/components/shell/ThemeMenu";
import { ButtonLink } from "@/components/ui";
import { BRAND } from "@/lib/brand";
import { NEW_REVIEW_HREF } from "@/lib/nav";

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
      <a
        href="#content"
        className="sr-only z-[70] rounded-[6px] bg-surface px-3 py-2 text-sm font-medium text-ink shadow-[var(--shadow-pop)] focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b border-line bg-surface/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1200px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <BrandMark href="/" />
          <nav aria-label="Sections" className="hidden items-center gap-1 md:flex">
            {NAV.map((n) => (
              <a key={n.href} href={n.href} className="rounded-[6px] px-3 py-2 text-sm text-ink-2 transition-colors hover:bg-surface-3 hover:text-ink">
                {n.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-1.5">
            <ThemeMenu side="bottom" />
            <ButtonLink href="/dashboard" variant="ghost" className="max-sm:hidden">
              Open the app
            </ButtonLink>
            <ButtonLink href={NEW_REVIEW_HREF} variant="primary">
              Start a review
            </ButtonLink>
          </div>
        </div>
      </header>
      <main id="content" className="flex-1">
        {children}
      </main>
      <footer className="border-t border-line bg-canvas">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-4 px-4 py-10 text-[13px] text-ink-3 sm:px-6 md:flex-row md:items-center md:justify-between lg:px-8">
          <p className="max-w-2xl leading-5">
            {BRAND.name} gives automated, heuristic guidance only. It is not legal advice, is not affiliated with YouTube, Google,
            Instagram or Meta, and cannot guarantee any platform enforcement outcome.
          </p>
          <div className="flex gap-4">
            <Link href="/policies" className="hover:text-ink">
              Policy library
            </Link>
            <a href="#sources" className="hover:text-ink">
              Sources
            </a>
            <Link href="/dashboard" className="hover:text-ink">
              Open the app
            </Link>
          </div>
        </div>
      </footer>
    </>
  );
}
