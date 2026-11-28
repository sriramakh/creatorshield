"use client";

import { CircleCheck, CircleX, Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { api, errorMessage, type Health, type Language, type WorkspaceSettings } from "@/lib/api";
import { setTheme, useThemeChoice, type ThemeChoice } from "@/lib/theme";
import { useWorkspace } from "@/lib/workspace";
import { MarketPicker } from "./creator/MarketPicker";
import { MODE_OPTIONS } from "./OnboardingDialog";
import { PageContainer } from "./shell/AppShell";
import { LANGUAGE_OPTIONS } from "@/lib/reviewForm";
import { Badge, Button, Callout, ErrorNotice, Field, Input, PageHeader, RadioCards, Section, SegmentedControl, Select, Skeleton, useToast } from "./ui";

type Draft = Pick<WorkspaceSettings, "mode" | "display_name" | "default_platform" | "default_markets" | "default_language">;

export function SettingsPage() {
  const { settings, settingsError, config, platforms, updateSettings, marketLabel } = useWorkspace();
  const toast = useToast();
  const theme = useThemeChoice();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [baseline, setBaseline] = useState<WorkspaceSettings | null>(null);
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [statsDays, setStatsDays] = useState<number | null>(null);
  const [catalogueDays, setCatalogueDays] = useState<number | null>(null);

  if (settings && baseline !== settings) {
    setBaseline(settings);
    setDraft({
      mode: settings.mode,
      display_name: settings.display_name,
      default_platform: settings.default_platform,
      default_markets: settings.default_markets,
      default_language: settings.default_language,
    });
  }

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((e: unknown) => setHealthError(errorMessage(e)));
    api
      .insights(7)
      .then((i) => setStatsDays(i.stats_retention_days))
      .catch(() => {});
    api
      .provenanceStatus()
      .then((s) => setCatalogueDays(s.catalogue.retention_days))
      .catch(() => {});
  }, []);

  const dirty =
    !!draft &&
    !!settings &&
    (draft.mode !== settings.mode ||
      draft.display_name !== settings.display_name ||
      draft.default_platform !== settings.default_platform ||
      draft.default_language !== settings.default_language ||
      draft.default_markets.join() !== settings.default_markets.join());

  async function save() {
    if (!draft || !settings) return;
    setBusy(true);
    const patch: Partial<WorkspaceSettings> = {};
    (Object.keys(draft) as (keyof Draft)[]).forEach((k) => {
      if (JSON.stringify(draft[k]) !== JSON.stringify(settings[k])) Object.assign(patch, { [k]: k === "display_name" ? draft[k].trim() : draft[k] });
    });
    try {
      await updateSettings(patch);
      toast({ tone: "success", title: "Settings saved" });
    } catch (e) {
      toast({ tone: "error", title: "Settings were not saved", description: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  }

  const kb = health?.checks.policy_kb;
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft((d) => (d ? { ...d, [k]: v } : d));

  return (
    <PageContainer className="max-w-4xl space-y-6">
      <PageHeader title="Settings" description="Defaults for new reviews and caption checks, how the workspace reads, and what the system keeps." />
      {settingsError && <ErrorNotice title="Could not load settings" message={settingsError} />}

      <Section
        title="Workspace"
        description="New reviews and caption checks start with these choices; you can change them on each one."
        actions={
          <Button variant="primary" onClick={save} loading={busy} disabled={!dirty}>
            Save changes
          </Button>
        }
      >
        {!draft ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <div className="space-y-5">
            <fieldset className="space-y-2">
              <legend className="mb-2 text-[13px] font-medium text-ink">Workspace mode</legend>
              <RadioCards label="Workspace mode" value={draft.mode} onChange={(v) => set("mode", v)} options={MODE_OPTIONS} />
              <p className="text-[12px] text-ink-3">
                {draft.mode === "agency"
                  ? "Agency mode shows client labels on uploads, reviews, the catalogue and the rights ledger, and breaks insights down by client."
                  : "Creator mode hides client labels and treats your catalogue as your own past posts."}
              </p>
            </fieldset>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Display name" hint="Used for the greeting on Overview.">
                {(p) => <Input {...p} value={draft.display_name} onChange={(e) => set("display_name", e.target.value.slice(0, 80))} />}
              </Field>
              <Field label="Default platform">
                {(p) => (
                  <Select {...p} value={draft.default_platform} onChange={(e) => set("default_platform", e.target.value)}>
                    {platforms.map((pl) => (
                      <option key={pl.id} value={pl.id}>
                        {pl.label}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            </div>
            <div className="space-y-1.5">
              <div className="text-[13px] font-medium text-ink">Default audience markets</div>
              <MarketPicker value={draft.default_markets} onChange={(v) => set("default_markets", v)} label="Default audience markets" />
            </div>
            <div className="space-y-1.5">
              <div className="text-[13px] font-medium text-ink">Default spoken language</div>
              <SegmentedControl label="Default spoken language" value={draft.default_language} onChange={(v: Language) => set("default_language", v)} options={LANGUAGE_OPTIONS} />
            </div>
          </div>
        )}
      </Section>

      <Section title="Appearance">
        <div className="space-y-1.5">
          <div className="text-[13px] font-medium text-ink">Theme</div>
          <SegmentedControl<ThemeChoice>
            label="Theme"
            value={theme}
            onChange={setTheme}
            options={[
              { value: "light", label: (
                  <>
                    <Sun aria-hidden /> Light
                  </>
                ), ariaLabel: "Light" },
              { value: "dark", label: (
                  <>
                    <Moon aria-hidden /> Dark
                  </>
                ), ariaLabel: "Dark" },
              { value: "system", label: (
                  <>
                    <Monitor aria-hidden /> Match system
                  </>
                ), ariaLabel: "Match system" },
            ]}
          />
          <p className="text-[12px] text-ink-3">Saved in this browser.</p>
        </div>
      </Section>

      <Section title="Data and retention" description="Set on the server. Shown here so you know what is kept.">
        {!config ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <dl className="grid gap-x-6 gap-y-3 text-[13px] sm:grid-cols-2">
            <Fact label="Videos, frames and transcripts">
              {config.delete_media_after_analysis ? "Deleted as soon as each review finishes" : `Deleted after ${config.retention_hours} hours`}
            </Fact>
            <Fact label="Insights">{statsDays != null ? `Outcomes only, no content, kept ${statsDays} days` : "Outcomes only, no content"}</Fact>
            <Fact label="Catalogue fingerprints">{catalogueDays != null ? `Kept ${catalogueDays} days; no media` : "No media is kept"}</Fact>
            <Fact label="Rights-ledger proofs">Kept until you delete the record</Fact>
          </dl>
        )}
      </Section>

      <Section title="System">
        {healthError && <Callout tone="danger" title="Could not read system health">{healthError}</Callout>}
        {!health && !healthError && <Skeleton className="h-24 w-full" />}
        {health && (
          <div className="space-y-4">
            <ul className="grid gap-2 sm:grid-cols-2">
              {Object.entries(health.checks)
                .filter(([k]) => k !== "policy_kb")
                .map(([k, v]) => {
                  const ok = v === "ok" || v === "not_used";
                  return (
                    <li key={k} className="flex items-center justify-between gap-3 rounded-[8px] border border-line px-3 py-2 text-[13px]">
                      <span className="capitalize text-ink">{k.replace(/_/g, " ")}</span>
                      <Badge tone={ok ? "success" : "critical"} icon={ok ? CircleCheck : CircleX}>
                        {typeof v === "string" ? v.replace(/_/g, " ") : "ok"}
                      </Badge>
                    </li>
                  );
                })}
            </ul>
            <dl className="grid gap-x-6 gap-y-3 text-[13px] sm:grid-cols-2">
              <Fact label="AI provider">
                {config ? `${config.ai_provider}${config.ai_model && config.ai_model !== config.ai_provider ? ` · ${config.ai_model}` : ""}${config.mock_mode ? " (mock: placeholder findings)" : ""}` : "—"}
              </Fact>
              <Fact label="Policy library">{kb && typeof kb === "object" ? `Version ${kb.version} · ${kb.rules} rules` : "—"}</Fact>
              <Fact label="Audience markets">{config?.markets.map((m) => `${marketLabel(m.id)} (${m.regulator})`).join(", ") ?? "—"}</Fact>
              <Fact label="Platforms">{platforms.map((p) => p.label).join(", ") || "—"}</Fact>
            </dl>
          </div>
        )}
      </Section>
    </PageContainer>
  );
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-ink-3">{label}</dt>
      <dd className="mt-0.5 text-ink">{children}</dd>
    </div>
  );
}
