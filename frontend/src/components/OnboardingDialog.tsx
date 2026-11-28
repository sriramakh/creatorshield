"use client";

import { Building, User } from "lucide-react";
import { useState } from "react";
import { errorMessage, type MarketId, type WorkspaceMode } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { MarketPicker } from "./creator/MarketPicker";
import { Button, Callout, Dialog, Field, Input, RadioCards, useToast } from "./ui";

export const MODE_OPTIONS: { value: WorkspaceMode; title: string; description: string; icon: React.ReactNode }[] = [
  {
    value: "creator",
    title: "I post my own videos",
    description: "Simple wording, no client labels. Your past posts are your catalogue.",
    icon: <User />,
  },
  {
    value: "agency",
    title: "I manage creators or brands",
    description: "Client labels on reviews, filters and insights by client, cross-client footage matching.",
    icon: <Building />,
  },
];

/** First run (settings.onboarded === false): three questions, then onboarded: true. Skippable. */
export function OnboardingDialog() {
  const { settings, platforms, updateSettings } = useWorkspace();
  const toast = useToast();
  const [dismissed, setDismissed] = useState(false);
  const [mode, setMode] = useState<WorkspaceMode | null>(null);
  const [name, setName] = useState("");
  const [markets, setMarkets] = useState<MarketId[] | null>(null);
  const [platform, setPlatform] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!settings || settings.onboarded || dismissed) return null;

  async function save(skip: boolean) {
    if (!settings) return;
    setBusy(true);
    setError(null);
    try {
      await updateSettings(
        skip
          ? { onboarded: true }
          : {
              onboarded: true,
              mode: mode ?? settings.mode,
              display_name: name.trim(),
              default_markets: markets ?? settings.default_markets,
              default_platform: platform ?? settings.default_platform,
            },
      );
      setDismissed(true);
      if (!skip) toast({ tone: "success", title: "Workspace set up", description: "Change any of this later in Settings." });
    } catch (e) {
      if (skip) {
        // Skipping always closes it for this visit; it asks again next time if the save failed.
        setDismissed(true);
        toast({ tone: "error", title: "Setup was skipped but not saved", description: errorMessage(e) });
      } else {
        setError(errorMessage(e));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(o) => !o && !busy && save(true)}
      size="lg"
      title="Set up your workspace"
      description="Three quick choices so reviews start with the right defaults. You can change them later in Settings."
      footer={
        <>
          <Button variant="ghost" onClick={() => save(true)} disabled={busy}>
            Skip for now
          </Button>
          <Button variant="primary" onClick={() => save(false)} loading={busy}>
            Save and continue
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        <fieldset className="space-y-2">
          <legend className="mb-2 text-[13px] font-medium text-ink">Who are you?</legend>
          <RadioCards label="Workspace mode" value={mode ?? settings.mode} onChange={setMode} options={MODE_OPTIONS} />
        </fieldset>
        <Field label="Your name" hint="Optional. Used for the greeting on Overview.">
          {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value.slice(0, 80))} autoComplete="given-name" />}
        </Field>
        <div className="space-y-1.5">
          <div className="text-[13px] font-medium text-ink">Where is your audience?</div>
          <MarketPicker value={markets ?? settings.default_markets} onChange={setMarkets} />
        </div>
        <div className="space-y-2">
          <div className="text-[13px] font-medium text-ink">Where do you post most?</div>
          <RadioCards
            label="Default platform"
            value={platform ?? settings.default_platform}
            onChange={setPlatform}
            options={platforms.map((p) => ({ value: p.id, title: p.label, description: p.description }))}
            className="sm:grid-cols-3"
          />
        </div>
        {error && (
          <Callout tone="danger" title="Not saved">
            {error}
          </Callout>
        )}
      </div>
    </Dialog>
  );
}
