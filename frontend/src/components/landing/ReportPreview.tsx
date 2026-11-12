// A static picture of a CreatorShield report for the hero. Labelled as an example.

const FINDINGS = [
  {
    at: "0:00",
    sev: "High",
    tone: "bg-red-500/15 text-red-300 ring-red-400/30",
    area: "Disclosure",
    text: "Paid agreement with FitFuel: no disclosure in the opening caption",
    from: "Rights ledger",
  },
  {
    at: "0:21",
    sev: "Medium",
    tone: "bg-amber-500/15 text-amber-200 ring-amber-400/30",
    area: "Licensing",
    text: "Broadcaster logo on screen: “Star Sports”",
    from: "On-screen text",
  },
  {
    at: "0:37",
    sev: "Medium",
    tone: "bg-amber-500/15 text-amber-200 ring-amber-400/30",
    area: "Claims",
    text: "“Guaranteed to burn fat in 7 days”",
    from: "Speech",
  },
  {
    at: "0:44",
    sev: "Low",
    tone: "bg-sky-500/15 text-sky-200 ring-sky-400/30",
    area: "Originality",
    text: "Footage also appears under another client",
    from: "Catalogue",
  },
];

export function ReportPreview() {
  const score = 72;
  const circumference = 2 * Math.PI * 34;
  return (
    <figure
      aria-label="Example CreatorShield report"
      className="relative w-full max-w-xl rounded-2xl border border-white/10 bg-slate-900/70 p-5 text-left shadow-2xl shadow-indigo-950/60 backdrop-blur-xl sm:p-6"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-indigo-300/80">Example report</p>
          <p className="mt-1 truncate text-base font-semibold text-white">Morning routine with FitFuel</p>
          <p className="mt-0.5 text-xs text-slate-400">Instagram Reel · 0:58 · English</p>
        </div>
        <div className="relative h-20 w-20 flex-none" role="img" aria-label={`Risk score ${score} of 100, high`}>
          <svg viewBox="0 0 80 80" className="h-20 w-20 -rotate-90">
            <circle cx="40" cy="40" r="34" fill="none" stroke="currentColor" strokeWidth="7" className="text-white/10" />
            <circle
              cx="40"
              cy="40"
              r="34"
              fill="none"
              stroke="url(#risk)"
              strokeWidth="7"
              strokeLinecap="round"
              strokeDasharray={`${(score / 100) * circumference} ${circumference}`}
            />
            <defs>
              <linearGradient id="risk" x1="0" x2="1" y1="0" y2="1">
                <stop offset="0%" stopColor="#f59e0b" />
                <stop offset="100%" stopColor="#ef4444" />
              </linearGradient>
            </defs>
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xl font-semibold leading-none text-white">{score}</span>
            <span className="mt-0.5 text-[10px] font-medium uppercase tracking-wider text-red-300">High</span>
          </div>
        </div>
      </div>

      <ol className="mt-5 space-y-2">
        {FINDINGS.map((f) => (
          <li key={f.at} className="flex items-start gap-3 rounded-xl border border-white/5 bg-white/[0.03] p-3">
            <span className="mt-0.5 flex-none rounded-md bg-white/10 px-1.5 py-0.5 font-mono text-[11px] text-slate-200">
              {f.at}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${f.tone}`}>{f.sev}</span>
                <span className="text-[11px] font-medium text-slate-400">{f.area}</span>
                <span className="text-[11px] text-slate-500">· {f.from}</span>
              </div>
              <p className="mt-1 text-[13px] leading-snug text-slate-100">{f.text}</p>
            </div>
          </li>
        ))}
      </ol>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-white/10 pt-4">
        <p className="text-xs text-slate-400">
          Cited to <span className="text-slate-200">YouTube, Instagram &amp; ASCI</span> official pages
        </p>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-400/10 px-2.5 py-1 text-[11px] font-medium text-emerald-300 ring-1 ring-emerald-400/30">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Evidence pack ready
        </span>
      </div>
    </figure>
  );
}
