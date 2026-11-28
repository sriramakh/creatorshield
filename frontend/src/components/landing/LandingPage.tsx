import {
  ArrowRight,
  BookOpen,
  BriefcaseBusiness,
  Building,
  ChartLine,
  Check,
  Earth,
  ListChecks,
  ExternalLink,
  Film,
  FingerprintPattern,
  Link2,
  Lock,
  Megaphone,
  Package,
  Plus,
  ScanSearch,
  ScanText,
  Scale,
  Tag,
  Timer,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";
import { BRAND } from "@/lib/brand";
import { NEW_REVIEW_HREF } from "@/lib/nav";
import { ButtonLink } from "../ui";
import { CASES, FAQ, SCENARIOS, SHIFTS, SOURCE_ORDER, SOURCES, STATS, type SourceId } from "./content";
import { ReportPreview } from "./ReportPreview";

function SourceLink({ id }: { id: SourceId }) {
  const n = SOURCE_ORDER.indexOf(id) + 1;
  return (
    <a
      href={SOURCES[id].url}
      target="_blank"
      rel="noopener noreferrer"
      title={SOURCES[id].label}
      aria-label={`Source ${n}: ${SOURCES[id].label}`}
      className="ml-0.5 align-super text-[10px] font-semibold text-accent hover:underline"
    >
      [{n}]
    </a>
  );
}

function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="text-[12px] leading-4 font-semibold tracking-[0.08em] text-accent uppercase">{children}</p>;
}

function SectionHeading({ eyebrow, title, lead }: { eyebrow: string; title: ReactNode; lead?: ReactNode }) {
  return (
    <div className="max-w-2xl">
      <Eyebrow>{eyebrow}</Eyebrow>
      <h2 className="mt-3 text-[28px] leading-9 font-[650] tracking-tight text-ink sm:text-[34px] sm:leading-[42px]">{title}</h2>
      {lead && <p className="mt-4 text-[16px] leading-7 text-ink-2">{lead}</p>}
    </div>
  );
}

const WRAP = "mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8";

// ------------------------------------------------------------------- hero

function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-line bg-canvas">
      <div className="landing-grid pointer-events-none absolute inset-0" aria-hidden />
      <div className={`relative grid items-center gap-12 pt-14 pb-16 lg:grid-cols-[1.05fr_1fr] lg:pt-20 lg:pb-24 ${WRAP}`}>
        <div>
          <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-[12px] font-medium text-ink-2">
            <span className="size-1.5 rounded-full bg-success-solid" aria-hidden />
            Pre-publication review for Shorts and Reels
          </span>
          <h1 className="mt-6 text-[40px] leading-[44px] font-[650] tracking-tight text-ink sm:text-[56px] sm:leading-[60px]">
            Years to build.
            <br />
            <span className="text-accent">One upload to lose.</span>
          </h1>
          <p className="mt-6 max-w-xl text-[17px] leading-7 text-ink-2">
            {BRAND.name} checks your video and caption against official YouTube and Instagram rules and the advertising guidance of
            the markets you post to, then gives one verdict: fix first, review, or no issues found by these checks. It reads the full
            transcript, sampled key frames, on-screen text and the caption, and shows what to fix,{" "}
            <span className="font-medium text-ink">down to the second</span> wherever the evidence is in the video.
          </p>
          <p className="mt-3 text-[15px] text-ink-3">For independent creators, and for the agencies and managers who post for them.</p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <ButtonLink href={NEW_REVIEW_HREF} variant="primary" size="lg" trailingIcon={<ArrowRight />}>
              Start a review
            </ButtonLink>
            <ButtonLink href="/check" size="lg" leadingIcon={<ScanText />}>
              Check a caption
            </ButtonLink>
          </div>
          <ul className="mt-8 grid gap-2 text-[14px] text-ink-2 sm:grid-cols-2">
            {[
              "Instant caption check, nothing stored",
              "Disclosure checked for India, the US and the UK",
              "Brand briefs checked on every review",
              "Cites only verified official pages",
              "English and हिंदी, up to 30 minutes",
              "Auto-deletes videos after 72 hours by default",
            ].map((t) => (
              <li key={t} className="flex items-center gap-2">
                <Check className="size-4 shrink-0 text-success-fg" aria-hidden /> {t}
              </li>
            ))}
          </ul>
        </div>
        <div className="flex justify-center lg:justify-end">
          <ReportPreview />
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------- stats

function StatsBand() {
  return (
    <section aria-label="Enforcement by the numbers" className="border-b border-line bg-surface">
      <dl className={`grid gap-px sm:grid-cols-2 lg:grid-cols-4 ${WRAP} px-0 sm:px-0 lg:px-0`}>
        {STATS.map((s) => (
          <div key={s.value} className="px-6 py-8">
            <dt className="tabular text-[32px] leading-10 font-[650] tracking-tight text-ink">
              {s.value}
              <SourceLink id={s.source} />
            </dt>
            <dd className="mt-2 text-[14px] leading-6 text-ink-2">{s.label}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

// ------------------------------------------------------------------- why

function WhyItMatters() {
  return (
    <section id="why" className="scroll-mt-20 py-20 sm:py-24">
      <div className={`grid gap-12 lg:grid-cols-[0.9fr_1.1fr] ${WRAP}`}>
        <div>
          <SectionHeading
            eyebrow="Why it matters"
            title="A strike takes seconds to earn and months to undo."
            lead={
              <>
                Platforms enforce with machines, at a scale no team can appeal its way out of. The fix is usually small — a
                word in the caption, a three-second cut, a licence on file — but only if you find it <em>before</em> you post.
              </>
            }
          />
          <div className="mt-8 rounded-[10px] border border-line bg-surface p-6">
            <p className="text-[14px] font-semibold text-ink">After you post, the clock is not on your side</p>
            <ol className="mt-4 space-y-3 text-[14px] text-ink-2">
              {[
                ["Claim or report", "Automated match or mass reports"],
                ["Strike", "Upload and live limits, monetisation at risk"],
                ["Second and third strike", "Within 90 days: channel up for termination"],
                ["Appeal", "Weeks, with your evidence scattered across email and drives"],
              ].map(([a, b], i) => (
                <li key={a} className="flex gap-3">
                  <span className="tabular flex size-6 flex-none items-center justify-center rounded-full border border-critical-line bg-critical-bg text-[12px] font-semibold text-critical-fg">
                    {i + 1}
                  </span>
                  <span>
                    <span className="font-medium text-ink">{a}.</span> {b}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </div>
        <div className="grid content-start gap-4 sm:grid-cols-2">
          {SHIFTS.map((s) => (
            <article key={s.title} className="rounded-[10px] border border-line bg-surface p-6">
              <h3 className="text-[16px] font-semibold text-ink">
                {s.title}
                {[...s.sources]
                  .sort((a, b) => SOURCE_ORDER.indexOf(a) - SOURCE_ORDER.indexOf(b))
                  .map((id) => (
                    <SourceLink key={id} id={id} />
                  ))}
              </h3>
              <p className="mt-3 text-[14px] leading-6 text-ink-2">{s.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------- stories

function Stories() {
  return (
    <section id="stories" className="scroll-mt-20 border-y border-line bg-surface py-20 sm:py-24">
      <div className={WRAP}>
        <SectionHeading
          eyebrow="Cautionary tales"
          title="Real creators. Real takedowns. What a review checks for."
          lead="Documented cases, told from the public record and linked to the reporting. For each: what happened, what a review checks for in content like it, and, honestly, what no tool could have prevented."
        />
        <div className="mt-12 grid gap-5 lg:grid-cols-2">
          {CASES.map((c) => (
            <article key={c.who} className="flex flex-col rounded-[10px] border border-line bg-canvas p-6">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-[6px] border border-critical-line bg-critical-bg px-2 py-0.5 text-[12px] font-medium text-critical-fg">{c.outcome}</span>
                <span className="text-[13px] text-ink-3">
                  {c.who} · {c.when}
                </span>
              </div>
              <h3 className="mt-4 text-[19px] leading-7 font-semibold tracking-tight text-ink">{c.title}</h3>
              <p className="mt-2 text-[14px] leading-6 text-ink-2">{c.happened}</p>
              <div className="mt-5 rounded-[8px] border border-line bg-surface p-4">
                <p className="text-[12px] font-semibold tracking-[0.04em] text-success-fg uppercase">{c.flaggedTitle ?? "What a review checks for"}</p>
                <ul className="mt-3 space-y-2">
                  {c.flagged.map((f) => (
                    <li key={f} className="flex gap-2 text-[14px] text-ink">
                      <Check className="mt-1 size-4 flex-none text-success-fg" aria-hidden />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
              <p className="mt-4 flex gap-2 text-[14px] text-ink-2">
                <X className="mt-1 size-4 flex-none text-ink-3" aria-hidden />
                <span>
                  <span className="font-medium text-ink">What it cannot do: </span>
                  {c.limits}
                </span>
              </p>
              <div className="mt-auto flex flex-wrap gap-x-4 gap-y-1 pt-5">
                {c.sources.map((id) => (
                  <a key={id} href={SOURCES[id].url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[13px] text-accent hover:underline">
                    <ExternalLink className="size-3.5" aria-hidden />
                    {SOURCES[id].label.split(":")[0]}
                  </a>
                ))}
              </div>
            </article>
          ))}
        </div>

        <div className="mt-16">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h3 className="text-[22px] leading-8 font-semibold tracking-tight text-ink">The ten-second fix</h3>
            <p className="text-[12px] font-medium tracking-[0.06em] text-ink-3 uppercase">Illustrative scenarios · not real accounts</p>
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {SCENARIOS.map((s) => (
              <article key={s.who} className="rounded-[10px] border border-line bg-canvas p-5">
                <p className="text-[14px] font-semibold text-ink">{s.who}</p>
                <p className="mt-3 text-[14px] leading-6 text-ink-2">
                  <span className="font-medium text-high-fg">Risk: </span>
                  {s.risk}
                </p>
                <p className="mt-3 text-[14px] leading-6 text-ink-2">
                  <span className="font-medium text-success-fg">Caught: </span>
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

const STEPS = [
  { t: "Upload or import", d: "Drop a file up to 30 minutes / 5 GB, or pick a post from your connected Instagram or YouTube account." },
  { t: "We take it apart", d: "Timestamped transcript, key frames, on-screen text, sound, and a fingerprint of the picture and audio for repost matching." },
  { t: "Checked four ways", d: "Rule-based checks, an AI policy review, provenance and repost matching, and your own rights ledger." },
  { t: "Fix, then publish", d: "A ranked report with the quote or frame, the official rule and the fix. Plus an evidence pack if you ever need to dispute." },
];

function HowItWorks() {
  return (
    <section id="how" className="scroll-mt-20 py-20 sm:py-24">
      <div className={WRAP}>
        <SectionHeading eyebrow="How it works" title="Minutes before you post. Not months after." />
        <ol className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <li key={s.t} className="rounded-[10px] border border-line bg-surface p-6">
              <span className="tabular font-mono text-[13px] font-semibold text-accent">0{i + 1}</span>
              <h3 className="mt-3 text-[17px] font-semibold text-ink">{s.t}</h3>
              <p className="mt-2 text-[14px] leading-6 text-ink-2">{s.d}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------- features

const FEATURES: { icon: LucideIcon; t: string; d: string; tag?: string }[] = [
  {
    icon: ListChecks,
    t: "One readiness verdict",
    d: "Every review ends in one answer — fix first, review, or no issues found by these checks — with a checklist of what passed, what to check and what was not checked. Never “safe” or “approved”: without a completed AI review the best verdict is “review”.",
  },
  {
    icon: ScanText,
    t: "Instant caption check",
    d: "Paste a caption and see the disclosure status in each market, flagged wording with the rule behind it, and a suggested caption when the label is not clear. Rule-based, answers in milliseconds, stores nothing.",
    tag: "New",
  },
  {
    icon: Earth,
    t: "Market-aware disclosure",
    d: "Choose India, the US or the UK. Each adds that regulator’s advisory guidance — ASCI and the Department of Consumer Affairs, the FTC, or the ASA, CAP and CMA — and its view of which labels are clear, cited to official pages. Advisory, not legal advice.",
    tag: "New",
  },
  {
    icon: BriefcaseBusiness,
    t: "Brand-brief checks",
    d: "Save what a sponsor asked for — must-say lines, banned wording, hashtags, mentions, competitors and the opening disclosure — and every review checks the caption, speech and on-screen text against it.",
    tag: "New",
  },
  {
    icon: ScanSearch,
    t: "Full-length policy review",
    d: "Eight areas — community guidelines, harmful content, spam and misleading claims, monetisation, disclosure, originality, licensing and context — across the full transcript, key frames sampled through the video, on-screen text, caption and hashtags.",
  },
  {
    icon: Timer,
    t: "Evidence to the second",
    d: "Findings in the video are pinned to a timestamp with the exact quote or frame; caption and metadata findings quote the text. Each comes with a severity, a confidence and a concrete fix.",
  },
  {
    icon: BookOpen,
    t: "Citations you can check",
    d: "A versioned library of rules written from official platform and advertising-standards pages, each dated. The AI cannot cite anything outside the library.",
  },
  {
    icon: FingerprintPattern,
    t: "Copyright and provenance",
    d: "Reads other creators' @handles, broadcaster, studio and label names and © notices in on-screen text, and the AI review checks sampled frames for logos and scorebugs. Finds YouTube look-alikes. Opt-in paid song ID and web image search, with a spending cap.",
  },
  {
    icon: Film,
    t: "Cross-client repost catalogue",
    d: "Fingerprints every video you review. Catches your own reposts, and the same footage turning up under two different clients, even mirrored.",
    tag: "Agencies",
  },
  {
    icon: Scale,
    t: "Rights ledger",
    d: "Record licences, creator permissions, own channels and paid brand deals with proof. Matches are noted on every finding; expired and not-yet-started deals are flagged.",
  },
  {
    icon: Megaphone,
    t: "Sponsorship disclosure check",
    d: "Checks each declared sponsor against the opening caption, rejects 'not sponsored' style wording, and flags #ad buried in hashtags.",
  },
  {
    icon: Package,
    t: "One-click evidence pack",
    d: "The report, the original file's SHA-256 fingerprint, every match, your licences and proofs, and a draft dispute letter in one zip.",
  },
  {
    icon: Link2,
    t: "Connected accounts",
    d: "Review posts you've already published through the official Instagram and YouTube APIs, cross-checked against your original file.",
  },
  {
    icon: Lock,
    t: "Private by design",
    d: "Videos auto-delete after 72 hours by default or whenever you choose, and only a fingerprint is kept for repost matching. Speech, captions and on-screen text reach the AI as fenced-off data to review, with defences against instructions hidden in a video.",
  },
];

function Features() {
  return (
    <section id="features" className="scroll-mt-20 border-y border-line bg-surface py-20 sm:py-24">
      <div className={WRAP}>
        <SectionHeading
          eyebrow="Features"
          title="What a policy reviewer and a rights team would check — in one pass."
          lead="Platform tools tell you about a Content ID match after you upload. A review covers the speech, frames and text of your file, for both platforms, before you do."
        />
        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <article key={f.t} className={`rounded-[10px] border border-line bg-canvas p-6 ${i === 0 || i === FEATURES.length - 1 ? "lg:col-span-2" : ""}`}>
              <div className="flex items-center justify-between">
                <span className="flex size-10 items-center justify-center rounded-[10px] border border-line bg-surface text-accent">
                  <f.icon className="size-5" strokeWidth={1.75} aria-hidden />
                </span>
                {f.tag && <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[12px] font-medium text-accent">{f.tag}</span>}
              </div>
              <h3 className="mt-4 text-[16px] font-semibold text-ink">{f.t}</h3>
              <p className="mt-2 text-[14px] leading-6 text-ink-2">{f.d}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------- audiences

const AUDIENCES: { icon: LucideIcon; t: string; d: string; points: string[] }[] = [
  {
    icon: Users,
    t: "Independent creators",
    d: "Your channel is your business. Review every upload in the time it takes to write the caption.",
    points: ["Check a caption in seconds before you post", "Catch claims and missing disclosures", "Flag reused clips and music to clear"],
  },
  {
    icon: Building,
    t: "Agencies and talent managers",
    d: "One mistake on one client's channel is a call you don't want to make.",
    points: ["Brand briefs checked on every client video", "Client labels, filters and insights by client", "Cross-client footage matching and evidence packs"],
  },
  {
    icon: Tag,
    t: "Brands running influencer campaigns",
    d: "Regulators in India, the US and the UK hold advertisers responsible too.",
    points: ["Per-sponsor, per-market disclosure checks", "Your brief checked before the post goes live", "A record that you checked"],
  },
  {
    icon: ChartLine,
    t: "Finance and health creators",
    d: "The categories regulators are watching most closely.",
    points: ["Flags 'guaranteed' returns and cure claims", "Qualification-disclosure reminders", "Hindi and English"],
  },
];

function UseCases() {
  return (
    <section id="use-cases" className="scroll-mt-20 py-20 sm:py-24">
      <div className={WRAP}>
        <SectionHeading eyebrow="Who it's for" title="Built for the people with the most to lose." />
        <div className="mt-12 grid gap-4 md:grid-cols-2">
          {AUDIENCES.map((a) => (
            <article key={a.t} className="flex gap-5 rounded-[10px] border border-line bg-surface p-6">
              <span className="flex size-11 flex-none items-center justify-center rounded-[10px] bg-accent-soft text-accent">
                <a.icon className="size-5" strokeWidth={1.75} aria-hidden />
              </span>
              <div>
                <h3 className="text-[17px] font-semibold text-ink">{a.t}</h3>
                <p className="mt-1 text-[14px] text-ink-2">{a.d}</p>
                <ul className="mt-4 space-y-1.5">
                  {a.points.map((p) => (
                    <li key={p} className="flex items-center gap-2 text-[14px] text-ink">
                      <Check className="size-4 flex-none text-accent" aria-hidden /> {p}
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

// ------------------------------------------------------------------- faq, cta, sources

function Faq() {
  return (
    <section id="faq" className="scroll-mt-20 border-y border-line bg-surface py-20 sm:py-24">
      <div className={`grid gap-12 lg:grid-cols-[0.8fr_1.2fr] ${WRAP}`}>
        <SectionHeading eyebrow="Straight answers" title={<>No ‘ban-proof’ promises. Just fewer surprises.</>} />
        <div className="divide-y divide-line rounded-[10px] border border-line bg-canvas">
          {FAQ.map((f) => (
            <details key={f.q} className="group px-5 py-4 sm:px-6">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 rounded-[6px] text-[15px] font-semibold text-ink [&::-webkit-details-marker]:hidden">
                {f.q}
                <Plus className="size-4 flex-none text-ink-3 transition-transform duration-[180ms] group-open:rotate-45" aria-hidden />
              </summary>
              <p className="mt-3 text-[14px] leading-6 text-ink-2">{f.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

function FinalCta() {
  return (
    <section className="py-20 sm:py-24">
      <div className="mx-auto max-w-3xl px-4 text-center sm:px-6">
        <h2 className="text-[30px] leading-9 font-[650] tracking-tight text-ink sm:text-[40px] sm:leading-[48px]">Your next upload is the one that counts.</h2>
        <p className="mx-auto mt-4 max-w-xl text-[17px] leading-7 text-ink-2">Review it first. Most fixes take ten seconds; most appeals take weeks.</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <ButtonLink href={NEW_REVIEW_HREF} variant="primary" size="lg" trailingIcon={<ArrowRight />}>
            Start a review
          </ButtonLink>
          <ButtonLink href="/dashboard" size="lg">
            Open the app
          </ButtonLink>
        </div>
      </div>
    </section>
  );
}

function Sources() {
  return (
    <section id="sources" aria-label="Sources" className="scroll-mt-20 border-t border-line bg-surface py-12">
      <div className={WRAP}>
        <h2 className="text-[14px] font-semibold text-ink">Sources</h2>
        <ol className="mt-4 grid gap-x-8 gap-y-2 text-[13px] text-ink-3 md:grid-cols-2">
          {SOURCE_ORDER.map((id, i) => (
            <li key={id} className="flex gap-2">
              <span className="tabular w-5 flex-none text-right font-mono">{i + 1}.</span>
              <a href={SOURCES[id].url} target="_blank" rel="noopener noreferrer" className="hover:text-accent hover:underline">
                {SOURCES[id].label}
              </a>
            </li>
          ))}
        </ol>
        <p className="mt-6 max-w-3xl text-[13px] leading-5 text-ink-3">
          Case summaries are drawn from public reporting linked above; outcomes may have changed since publication. “What a review
          checks for” describes the checks the product runs today, not a claim about how any platform would have ruled.
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
