import Link from "next/link";
import type { ReactNode } from "react";
import { CASES, FAQ, SCENARIOS, SHIFTS, SOURCE_ORDER, SOURCES, STATS, type SourceId } from "./content";
import {
  ArrowIcon,
  BookIcon,
  BuildingIcon,
  ChartIcon,
  CheckIcon,
  ExternalIcon,
  FilmIcon,
  FingerprintIcon,
  LedgerIcon,
  LinkIcon,
  LockIcon,
  MegaphoneIcon,
  PackageIcon,
  PinIcon,
  ScanIcon,
  TagIcon,
  UsersIcon,
  XIcon,
} from "./icons";
import { ReportPreview } from "./ReportPreview";

function SourceLink({ id, className = "" }: { id: SourceId; className?: string }) {
  const n = SOURCE_ORDER.indexOf(id) + 1;
  return (
    <a
      href={SOURCES[id].url}
      target="_blank"
      rel="noopener noreferrer"
      title={SOURCES[id].label}
      className={`inline-flex items-center gap-0.5 align-super text-[10px] font-semibold text-indigo-500 hover:text-indigo-400 ${className}`}
    >
      [{n}]
    </a>
  );
}

function Eyebrow({ children, dark = false }: { children: ReactNode; dark?: boolean }) {
  return (
    <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${dark ? "text-indigo-300" : "text-indigo-600"}`}>
      {children}
    </p>
  );
}

function PrimaryCta({ children = "Review a video" }: { children?: ReactNode }) {
  return (
    <Link
      href="/analyses/new"
      className="group inline-flex items-center gap-2 rounded-xl bg-indigo-500 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 transition hover:bg-indigo-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-300"
    >
      {children}
      <ArrowIcon className="h-4 w-4 transition group-hover:translate-x-0.5" />
    </Link>
  );
}

// ------------------------------------------------------------------- hero

function Hero() {
  return (
    <section className="relative overflow-hidden bg-slate-950 text-white">
      <div className="landing-grid pointer-events-none absolute inset-0 opacity-40" aria-hidden />
      <div
        className="pointer-events-none absolute -top-40 left-1/2 h-[36rem] w-[60rem] -translate-x-1/2 rounded-full bg-indigo-600/30 blur-3xl"
        aria-hidden
      />
      <div className="pointer-events-none absolute -bottom-48 right-[-10rem] h-[28rem] w-[28rem] rounded-full bg-fuchsia-600/20 blur-3xl" aria-hidden />

      <div className="relative mx-auto grid max-w-7xl items-center gap-14 px-4 pb-20 pt-16 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:px-8 lg:pb-28 lg:pt-24">
        <div className="landing-rise">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-indigo-200">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
            Pre-publication review for Shorts &amp; Reels
          </span>
          <h1 className="mt-6 text-4xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">
            Years to build.
            <br />
            <span className="bg-gradient-to-r from-indigo-300 via-fuchsia-300 to-amber-200 bg-clip-text text-transparent">
              One upload to lose.
            </span>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-300">
            CreatorShield checks every video against the official YouTube, Instagram and ASCI rules — speech, frames,
            on-screen text, music, captions and sponsorship disclosure — and tells you what to fix,{" "}
            <span className="text-white">down to the second</span>, before you post.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <PrimaryCta />
            <a
              href="#stories"
              className="inline-flex items-center gap-2 rounded-xl border border-white/15 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/5"
            >
              See what it would have caught
            </a>
          </div>
          <ul className="mt-8 grid gap-2 text-sm text-slate-400 sm:grid-cols-2">
            {[
              "Cites only verified official policy pages",
              "English & हिंदी, up to 30 minutes",
              "No scraping, official APIs only",
              "Auto-deletes your video in 72 hours",
            ].map((t) => (
              <li key={t} className="flex items-center gap-2">
                <CheckIcon className="h-4 w-4 flex-none text-emerald-400" /> {t}
              </li>
            ))}
          </ul>
        </div>
        <div className="landing-rise flex justify-center lg:justify-end" style={{ animationDelay: "120ms" }}>
          <ReportPreview />
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------- stats

function StatsBand() {
  return (
    <section aria-label="Enforcement by the numbers" className="border-b border-slate-200 bg-white">
      <dl className="mx-auto grid max-w-7xl gap-px bg-slate-200 sm:grid-cols-2 lg:grid-cols-4">
        {STATS.map((s) => (
          <div key={s.value} className="bg-white px-6 py-8">
            <dt className="text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
              {s.value}
              <SourceLink id={s.source} className="ml-1" />
            </dt>
            <dd className="mt-2 text-sm leading-relaxed text-slate-600">{s.label}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

// ------------------------------------------------------------------- why

function WhyItMatters() {
  return (
    <section id="why" className="scroll-mt-20 bg-slate-50 py-20 sm:py-28">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid gap-12 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <Eyebrow>Why it matters</Eyebrow>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
              A strike takes seconds to earn and months to undo.
            </h2>
            <p className="mt-5 text-lg leading-relaxed text-slate-600">
              Platforms now enforce with machines, at a scale no team can appeal its way out of. The fix is almost
              always tiny — a word in the caption, a three-second cut, a licence on file — but only if you find it{" "}
              <em>before</em> you post.
            </p>
            <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-6">
              <p className="text-sm font-semibold text-slate-900">After you post, the clock is not on your side</p>
              <ol className="mt-4 space-y-3 text-sm text-slate-600">
                {[
                  ["Claim or report", "Automated match or mass reports"],
                  ["Strike", "Upload and live limits, monetisation at risk"],
                  ["Second and third strike", "Within 90 days: channel up for termination"],
                  ["Appeal", "Weeks, with your evidence scattered across email and drives"],
                ].map(([a, b], i) => (
                  <li key={a} className="flex gap-3">
                    <span className="flex h-6 w-6 flex-none items-center justify-center rounded-full bg-red-50 text-xs font-semibold text-red-700 ring-1 ring-red-200">
                      {i + 1}
                    </span>
                    <span>
                      <span className="font-medium text-slate-900">{a}.</span> {b}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {SHIFTS.map((s) => (
              <article key={s.title} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h3 className="text-base font-semibold text-slate-900">
                  {s.title}
                  {[...s.sources].sort((a, b) => SOURCE_ORDER.indexOf(a) - SOURCE_ORDER.indexOf(b)).map((id) => (
                    <SourceLink key={id} id={id} className="ml-1" />
                  ))}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-slate-600">{s.body}</p>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------- stories

function Stories() {
  return (
    <section id="stories" className="relative scroll-mt-20 overflow-hidden bg-slate-950 py-20 text-white sm:py-28">
      <div className="pointer-events-none absolute left-[-10rem] top-20 h-[30rem] w-[30rem] rounded-full bg-indigo-700/20 blur-3xl" aria-hidden />
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          <Eyebrow dark>Cautionary tales</Eyebrow>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
            Real creators. Real takedowns. What a review would have caught.
          </h2>
          <p className="mt-4 text-lg text-slate-300">
            Documented cases, told from the public record and linked to the reporting. For each one: what happened,
            what CreatorShield checks for — and, honestly, what no tool could have prevented.
          </p>
        </div>

        <div className="mt-12 grid gap-6 lg:grid-cols-2">
          {CASES.map((c) => (
            <article
              key={c.who}
              className="flex flex-col rounded-2xl border border-white/10 bg-white/[0.04] p-6 backdrop-blur sm:p-7"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-red-500/15 px-2.5 py-1 text-xs font-semibold text-red-300 ring-1 ring-red-400/30">
                  {c.outcome}
                </span>
                <span className="text-xs text-slate-400">
                  {c.who} · {c.when}
                </span>
              </div>
              <h3 className="mt-4 text-xl font-semibold tracking-tight">{c.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-slate-300">{c.happened}</p>

              <div className="mt-5 rounded-xl border border-emerald-400/20 bg-emerald-400/[0.06] p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-emerald-300">
                  {c.flaggedTitle ?? "What CreatorShield checks for"}
                </p>
                <ul className="mt-3 space-y-2">
                  {c.flagged.map((f) => (
                    <li key={f} className="flex gap-2 text-sm text-slate-200">
                      <CheckIcon className="mt-0.5 h-4 w-4 flex-none text-emerald-400" />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
              <p className="mt-4 flex gap-2 text-sm text-slate-400">
                <XIcon className="mt-0.5 h-4 w-4 flex-none text-slate-500" />
                <span>
                  <span className="font-medium text-slate-300">What it can&apos;t do: </span>
                  {c.limits}
                </span>
              </p>
              <div className="mt-auto flex flex-wrap gap-x-4 gap-y-1 pt-5">
                {c.sources.map((id) => (
                  <a
                    key={id}
                    href={SOURCES[id].url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-indigo-300 hover:text-indigo-200"
                  >
                    <ExternalIcon className="h-3.5 w-3.5" />
                    {SOURCES[id].label.split(":")[0]}
                  </a>
                ))}
              </div>
            </article>
          ))}
        </div>

        <div className="mt-16">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h3 className="text-2xl font-semibold tracking-tight">The ten-second fix</h3>
            <p className="text-xs font-medium uppercase tracking-wider text-slate-500">
              Illustrative scenarios · not real accounts
            </p>
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {SCENARIOS.map((s) => (
              <article key={s.who} className="rounded-2xl border border-white/10 bg-slate-900/60 p-5">
                <p className="text-sm font-semibold text-white">{s.who}</p>
                <p className="mt-3 text-sm leading-relaxed text-slate-400">
                  <span className="font-medium text-red-300">Risk: </span>
                  {s.risk}
                </p>
                <p className="mt-3 text-sm leading-relaxed text-slate-300">
                  <span className="font-medium text-emerald-300">Caught: </span>
                  {s.fix}
                </p>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------- how

function HowItWorks() {
  const steps = [
    {
      t: "Upload or import",
      d: "Drop a file up to 30 minutes / 5 GB, or pick a post from your connected Instagram or YouTube account.",
    },
    {
      t: "We take it apart",
      d: "Timestamped transcript, key frames, on-screen text, sound, and a fingerprint of the picture and audio for repost matching.",
    },
    {
      t: "Checked four ways",
      d: "Rule-based checks, an AI policy review, provenance and repost matching, and your own rights ledger.",
    },
    {
      t: "Fix, then publish",
      d: "A ranked report with the quote or frame, the official rule and the fix. Plus an evidence pack if you ever need to dispute.",
    },
  ];
  return (
    <section id="how" className="scroll-mt-20 bg-white py-20 sm:py-28">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl">
          <Eyebrow>How it works</Eyebrow>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            Minutes before you post. Not months after.
          </h2>
        </div>
        <ol className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {steps.map((s, i) => (
            <li key={s.t} className="relative rounded-2xl border border-slate-200 bg-slate-50 p-6">
              <span className="font-mono text-sm font-semibold text-indigo-600">0{i + 1}</span>
              <h3 className="mt-3 text-lg font-semibold text-slate-900">{s.t}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{s.d}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------- features

const FEATURES = [
  {
    icon: ScanIcon,
    t: "Whole-video policy review",
    d: "Eight areas — community guidelines, harmful content, spam and misleading claims, monetisation, disclosure, originality, licensing and context — across speech, frames, on-screen text, caption and hashtags.",
  },
  {
    icon: PinIcon,
    t: "Evidence to the second",
    d: "Every finding is pinned to a timestamp with the exact quote or frame, a severity, a confidence and a concrete fix.",
  },
  {
    icon: BookIcon,
    t: "Citations you can trust",
    d: "35 rules written from official YouTube, Instagram, Meta and ASCI pages, each dated. The AI cannot cite anything outside the library.",
  },
  {
    icon: FingerprintIcon,
    t: "Copyright & provenance",
    d: "Spots other creators' handles, broadcaster and label logos and © notices on screen. Finds YouTube look-alikes. Optional song ID and web image search, with a spending cap.",
    tag: "New",
  },
  {
    icon: FilmIcon,
    t: "Cross-client repost catalogue",
    d: "Fingerprints every video you review. Catches your own reposts, and the same footage turning up under two different clients, even mirrored.",
    tag: "Agencies",
  },
  {
    icon: LedgerIcon,
    t: "Rights ledger",
    d: "Record licences, creator permissions, own channels and paid brand deals with proof. Matches are noted on every finding; expired and not-yet-started deals are flagged.",
  },
  {
    icon: MegaphoneIcon,
    t: "Sponsorship disclosure check",
    d: "Checks each declared sponsor against the opening caption, rejects 'not sponsored' style wording, and flags #ad buried in hashtags.",
  },
  {
    icon: PackageIcon,
    t: "One-click evidence pack",
    d: "The report, the original file's SHA-256 fingerprint, every match, your licences and proofs, and a draft dispute letter in one zip.",
  },
  {
    icon: LinkIcon,
    t: "Connected accounts",
    d: "Review posts you've already published through the official Instagram and YouTube APIs, cross-checked against your original file.",
  },
  {
    icon: LockIcon,
    t: "Private by design",
    d: "Videos auto-delete after 72 hours or whenever you choose, only a fingerprint is kept for repost matching, and instructions hidden in a video can't steer the AI.",
  },
];

function Features() {
  return (
    <section id="features" className="scroll-mt-20 bg-slate-50 py-20 sm:py-28">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl">
          <Eyebrow>Features</Eyebrow>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            Everything a reviewer, a rights team and a lawyer would check — in one pass.
          </h2>
          <p className="mt-4 text-lg text-slate-600">
            Platform tools tell you about a Content ID match after you upload. CreatorShield looks at the whole video,
            on both platforms, before you do.
          </p>
        </div>
        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <article
              key={f.t}
              className={`group relative rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${
                i === 0 || i === FEATURES.length - 1 ? "lg:col-span-2" : ""
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 ring-1 ring-indigo-100">
                  <f.icon className="h-5 w-5" />
                </span>
                {f.tag && (
                  <span className="rounded-full bg-fuchsia-50 px-2 py-0.5 text-[11px] font-semibold text-fuchsia-700 ring-1 ring-fuchsia-200">
                    {f.tag}
                  </span>
                )}
              </div>
              <h3 className="mt-4 text-base font-semibold text-slate-900">{f.t}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{f.d}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------- use cases

const AUDIENCES = [
  {
    icon: UsersIcon,
    t: "Creators with 100K to 10M followers",
    d: "Your channel is your business. Review every upload in the time it takes to write the caption.",
    points: ["Catch slurs, claims and missing disclosures", "Know which clip or song is a risk", "Keep licences in one place"],
  },
  {
    icon: BuildingIcon,
    t: "Agencies & talent managers",
    d: "One mistake on one client's channel is a call you don't want to make.",
    points: ["Client labels on every review", "Cross-client footage matching", "Evidence packs for disputes"],
  },
  {
    icon: TagIcon,
    t: "Brands running influencer campaigns",
    d: "ASCI and the CCPA hold advertisers responsible too.",
    points: ["Per-sponsor disclosure checks", "Claims review before the post goes live", "A record that you checked"],
  },
  {
    icon: ChartIcon,
    t: "Finance & health creators",
    d: "The categories regulators are watching most closely.",
    points: ["Flags 'guaranteed' returns and cure claims", "Qualification-disclosure reminders", "Hindi and English"],
  },
];

function UseCases() {
  return (
    <section id="use-cases" className="scroll-mt-20 bg-white py-20 sm:py-28">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl">
          <Eyebrow>Who it&apos;s for</Eyebrow>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            Built for the people with the most to lose.
          </h2>
        </div>
        <div className="mt-12 grid gap-6 md:grid-cols-2">
          {AUDIENCES.map((a) => (
            <article key={a.t} className="flex gap-5 rounded-2xl border border-slate-200 p-6">
              <span className="flex h-12 w-12 flex-none items-center justify-center rounded-2xl bg-slate-900 text-white">
                <a.icon className="h-6 w-6" />
              </span>
              <div>
                <h3 className="text-lg font-semibold text-slate-900">{a.t}</h3>
                <p className="mt-1 text-sm text-slate-600">{a.d}</p>
                <ul className="mt-4 space-y-1.5">
                  {a.points.map((p) => (
                    <li key={p} className="flex items-center gap-2 text-sm text-slate-700">
                      <CheckIcon className="h-4 w-4 flex-none text-indigo-600" /> {p}
                    </li>
                  ))}
                </ul>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------- faq + cta

function Faq() {
  return (
    <section id="faq" className="scroll-mt-20 bg-slate-50 py-20 sm:py-28">
      <div className="mx-auto grid max-w-7xl gap-12 px-4 sm:px-6 lg:grid-cols-[0.8fr_1.2fr] lg:px-8">
        <div>
          <Eyebrow>Straight answers</Eyebrow>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            No &lsquo;ban-proof&rsquo; promises. Just fewer surprises.
          </h2>
        </div>
        <div className="divide-y divide-slate-200 rounded-2xl border border-slate-200 bg-white">
          {FAQ.map((f) => (
            <details key={f.q} className="group p-5 sm:p-6">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-base font-semibold text-slate-900">
                {f.q}
                <span className="flex h-7 w-7 flex-none items-center justify-center rounded-full border border-slate-200 text-slate-500 transition group-open:rotate-45">
                  +
                </span>
              </summary>
              <p className="mt-3 text-sm leading-relaxed text-slate-600">{f.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

function FinalCta() {
  return (
    <section className="relative overflow-hidden bg-slate-950 py-20 text-white sm:py-24">
      <div
        className="pointer-events-none absolute left-1/2 top-1/2 h-[30rem] w-[50rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-indigo-600/25 blur-3xl"
        aria-hidden
      />
      <div className="relative mx-auto max-w-3xl px-4 text-center sm:px-6">
        <h2 className="text-3xl font-semibold tracking-tight sm:text-5xl">Your next upload is the one that counts.</h2>
        <p className="mx-auto mt-5 max-w-xl text-lg text-slate-300">
          Review it first. Most fixes take ten seconds; most appeals take weeks.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <PrimaryCta>Review a video now</PrimaryCta>
          <Link
            href="/dashboard"
            className="inline-flex items-center rounded-xl border border-white/15 px-5 py-3 text-sm font-semibold transition hover:bg-white/5"
          >
            Open the dashboard
          </Link>
        </div>
      </div>
    </section>
  );
}

function Sources() {
  return (
    <section id="sources" aria-label="Sources" className="scroll-mt-20 border-t border-slate-200 bg-white py-12">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <h2 className="text-sm font-semibold text-slate-900">Sources</h2>
        <ol className="mt-4 grid gap-x-8 gap-y-2 text-xs text-slate-500 md:grid-cols-2">
          {SOURCE_ORDER.map((id, i) => (
            <li key={id} className="flex gap-2">
              <span className="w-5 flex-none text-right font-mono">{i + 1}.</span>
              <a href={SOURCES[id].url} target="_blank" rel="noopener noreferrer" className="hover:text-indigo-600">
                {SOURCES[id].label}
              </a>
            </li>
          ))}
        </ol>
        <p className="mt-6 max-w-3xl text-xs leading-relaxed text-slate-400">
          Case summaries are drawn from public reporting linked above; outcomes may have changed since publication.
          &ldquo;What CreatorShield checks for&rdquo; describes the checks the product runs today, not a claim about how
          any platform would have ruled.
        </p>
      </div>
    </section>
  );
}

export function LandingPage() {
  return (
    <>
      <Hero />
      <StatsBand />
      <WhyItMatters />
      <Stories />
      <HowItWorks />
      <Features />
      <UseCases />
      <Faq />
      <FinalCta />
      <Sources />
    </>
  );
}
