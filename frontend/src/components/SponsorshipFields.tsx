"use client";

export type Sponsorship = {
  relationship: "unknown" | "none" | "paid" | "gifted" | "affiliate" | "employment" | "other";
  sponsors: string[];
};
export const EMPTY_SPONSORSHIP: Sponsorship = { relationship: "unknown", sponsors: [] };

export function SponsorshipFields({ value, onChange }: {
  value: Sponsorship; onChange: (value: Sponsorship) => void;
}) {
  return <fieldset className="space-y-3 rounded-lg border border-slate-200 p-3">
    <legend className="px-1 text-sm font-semibold">Sponsorship details</legend>
    <label className="block text-sm">Commercial relationship
      <select className="mt-1 block w-full rounded border p-2" value={value.relationship}
        onChange={e => onChange({ ...value, relationship: e.target.value as Sponsorship["relationship"] })}>
        <option value="unknown">Not sure / not supplied</option>
        <option value="none">No commercial relationship</option>
        <option value="paid">Paid sponsorship</option>
        <option value="gifted">Gift or free product</option>
        <option value="affiliate">Affiliate commission</option>
        <option value="employment">Employment or family connection</option>
        <option value="other">Other benefit or mixed arrangements</option>
      </select>
    </label>
    <label className="block text-sm">Sponsor names, separated by commas
      <input className="mt-1 block w-full rounded border p-2" maxLength={1000}
        value={value.sponsors.join(",")}
        onChange={e => onChange({ ...value, sponsors: e.target.value.split(",") })}
        placeholder="Brand A, Brand B" />
    </label>
    <p className="text-xs text-slate-500">These are your declarations. Each sponsor needs review. We cannot verify the platform’s paid-promotion setting or on-screen label duration.</p>
  </fieldset>;
}
