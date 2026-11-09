"use client";

import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { api, type ConnectedPlatform, type RightsKind, type RightsRecord } from "@/lib/api";
import { fmtDay } from "@/lib/format";
import { DownloadIcon, TrashIcon } from "./icons";
import { Banner, Card, Skeleton } from "./ui";

const KINDS: { value: RightsKind; label: string; help: string; placeholder: string }[] = [
  {
    value: "creator_permission",
    label: "Permission from a creator",
    help: "Covers their @handle on screen and their footage in your catalogue.",
    placeholder: "@their_handle",
  },
  {
    value: "music_license",
    label: "Music licence or subscription",
    help: "Matches identified songs by artist, label or title.",
    placeholder: "Artist, label or song title",
  },
  {
    value: "footage_license",
    label: "Footage / stock / broadcast licence",
    help: "Covers broadcaster/studio branding and web matches on these names or domains.",
    placeholder: "Broadcaster, studio, stock site or domain",
  },
  {
    value: "brand_agreement",
    label: "Paid brand agreement",
    help: "Videos that mention this brand without #ad/paid-partnership get a high-severity disclosure finding.",
    placeholder: "Brand name, @handle or domain",
  },
  {
    value: "own_channel",
    label: "Own channel or brand",
    help: "Your other handles, brand names and domains.",
    placeholder: "@your_other_handle, yourbrand.com",
  },
];

const PLATFORMS: { value: ConnectedPlatform; label: string }[] = [
  { value: "youtube", label: "YouTube" },
  { value: "instagram", label: "Instagram" },
];

const RECORD_STATUS: Record<RightsRecord["status"], { label: string; className: string }> = {
  active: { label: "Active", className: "bg-emerald-50 text-emerald-800 ring-emerald-200" },
  expired: { label: "Expired", className: "bg-amber-50 text-amber-800 ring-amber-200" },
  not_started: { label: "Not started", className: "bg-slate-100 text-slate-700 ring-slate-200" },
};

const PROOF_ACCEPT = ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg";
const PROOF_MAX_MB = 10;

const EMPTY = {
  kind: "creator_permission" as RightsKind,
  counterparty: "",
  matchTerms: "",
  platforms: [] as ConnectedPlatform[],
  clientLabel: "",
  validFrom: "",
  validUntil: "",
  reference: "",
  notes: "",
};

const inputClass =
  "mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100";

export function RightsLedger() {
  const [records, setRecords] = useState<RightsRecord[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .rights()
      .then((r) => {
        setRecords(r);
        setLoadError(null);
      })
      .catch((e: Error) => setLoadError(e.message));
  }, []);
  useEffect(load, [load]);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Rights ledger</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-500">
          Record what you own, licensed or agreed. Reviews mark matching content as covered, and evidence packs include
          these records and proofs. Your own record — not verified with the other party.
        </p>
      </div>
      {loadError && <Banner tone="danger" title="Could not load the rights ledger">{loadError}</Banner>}

      <div className="grid items-start gap-6 lg:grid-cols-[1fr_380px]">
        <section aria-label="Records" className="min-w-0 space-y-3">
          {!records && !loadError && [0, 1].map((i) => <Skeleton key={i} className="h-28 w-full" />)}
          {records && records.length === 0 && (
            <Card className="p-6 text-sm text-slate-600">
              No records yet. Add the permissions, licences and brand deals you hold so reviews can tell covered content
              from content that still needs clearing.
            </Card>
          )}
          {records?.map((r) => <RecordCard key={r.id} record={r} onChange={load} />)}
        </section>
        <div className="lg:sticky lg:top-24">
          <AddRecordForm onAdded={load} />
        </div>
      </div>
    </div>
  );
}

function RecordCard({ record: r, onChange }: { record: RightsRecord; onChange: () => void }) {
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const st = RECORD_STATUS[r.status];

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await api.removeRight(r.id);
      onChange();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <Card className="p-4" label={`${r.kind_label}: ${r.counterparty}`}>
      <div id={`record-${r.id}`} className="flex scroll-mt-24 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{r.kind_label}</div>
          <h2 className="mt-0.5 text-[15px] font-semibold text-slate-900">{r.counterparty}</h2>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${st.className}`}>{st.label}</span>
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {r.match_terms.map((t) => (
          <span key={t} className="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700">{t}</span>
        ))}
      </div>

      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
        <dt className="text-slate-500">Platforms</dt>
        <dd className="text-slate-700">
          {r.platforms.length ? r.platforms.map((p) => PLATFORMS.find((x) => x.value === p)?.label ?? p).join(", ") : "All platforms"}
        </dd>
        {r.client_label && (
          <>
            <dt className="text-slate-500">Client</dt>
            <dd className="text-slate-700">{r.client_label}</dd>
          </>
        )}
        <dt className="text-slate-500">Valid</dt>
        <dd className={r.status === "expired" ? "font-medium text-amber-800" : "text-slate-700"}>
          {r.valid_from ? fmtDay(r.valid_from) : "Any time"} – {r.valid_until ? fmtDay(r.valid_until) : "no end date"}
        </dd>
        {r.reference && (
          <>
            <dt className="text-slate-500">Reference</dt>
            <dd className="break-words text-slate-700">{r.reference}</dd>
          </>
        )}
        {r.notes && (
          <>
            <dt className="text-slate-500">Notes</dt>
            <dd className="whitespace-pre-line break-words text-slate-700">{r.notes}</dd>
          </>
        )}
      </dl>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3 text-xs">
        {r.has_proof ? (
          <a href={api.proofUrl(r.id)} className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline">
            <DownloadIcon className="h-3.5 w-3.5" /> Proof
          </a>
        ) : (
          <span className="text-slate-400">No proof attached</span>
        )}
        {confirm ? (
          <span className="flex items-center gap-1">
            <span className="text-red-800">Delete this record?</span>
            <button
              type="button"
              disabled={busy}
              onClick={remove}
              className="rounded bg-red-600 px-2 py-1 font-semibold text-white hover:bg-red-700 disabled:bg-red-300"
            >
              Delete
            </button>
            <button type="button" onClick={() => setConfirm(false)} className="px-1 text-slate-600">
              Cancel
            </button>
          </span>
        ) : (
          <button
            type="button"
            onClick={() => setConfirm(true)}
            className="inline-flex items-center gap-1 font-medium text-slate-500 hover:text-red-700"
          >
            <TrashIcon className="h-3.5 w-3.5" /> Delete
          </button>
        )}
      </div>
      {error && <p className="mt-2 text-xs font-medium text-red-700" role="alert">{error}</p>}
    </Card>
  );
}

function AddRecordForm({ onAdded }: { onAdded: () => void }) {
  const [form, setForm] = useState(EMPTY);
  const [proof, setProof] = useState<File | null>(null);
  const [fileKey, setFileKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [added, setAdded] = useState<string | null>(null);

  // Routes stay mounted (hidden) after navigation; start clean on the next visit.
  useLayoutEffect(
    () => () => {
      setForm(EMPTY);
      setProof(null);
      setFileKey((k) => k + 1);
      setError(null);
      setAdded(null);
    },
    [],
  );

  const kind = KINDS.find((k) => k.value === form.kind) ?? KINDS[0];
  const set = <K extends keyof typeof EMPTY>(key: K, value: (typeof EMPTY)[K]) => setForm((f) => ({ ...f, [key]: value }));

  function pickProof(f: File | undefined) {
    setError(null);
    if (f && f.size > PROOF_MAX_MB * 1024 * 1024) {
      setError(`Proof file is larger than ${PROOF_MAX_MB} MB.`);
      setProof(null);
      setFileKey((k) => k + 1);
      return;
    }
    setProof(f ?? null);
  }

  async function submit() {
    setBusy(true);
    setError(null);
    setAdded(null);
    const body = new FormData();
    body.append("kind", form.kind);
    body.append("counterparty", form.counterparty.trim());
    body.append("match_terms", form.matchTerms);
    body.append("platforms", form.platforms.join(","));
    body.append("client_label", form.clientLabel.trim());
    body.append("valid_from", form.validFrom);
    body.append("valid_until", form.validUntil);
    body.append("reference", form.reference.trim());
    body.append("notes", form.notes.trim());
    if (proof) body.append("proof", proof);
    try {
      const rec = await api.addRight(body);
      setForm(EMPTY);
      setProof(null);
      setFileKey((k) => k + 1);
      setAdded(`Added “${rec.counterparty}”. Completed reviews were re-checked against the ledger.`);
      onAdded();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="space-y-4 p-5" label="Add a record">
      <h2 className="text-sm font-semibold">Add a record</h2>

      <div>
        <label htmlFor="rights-kind" className="text-xs font-semibold text-slate-700">Type</label>
        <select
          id="rights-kind"
          value={form.kind}
          onChange={(e) => set("kind", e.target.value as RightsKind)}
          className={`${inputClass} bg-white`}
        >
          {KINDS.map((k) => (
            <option key={k.value} value={k.value}>{k.label}</option>
          ))}
        </select>
        <p className="mt-1 text-[11px] text-slate-500">{kind.help}</p>
      </div>

      <div>
        <label htmlFor="rights-counterparty" className="text-xs font-semibold text-slate-700">Account, brand, label or licensor</label>
        <input
          id="rights-counterparty"
          value={form.counterparty}
          onChange={(e) => set("counterparty", e.target.value.slice(0, 200))}
          className={inputClass}
        />
      </div>

      <div>
        <label htmlFor="rights-terms" className="text-xs font-semibold text-slate-700">Match terms</label>
        <textarea
          id="rights-terms"
          value={form.matchTerms}
          onChange={(e) => set("matchTerms", e.target.value.slice(0, 2000))}
          rows={2}
          placeholder={kind.placeholder}
          className={`${inputClass} resize-y`}
        />
        <p className="mt-1 text-[11px] text-slate-500">
          Comma or one per line: @handles, brand or label names, domains. Defaults to the name above.
        </p>
      </div>

      <fieldset>
        <legend className="text-xs font-semibold text-slate-700">Platforms</legend>
        <div className="mt-1 flex gap-4">
          {PLATFORMS.map((p) => (
            <label key={p.value} className="flex items-center gap-1.5 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={form.platforms.includes(p.value)}
                onChange={(e) =>
                  set("platforms", e.target.checked ? [...form.platforms, p.value] : form.platforms.filter((x) => x !== p.value))
                }
                className="h-4 w-4 accent-brand-600"
              />
              {p.label}
            </label>
          ))}
        </div>
        <p className="mt-1 text-[11px] text-slate-500">Leave both unticked to cover all platforms.</p>
      </fieldset>

      <div>
        <label htmlFor="rights-client" className="text-xs font-semibold text-slate-700">Client / account (optional)</label>
        <input
          id="rights-client"
          value={form.clientLabel}
          onChange={(e) => set("clientLabel", e.target.value.slice(0, 100))}
          className={inputClass}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="rights-from" className="text-xs font-semibold text-slate-700">Valid from</label>
          <input id="rights-from" type="date" value={form.validFrom} onChange={(e) => set("validFrom", e.target.value)} className={inputClass} />
        </div>
        <div>
          <label htmlFor="rights-until" className="text-xs font-semibold text-slate-700">Valid until</label>
          <input id="rights-until" type="date" value={form.validUntil} onChange={(e) => set("validUntil", e.target.value)} className={inputClass} />
        </div>
      </div>

      <div>
        <label htmlFor="rights-reference" className="text-xs font-semibold text-slate-700">Reference</label>
        <input
          id="rights-reference"
          value={form.reference}
          onChange={(e) => set("reference", e.target.value.slice(0, 300))}
          placeholder="Licence ID, contract number or email date"
          className={inputClass}
        />
      </div>

      <div>
        <label htmlFor="rights-notes" className="text-xs font-semibold text-slate-700">Notes</label>
        <textarea
          id="rights-notes"
          value={form.notes}
          onChange={(e) => set("notes", e.target.value.slice(0, 2000))}
          rows={2}
          className={`${inputClass} resize-y`}
        />
      </div>

      <div>
        <label htmlFor="rights-proof" className="text-xs font-semibold text-slate-700">Proof (optional)</label>
        <input
          key={fileKey}
          id="rights-proof"
          type="file"
          accept={PROOF_ACCEPT}
          onChange={(e) => pickProof(e.target.files?.[0])}
          className="mt-1 block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-slate-800"
        />
        <p className="mt-1 text-[11px] text-slate-500">PDF, PNG or JPEG up to {PROOF_MAX_MB} MB — a contract, licence or screenshot of the agreement.</p>
      </div>

      <div aria-live="polite">
        {error && <p className="text-sm font-medium text-red-700">{error}</p>}
        {added && <p className="text-sm font-medium text-emerald-700">{added}</p>}
      </div>

      <button
        type="button"
        onClick={submit}
        disabled={busy || !form.counterparty.trim()}
        className="inline-flex w-full items-center justify-center rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {busy ? "Saving…" : "Add record"}
      </button>
    </Card>
  );
}
