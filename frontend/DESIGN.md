# CreatorShield design system

The bar: this should read as a product from a company with a large, permanent design team.
Calm, exact, dense where it helps, never decorative. Every screen answers "what do I do next?"
in one glance. Nothing here is a mock-up; every control works.

## Principles

1. **Verdict first.** A creator wants one answer: can I post this? Lead with the verdict,
   then the reasons, then the evidence. Never make someone read a table to learn the outcome.
2. **Quiet surface, loud signal.** Neutral canvas, one accent, colour reserved for status.
   If a screen has more than one saturated element competing, remove one.
3. **Status is never colour alone.** Every severity/verdict carries an icon and a word.
4. **Honest by construction.** Mock mode, limited analysis modes, "cannot check" items and
   heuristic scores are stated plainly, close to the number they qualify, without alarm.
5. **Fast hands.** Keyboard reachable everywhere, command palette, predictable focus order.
6. **Works on a phone.** Creators review on mobile. Every page is usable at 360 px.

## Tokens

Defined as CSS custom properties in `src/app/globals.css`, exposed to Tailwind 4 through
`@theme inline`. Components use semantic tokens only (`bg-surface`, `text-muted`,
`border-line`), never raw palette values. Light is the default; dark is set with
`data-theme="dark"` on `<html>` (user choice persisted, falls back to `prefers-color-scheme`).

| Token | Light | Dark | Use |
|---|---|---|---|
| `--canvas` | `#F5F6F8` | `#0A0D12` | Page background |
| `--surface` | `#FFFFFF` | `#11151C` | Cards, panels, sidebar |
| `--surface-2` | `#F9FAFB` | `#161B24` | Table headers, insets, hover |
| `--surface-3` | `#EEF0F3` | `#1D2330` | Pressed, selected rows, tracks |
| `--line` | `#E3E6EB` | `#232A36` | Default borders, dividers |
| `--line-strong` | `#CBD0D8` | `#343D4D` | Input borders, emphasised dividers |
| `--ink` | `#0B1220` | `#F2F4F8` | Primary text |
| `--ink-2` | `#3D4757` | `#C3CAD6` | Secondary text |
| `--ink-3` | `#5F6B7E` | `#8B95A7` | Tertiary text, placeholders (AA on every surface; light was `#667085`, 4.36:1 on `surface-3`) |
| `--accent` | `#1F4FD8` | `#6E9BFF` | Primary actions, links, focus, selection |
| `--accent-hover` | `#173FB4` | `#8DB1FF` | |
| `--accent-soft` | `#EAF0FF` | `#162445` | Selected backgrounds, accent chips |
| `--on-accent` | `#FFFFFF` | `#0A0D12` | Text on accent |
| `--focus` | `#1F4FD8` | `#8DB1FF` | 2 px focus ring, 2 px offset |

Status scales, each with `-fg` (text/icon), `-bg` (soft fill), `-line` (border), `-solid` (dot, bar):

| Scale | Light fg / bg / line / solid | Meaning |
|---|---|---|
| `critical` | `#A8071A` / `#FDECEC` / `#F5B8B8` / `#D92D20` | Critical severity, blocked |
| `high` | `#B54708` / `#FEF0E6` / `#F9C9A4` / `#EF6820` | High severity |
| `medium` | `#8A5A00` / `#FEF7DC` / `#F3D98A` / `#EAAA08` | Medium severity, warnings |
| `low` | `#175CD3` / `#EAF2FF` / `#B9D2FB` / `#2E90FA` | Low severity |
| `info` | `#475467` / `#F2F4F7` / `#D5D9E0` / `#667085` | Informational |
| `success` | `#067647` / `#E7F6EE` / `#ABDFC5` / `#17B26A` | Ready, passed, covered |

Dark values are the same hues re-balanced for a dark surface (fg lightened to AA, bg at ~14 % alpha).
The exact dark values live in `src/app/globals.css`. `node scripts/contrast.mjs` checks every text/background pair
in both themes (and prints the solid fills, which only ever accompany an icon and a word); run it after changing a token.
All text/background pairs meet WCAG AA (4.5:1 body, 3:1 large text and UI glyphs) in both themes.

**Type.** Geist Sans / Geist Mono. Scale (size/line-height/weight):
`display 30/36/650`, `h1 24/32/650`, `h2 18/26/600`, `h3 15/22/600`, `body 14/22/400`,
`small 13/20/400`, `caption 12/16/500`, `overline 11/16/600 uppercase +0.06em`.
Numbers in tables and KPIs use `font-variant-numeric: tabular-nums`. Max line length 72ch for prose.

**Space.** 4 px base: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64. Page gutters 24 (desktop) / 16 (mobile).
**Radius.** 6 (controls, chips), 10 (cards, panels), 14 (dialogs), full (pills, avatars).
**Elevation.** Borders do the work. Shadows only for things that float:
`pop: 0 4px 16px rgb(11 18 32 / .08), 0 1px 2px rgb(11 18 32 / .06)`; dialogs one step stronger.
**Motion.** 120 ms for hover/press, 180 ms for enter/exit, `cubic-bezier(.2,.7,.2,1)`.
Nothing loops except progress. All motion off under `prefers-reduced-motion`.

## Components (`src/components/ui/`)

One file per primitive, all typed, all with visible focus, disabled and loading states.

- `Button` — variants `primary | secondary | ghost | danger | link`, sizes `sm (28) | md (36) | lg (44)`,
  `loading`, leading/trailing icon. One primary button per view.
- `IconButton` — always has `aria-label` and a tooltip.
- `Input`, `Textarea` (with counter), `Select`, `Checkbox`, `Switch`, `Field` (label, hint, error, required).
- `SegmentedControl`, `Tabs` (roving focus, arrow keys), `ChipGroup` (multi-select chips).
- `Badge` (neutral + status scales), `SeverityBadge`, `VerdictBadge`, `StatusDot`.
- `Card`, `Section` (titled card with actions), `StatTile` (label, value, delta, sparkline).
- `DataTable` — sticky header, sortable columns, row hover, row link, empty and loading rows,
  collapses to stacked cards under 720 px.
- `Callout` — `info | success | warning | danger`, optional action; replaces ad-hoc banners.
- `EmptyState` — icon, title, one sentence, primary action.
- `Skeleton` — matches the final layout to avoid shift.
- `Dialog` / `ConfirmDialog` — focus trap, Esc to close, returns focus. Destructive actions always confirm.
- `Drawer` — right-side panel for create/edit forms.
- `DropdownMenu`, `Tooltip`, `Popover`.
- `Toast` — success/error/info, auto-dismiss 5 s, `role="status"`/`"alert"`, action slot.
- `Progress` (determinate + indeterminate), `Stepper`, `Kbd`, `CopyButton`, `Breadcrumbs`, `PageHeader`.
- `CommandPalette` — `Ctrl/⌘ K`: navigate, start a review, open recent reviews, toggle theme.

Icons: `lucide-react`, 16 px in controls, 20 px in navigation, stroke 1.75. No emoji as icons.
Accessible primitives (dialog, menu, tooltip, tabs, popover) may use Radix UI.

## App shell

- **Sidebar** (240 px, collapsible to 64 px, state persisted). Product mark at top, grouped navigation:
  - *Review*: Overview, Reviews, Caption check
  - *Library*: Brand briefs, Rights ledger, Catalogue, Policy library
  - *Workspace*: Connected accounts, Settings
  Bottom: system status (AI provider, mock mode, retention), theme toggle, help/shortcuts.
- **Top bar** (56 px): breadcrumbs, command palette trigger, primary action "New review".
- **Mobile** (< 768 px): top bar with menu sheet, bottom tab bar (Overview, Reviews, New, Check, More).
- Content column max 1280 px; review detail uses the full width.
- Mock mode and missing-AI states are a persistent status chip in the shell with a popover
  explaining them, plus one inline `Callout` on screens where results are affected. Not a
  full-width yellow banner on every page.

## Screens

- **Overview** — greeting, readiness KPIs (stat tiles), trend, top issues, recent reviews, quick
  actions, first-run checklist.
- **Reviews** — filterable, searchable table (status, platform, verdict, client), stacked cards on mobile.
- **New review** — source (upload / from account), platform cards, audience markets, language,
  caption and hashtags with live disclosure feedback, commercial relationship, brand brief, client label
  (agency mode). Upload progress with cancel.
- **Review detail** — verdict banner with checklist; sticky video and timeline; tabs for Findings
  (grouped: Disclosure, Community guidelines, Brand brief, Rights and provenance, Other), Caption fix,
  Transcript and on-screen text, Rights, Details. Actions menu: report, JSON, evidence pack, re-run, delete.
- **Caption check** — editor on the left, live verdict, checklist, findings and a corrected caption on the right.
- **Brand briefs**, **Rights ledger**, **Catalogue**, **Connected accounts**, **Policy library**, **Settings**.
- **Landing page** — same tokens; speaks to creators and agencies; claims match the product.

## Content rules

- Sentence case everywhere. Buttons are verbs ("Start review", "Copy caption").
- Say what happened and what to do next. No "Oops", no exclamation marks, no blame.
- "Review", not "analysis", in the interface. "Risk indicator", never "probability".
- The product never says content is "safe", "approved", "cleared" or "compliant". It says
  "No issues found by these checks" and lists what was not checked.
- The product name lives in one constant (`src/lib/brand.ts`).
