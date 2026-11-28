"use client";

import { SPONSOR_LIMITS, type Sponsorship } from "@/lib/api";
import { Field, Input, Select } from "./ui";

export type { Sponsorship };
export const EMPTY_SPONSORSHIP: Sponsorship = { relationship: "unknown", sponsors: [] };

/** Trimmed, de-duplicated sponsor names, as the backend stores them. */
export function cleanSponsorship(value: Sponsorship): Sponsorship {
  const seen = new Set<string>();
  const sponsors: string[] = [];
  for (const raw of value.sponsors) {
    const name = raw.trim();
    if (name && !seen.has(name)) {
      seen.add(name);
      sponsors.push(name);
    }
  }
  return { ...value, sponsors };
}

/** The same limits as backend/app/schemas.py SponsorshipInput, checked before submitting. */
export function sponsorshipProblem(value: Sponsorship): string | null {
  const { sponsors } = cleanSponsorship(value);
  if (sponsors.length > SPONSOR_LIMITS.maxSponsors) return `List at most ${SPONSOR_LIMITS.maxSponsors} sponsors.`;
  const long = sponsors.find((s) => s.length > SPONSOR_LIMITS.maxNameLength);
  if (long) return `Sponsor names can be at most ${SPONSOR_LIMITS.maxNameLength} characters (“${long.slice(0, 24)}…” is longer).`;
  return null;
}

export const RELATIONSHIP_OPTIONS: { value: Sponsorship["relationship"]; label: string }[] = [
  { value: "unknown", label: "Not sure or not supplied" },
  { value: "none", label: "No commercial relationship" },
  { value: "paid", label: "Paid sponsorship" },
  { value: "gifted", label: "Gift or free product" },
  { value: "affiliate", label: "Affiliate commission" },
  { value: "employment", label: "Employment or family connection" },
  { value: "other", label: "Other benefit or mixed arrangements" },
];

export function SponsorshipFields({ value, onChange }: { value: Sponsorship; onChange: (value: Sponsorship) => void }) {
  const problem = sponsorshipProblem(value);
  const count = cleanSponsorship(value).sponsors.length;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Commercial relationship">
        {(p) => (
          <Select
            {...p}
            value={value.relationship}
            onChange={(e) => onChange({ ...value, relationship: e.target.value as Sponsorship["relationship"] })}
          >
            {RELATIONSHIP_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field
        label="Sponsors"
        hint={`Separate names with commas. Up to ${SPONSOR_LIMITS.maxSponsors}, ${SPONSOR_LIMITS.maxNameLength} characters each.`}
        error={problem}
        counter={count ? { value: count, max: SPONSOR_LIMITS.maxSponsors } : undefined}
      >
        {(p) => (
          <Input
            {...p}
            maxLength={1200}
            value={value.sponsors.join(",")}
            onChange={(e) => onChange({ ...value, sponsors: e.target.value.split(",") })}
            placeholder="Brand A, Brand B"
          />
        )}
      </Field>
      <p className="text-[12px] leading-4 text-ink-3 sm:col-span-2">
        These are your declarations, checked against the caption. We cannot see the platform’s paid-promotion setting or how
        long an on-screen label is shown.
      </p>
    </div>
  );
}
