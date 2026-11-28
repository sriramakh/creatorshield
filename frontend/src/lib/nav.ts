import {
  BookOpen,
  BriefcaseBusiness,
  Film,
  LayoutDashboard,
  Link2,
  List,
  Scale,
  ScanText,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavGroup = "Review" | "Library" | "Workspace";

export interface NavItem {
  href: string;
  label: string;
  /** Shorter label for the mobile tab bar. */
  short?: string;
  icon: LucideIcon;
  group: NavGroup;
  /** Extra path prefixes that mark this item active (e.g. review detail pages). */
  match?: (pathname: string) => boolean;
  /** Position in the mobile bottom bar (the "New" button sits in the middle). */
  mobile?: 1 | 2 | 3;
  /** Words the command palette also matches. */
  keywords?: string;
}

export const NEW_REVIEW_HREF = "/analyses/new";

/** Every destination in the app shell. Adding a page is one line here. */
export const NAV: NavItem[] = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard, group: "Review", mobile: 1, keywords: "dashboard home insights" },
  {
    href: "/reviews",
    label: "Reviews",
    icon: List,
    group: "Review",
    mobile: 2,
    keywords: "analyses history table",
    match: (p) => p === "/reviews" || (p.startsWith("/analyses/") && p !== NEW_REVIEW_HREF),
  },
  { href: "/check", label: "Caption check", short: "Check", icon: ScanText, group: "Review", mobile: 3, keywords: "caption disclosure quick instant" },
  { href: "/briefs", label: "Brand briefs", icon: BriefcaseBusiness, group: "Library", keywords: "sponsor brief requirements" },
  { href: "/rights", label: "Rights ledger", icon: Scale, group: "Library", keywords: "licences permissions brand deals" },
  { href: "/catalogue", label: "Catalogue", icon: Film, group: "Library", keywords: "fingerprints reposts past posts" },
  { href: "/policies", label: "Policy library", icon: BookOpen, group: "Library", keywords: "rules citations regulators" },
  { href: "/connections", label: "Connected accounts", icon: Link2, group: "Workspace", keywords: "instagram youtube oauth" },
  { href: "/settings", label: "Settings", icon: Settings, group: "Workspace", keywords: "preferences markets mode theme agency creator" },
];

export const NAV_GROUPS: NavGroup[] = ["Review", "Library", "Workspace"];

export function isNavActive(item: NavItem, pathname: string | null): boolean {
  if (!pathname) return false;
  return item.match ? item.match(pathname) : pathname === item.href || pathname.startsWith(`${item.href}/`);
}

/** Breadcrumb trail for a pathname: section, then the page. */
export function breadcrumbsFor(pathname: string | null): { href?: string; label: string }[] {
  if (!pathname) return [];
  if (pathname === NEW_REVIEW_HREF) return [{ href: "/reviews", label: "Reviews" }, { label: "New review" }];
  if (pathname.startsWith("/analyses/")) return [{ href: "/reviews", label: "Reviews" }, { label: "Review" }];
  const item = NAV.find((n) => isNavActive(n, pathname));
  return item ? [{ label: item.label }] : [];
}
