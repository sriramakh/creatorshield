"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Ellipsis,
  FileText,
  Keyboard,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  BriefcaseBusiness,
  ScanText,
  Search,
} from "lucide-react";
import { Suspense, useCallback, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";
import { api, type AnalysisSummary } from "@/lib/api";
import { BRAND } from "@/lib/brand";
import { cn } from "@/lib/cn";
import { NAV, NEW_REVIEW_HREF, breadcrumbsFor, isNavActive } from "@/lib/nav";
import { setSidebarCollapsed, toggleTheme, useSidebarCollapsed } from "@/lib/theme";
import { AuthNotice } from "../AuthNotice";
import { OnboardingDialog } from "../OnboardingDialog";
import { WorkspaceProvider } from "@/lib/workspace";
import {
  Breadcrumbs,
  ButtonLink,
  CommandPalette,
  Dialog,
  Drawer,
  IconButton,
  Kbd,
  ToastProvider,
  type Command,
} from "../ui";
import { BrandMark } from "./BrandMark";
import { Navigation } from "./Navigation";
import { StatusChip } from "./StatusChip";
import { ThemeMenu } from "./ThemeMenu";

const noopSubscribe = () => () => {};
/** "⌘" on Apple devices, "Ctrl" elsewhere (and during server rendering). */
function useModKey() {
  return useSyncExternalStore(
    noopSubscribe,
    () => (/Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl"),
    () => "Ctrl",
  );
}

function isTyping(target: EventTarget | null) {
  const el = target as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

/** Sidebar, top bar, mobile bars, command palette and toasts around every app page. */
export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const collapsed = useSidebarCollapsed();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [recent, setRecent] = useState<AnalysisSummary[]>([]);

  const openPalette = useCallback(() => {
    setPaletteOpen(true);
    api
      .list()
      .then((rows) => setRecent(rows.slice(0, 8)))
      .catch(() => {});
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (paletteOpen) setPaletteOpen(false);
        else openPalette();
      } else if (e.key === "?" && !isTyping(e.target) && !e.metaKey && !e.ctrlKey) {
        setShortcutsOpen(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [paletteOpen, openPalette]);

  const commands = useMemo<Command[]>(() => {
    const go = (href: string) => () => router.push(href);
    return [
      { id: "new", group: "Actions", label: "Start a new review", icon: <Plus />, keywords: "upload video analyse", onSelect: go(NEW_REVIEW_HREF) },
      { id: "check", group: "Actions", label: "Check a caption", icon: <ScanText />, keywords: "disclosure quick", onSelect: go("/check") },
      { id: "brief", group: "Actions", label: "Add a brand brief", icon: <BriefcaseBusiness />, keywords: "sponsor requirements", onSelect: go("/briefs?new=1") },
      { id: "theme", group: "Actions", label: "Toggle light / dark theme", icon: <Moon />, keywords: "dark mode appearance", onSelect: toggleTheme },
      {
        id: "sidebar",
        group: "Actions",
        label: collapsed ? "Expand sidebar" : "Collapse sidebar",
        icon: collapsed ? <PanelLeftOpen /> : <PanelLeftClose />,
        onSelect: () => setSidebarCollapsed(!collapsed),
      },
      { id: "shortcuts", group: "Actions", label: "Keyboard shortcuts", icon: <Keyboard />, onSelect: () => setShortcutsOpen(true) },
      ...NAV.map((n) => ({
        id: `nav-${n.href}`,
        group: "Go to",
        label: n.label,
        icon: <n.icon />,
        keywords: n.keywords,
        onSelect: go(n.href),
      })),
      ...recent.map((r) => ({
        id: `review-${r.id}`,
        group: "Recent reviews",
        label: r.source_title?.trim() || r.caption?.trim().split("\n")[0] || "Untitled video",
        icon: <FileText />,
        keywords: `${r.client_label ?? ""} ${r.platform}`,
        hint: r.status === "completed" ? undefined : r.status.replace("_", " "),
        onSelect: go(`/analyses/${r.id}`),
      })),
    ];
  }, [router, collapsed, recent]);

  const mod = useModKey();

  return (
    <ToastProvider>
      <WorkspaceProvider>
      <OnboardingDialog />
      <a
        href="#main"
        className="sr-only z-[70] rounded-[6px] bg-surface px-3 py-2 text-sm font-medium text-ink shadow-[var(--shadow-pop)] focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      <div className="flex min-h-dvh">
        {/* Desktop sidebar */}
        <aside
          aria-label="Sidebar"
          className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-line bg-surface transition-[width] duration-[180ms] md:flex collapsed:w-16"
        >
          <div className="flex h-14 items-center justify-between gap-2 px-3 collapsed:justify-center collapsed:px-0">
            <BrandMark className="collapsed:hidden" />
            <span className="hidden collapsed:flex">
              <BrandMark compact />
            </span>
            <IconButton
              size="sm"
              label="Collapse sidebar"
              icon={<PanelLeftClose />}
              onClick={() => setSidebarCollapsed(true)}
              className="collapsed:hidden"
            />
          </div>
          <div className="scroll-thin flex-1 overflow-y-auto px-3 py-3 collapsed:px-2">
            <Navigation variant="sidebar" collapsed={collapsed} />
          </div>
          <div className="space-y-2 border-t border-line p-3 collapsed:px-2">
            <StatusChip className="w-full collapsed:hidden" />
            <div className="hidden justify-center collapsed:flex">
              <StatusChip compact />
            </div>
            <div className="flex items-center gap-1 collapsed:flex-col">
              <ThemeMenu />
              <IconButton size="sm" label="Keyboard shortcuts" icon={<Keyboard />} onClick={() => setShortcutsOpen(true)} className="size-8" />
              <span className="hidden collapsed:inline-flex">
                <IconButton size="sm" label="Expand sidebar" icon={<PanelLeftOpen />} onClick={() => setSidebarCollapsed(false)} className="size-8" />
              </span>
            </div>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-surface/90 px-4 backdrop-blur md:px-6">
            <IconButton label="Open menu" icon={<Menu />} onClick={() => setSheetOpen(true)} className="-ml-2 md:hidden" />
            <BrandMark className="md:hidden" />
            <div className="hidden min-w-0 flex-1 md:block">
              <Suspense fallback={null}>
                <ShellBreadcrumbs />
              </Suspense>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <button
                type="button"
                onClick={openPalette}
                aria-label="Search and commands"
                aria-keyshortcuts="Control+K Meta+K"
                className="hidden h-9 w-60 items-center gap-2 rounded-[6px] border border-line-strong bg-surface px-3 text-sm text-ink-3 hover:border-ink-3 lg:flex"
              >
                <Search className="size-4" aria-hidden />
                <span className="flex-1 text-left">Search or jump to…</span>
                <Kbd>{mod} K</Kbd>
              </button>
              <IconButton label="Search and commands" icon={<Search />} onClick={openPalette} className="lg:hidden" />
              <ButtonLink href={NEW_REVIEW_HREF} variant="primary" leadingIcon={<Plus />} className="max-sm:hidden">
                New review
              </ButtonLink>
            </div>
          </header>

          <main id="main" tabIndex={-1} className="flex-1 px-4 pt-6 pb-28 focus:outline-none md:px-6 md:pt-8 md:pb-12">
            <AuthNotice />
            {children}
          </main>
          <footer className="hidden border-t border-line px-6 py-4 text-[12px] text-ink-3 md:block">
            {BRAND.name} gives automated, heuristic guidance. It is not legal advice, is not affiliated with YouTube, Google,
            Instagram or Meta, and cannot guarantee any platform enforcement outcome.
          </footer>
        </div>
      </div>

      <Suspense fallback={null}>
        <MobileTabBar onMore={() => setSheetOpen(true)} />
      </Suspense>

      <Drawer open={sheetOpen} onOpenChange={setSheetOpen} title="Menu" side="left" titleHidden>
        <div className="-mt-2 mb-5">
          <BrandMark />
        </div>
        <Navigation variant="sheet" collapsed={false} onNavigate={() => setSheetOpen(false)} />
        <div className="mt-6 space-y-3 border-t border-line pt-4">
          <StatusChip className="w-full" />
          <div className="flex items-center gap-2 text-sm text-ink-2">
            <ThemeMenu side="bottom" /> Theme
          </div>
        </div>
      </Drawer>

      <CommandPalette
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
        commands={commands}
        footer={
          <>
            <span className="inline-flex items-center gap-1">
              <Kbd>↑</Kbd>
              <Kbd>↓</Kbd> move
            </span>
            <span className="inline-flex items-center gap-1">
              <Kbd>Enter</Kbd> open
            </span>
            <span className="inline-flex items-center gap-1">
              <Kbd>Esc</Kbd> close
            </span>
          </>
        }
      />

      <Dialog open={shortcutsOpen} onOpenChange={setShortcutsOpen} title="Keyboard shortcuts" size="sm">
        <dl className="divide-y divide-line text-sm">
          {[
            [`${mod} K`, "Search pages, reviews and actions"],
            ["?", "Show keyboard shortcuts"],
            ["Esc", "Close a dialog, menu or panel"],
            ["← →", "Move between tabs and options"],
            ["Tab", "Move to the next control"],
          ].map(([keys, what]) => (
            <div key={keys} className="flex items-center justify-between gap-4 py-2.5">
              <dt className="text-ink-2">{what}</dt>
              <dd>
                <Kbd>{keys}</Kbd>
              </dd>
            </div>
          ))}
        </dl>
      </Dialog>
      </WorkspaceProvider>
    </ToastProvider>
  );
}

function ShellBreadcrumbs() {
  return <Breadcrumbs items={breadcrumbsFor(usePathname())} />;
}

function MobileTabBar({ onMore }: { onMore: () => void }) {
  const pathname = usePathname();
  const items = NAV.filter((n) => n.mobile).sort((a, b) => (a.mobile ?? 0) - (b.mobile ?? 0));
  const left = items.slice(0, 2);
  const right = items.slice(2, 3);
  const tab = (href: string, label: string, Icon: (typeof NAV)[number]["icon"], active: boolean) => (
    <Link
      key={href}
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-medium",
        active ? "text-accent" : "text-ink-3",
      )}
    >
      <Icon className="size-5" strokeWidth={1.75} aria-hidden />
      {label}
    </Link>
  );
  return (
    <nav
      aria-label="Quick navigation"
      className="fixed inset-x-0 bottom-0 z-30 flex h-16 items-stretch border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      {left.map((n) => tab(n.href, n.short ?? n.label, n.icon, isNavActive(n, pathname)))}
      <Link
        href={NEW_REVIEW_HREF}
        aria-current={pathname === NEW_REVIEW_HREF ? "page" : undefined}
        className="flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-medium text-ink"
      >
        <span className="flex size-8 items-center justify-center rounded-full bg-accent text-on-accent">
          <Plus className="size-5" aria-hidden />
        </span>
        New
      </Link>
      {right.map((n) => tab(n.href, n.short ?? n.label, n.icon, isNavActive(n, pathname)))}
      <button
        type="button"
        onClick={onMore}
        className="flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-medium text-ink-3"
      >
        <Ellipsis className="size-5" aria-hidden />
        More
      </button>
    </nav>
  );
}

/** Content width for app pages. Review detail opts into the full width. */
export function PageContainer({ children, wide = false, className }: { children: ReactNode; wide?: boolean; className?: string }) {
  return <div className={cn("mx-auto w-full", wide ? "max-w-[1600px]" : "max-w-[1280px]", className)}>{children}</div>;
}
