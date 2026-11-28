"use client";

import { CircleCheck, Clock, Download, Plus, Scale, Search, Trash } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, errorMessage, type ConnectedPlatform, type RightsKind, type RightsRecord } from "@/lib/api";
import { fmtDay } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace";
import { PageContainer } from "./shell/AppShell";
import {
  Badge,
  Button,
  Callout,
  Card,
  Checkbox,
  ConfirmDialog,
  Drawer,
  EmptyState,
  ErrorNotice,
  Field,
  FilePicker,
  IconButton,
  Input,
  PageHeader,
  Select,
  Skeleton,
  Textarea,
  buttonClasses,
  useToast,
  type BadgeTone,
} from "./ui";

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
    label: "Footage, stock or broadcast licence",
    help: "Covers broadcaster or studio branding and web matches on these names or domains.",
    placeholder: "Broadcaster, studio, stock site or domain",
  },
  {
    value: "brand_agreement",
    label: "Paid brand agreement",
    help: "Videos that mention this brand without #ad or a paid-partnership label get a high-severity disclosure finding.",
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

const RECORD_STATUS: Record<RightsRecord["status"], { label: string; tone: BadgeTone; icon: typeof CircleCheck }> = {
  active: { label: "Active", tone: "success", icon: CircleCheck },
  expired: { label: "Expired", tone: "medium", icon: Clock },
  not_started: { label: "Not started", tone: "neutral", icon: Clock },
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

export function RightsLedger() {
  const [records, setRecords] = useState<RightsRecord[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState("");

  const load = useCallback(() => {
    api
      .rights()
      .then((r) => {
        setRecords(r);
        setLoadError(null);
        // Links from a review (/rights#record-…) land here before the records exist.
        const target = window.location.hash.slice(1);
        if (target)
          requestAnimationFrame(() => {
            const el = document.getElementById(target);
            if (!el) return;
            el.scrollIntoView({ block: "center" });
            el.classList.add("highlight-flash");
          });
      })
      .catch((e: unknown) => setLoadError(errorMessage(e)));
  }, []);
  useEffect(load, [load]);

  const q = query.trim().toLowerCase();
  const shown = (records ?? []).filter(
    (r) => !q || `${r.counterparty} ${r.kind_label} ${r.match_terms.join(" ")} ${r.client_label ?? ""} ${r.reference}`.toLowerCase().includes(q),
  );

  return (
    <PageContainer className="max-w-5xl space-y-6">
      <PageHeader
        title="Rights ledger"
        description="Record what you own, have licensed or agreed. Reviews mark matching content as covered, and evidence packs include these records and proofs. These are your own records, not verified with the other party."
        actions={
          records && records.length > 0 ? (
            <Button variant="primary" leadingIcon={<Plus />} onClick={() => setAdding(true)}>
              Add record
            </Button>
          ) : undefined
        }
      />
      {loadError && <ErrorNotice title="Could not load the rights ledger" message={loadError} onRetry={load} />}

      {records && records.length > 0 && (
        <div className="relative w-full sm:w-80">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
          <Input
            type="search"
            aria-label="Search records"
            placeholder="Search names, terms, clients"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-8"
          />
        </div>
      )}

      <section aria-label="Records" className="space-y-3">
        {!records && !loadError && [0, 1, 2].map((i) => <Skeleton key={i} className="h-32 w-full rounded-[10px]" />)}
        {records && records.length === 0 && (
          <Card>
            <EmptyState
              icon={<Scale />}
              title="No records yet"
              description="Add the permissions, licences and brand deals you hold so reviews can tell covered content from content that still needs clearing."
              action={
                <Button variant="primary" leadingIcon={<Plus />} onClick={() => setAdding(true)}>
                  Add record
                </Button>
              }
            />
          </Card>
        )}
        {records && records.length > 0 && shown.length === 0 && <p className="text-sm text-ink-3">No records match “{query}”.</p>}
        {shown.map((r) => (
          <RecordCard key={r.id} record={r} onChange={load} />
        ))}
      </section>

      <AddRecordDrawer open={adding} onOpenChange={setAdding} onAdded={load} />
    </PageContainer>
  );
}

function RecordCard({ record: r, onChange }: { record: RightsRecord; onChange: () => void }) {
  const toast = useToast();
  const [confirm, setConfirm] = useState(false);
  const st = RECORD_STATUS[r.status];

  return (
    <Card id={`record-${r.id}`} className="scroll-mt-24 p-4" label={`${r.kind_label}: ${r.counterparty}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[12px] text-ink-3">{r.kind_label}</div>
          <h2 className="text-[15px] font-semibold text-ink">{r.counterparty}</h2>
        </div>
        <div className="flex items-center gap-1">
          <Badge tone={st.tone} icon={st.icon}>
            {st.label}
          </Badge>
          <IconButton size="sm" label={`Delete record for ${r.counterparty}`} icon={<Trash />} onClick={() => setConfirm(true)} />
        </div>
      </div>

      {r.match_terms.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {r.match_terms.map((t) => (
            <span key={t} className="rounded-[4px] bg-surface-3 px-1.5 py-0.5 font-mono text-[12px] text-ink-2">
              {t}
            </span>
          ))}
        </div>
      )}

      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[13px] sm:grid-cols-[auto_1fr_auto_1fr]">
        <dt className="text-ink-3">Platforms</dt>
        <dd className="text-ink">
          {r.platforms.length ? r.platforms.map((p) => PLATFORMS.find((x) => x.value === p)?.label ?? p).join(", ") : "All platforms"}
        </dd>
        <dt className="text-ink-3">Valid</dt>
        <dd className={r.status === "expired" ? "font-medium text-medium-fg" : "text-ink"}>
          {r.valid_from ? fmtDay(r.valid_from) : "Any time"} – {r.valid_until ? fmtDay(r.valid_until) : "no end date"}
        </dd>
        {r.client_label && (
          <>
            <dt className="text-ink-3">Client</dt>
            <dd className="text-ink">{r.client_label}</dd>
          </>
        )}
        {r.reference && (
          <>
            <dt className="text-ink-3">Reference</dt>
            <dd className="break-words text-ink">{r.reference}</dd>
          </>
        )}
      </dl>
      {r.notes && <p className="mt-2 text-[13px] whitespace-pre-line text-ink-2">{r.notes}</p>}

      <div className="mt-3 border-t border-line pt-3 text-[13px]">
        {r.has_proof ? (
          <a href={api.proofUrl(r.id)} className={buttonClasses("link", "sm", "gap-1.5")}>
            <Download aria-hidden /> Download proof
          </a>
        ) : (
          <span className="text-ink-3">No proof attached</span>
        )}
      </div>
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={`Delete the record for ${r.counterparty}?`}
        description="Completed reviews are re-checked without it, and its proof file is deleted. This cannot be undone."
        confirmLabel="Delete record"
        onConfirm={async () => {
          await api.removeRight(r.id);
          toast({ tone: "success", title: "Record deleted" });
          onChange();
        }}
      />
    </Card>
  );
}

function AddRecordDrawer({ open, onOpenChange, onAdded }: { open: boolean; onOpenChange: (o: boolean) => void; onAdded: () => void }) {
  const toast = useToast();
  const { agency } = useWorkspace();
  const [form, setForm] = useState(EMPTY);
  const [proof, setProof] = useState<File | null>(null);
  const [proofError, setProofError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const kind = KINDS.find((k) => k.value === form.kind) ?? KINDS[0];
  const set = <K extends keyof typeof EMPTY>(key: K, value: (typeof EMPTY)[K]) => setForm((f) => ({ ...f, [key]: value }));

  function close(next: boolean) {
    if (busy) return;
    if (!next) {
      setForm(EMPTY);
      setProof(null);
      setProofError(null);
      setError(null);
    }
    onOpenChange(next);
  }

  function pickProof(f: File | undefined) {
    setProofError(null);
    if (f && f.size > PROOF_MAX_MB * 1024 * 1024) {
      setProofError(`The proof file is larger than ${PROOF_MAX_MB} MB.`);
      setProof(null);
      return;
    }
    setProof(f ?? null);
  }

  async function submit() {
    setBusy(true);
    setError(null);
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
      toast({ tone: "success", title: `Added “${rec.counterparty}”`, description: "Completed reviews were re-checked against the ledger." });
      setBusy(false);
      onAdded();
      setForm(EMPTY);
      setProof(null);
      onOpenChange(false);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  }

  return (
    <Drawer
      open={open}
      onOpenChange={close}
      title="Add a record"
      description="A permission, licence, brand deal or your own channel."
      footer={
        <>
          <Button onClick={() => close(false)} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} loading={busy} disabled={!form.counterparty.trim()}>
            Save record
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Type" hint={kind.help}>
          {(p) => (
            <Select {...p} value={form.kind} onChange={(e) => set("kind", e.target.value as RightsKind)}>
              {KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Account, brand, label or licensor" required>
          {(p) => <Input {...p} value={form.counterparty} onChange={(e) => set("counterparty", e.target.value.slice(0, 200))} />}
        </Field>
        <Field label="Match terms" hint="Comma or one per line: @handles, brand or label names, domains. Defaults to the name above.">
          {(p) => (
            <Textarea {...p} value={form.matchTerms} onChange={(e) => set("matchTerms", e.target.value.slice(0, 2000))} rows={2} placeholder={kind.placeholder} />
          )}
        </Field>
        <fieldset className="space-y-1.5">
          <legend className="text-[13px] font-medium text-ink">Platforms</legend>
          <div className="flex gap-5">
            {PLATFORMS.map((p) => (
              <Checkbox
                key={p.value}
                label={p.label}
                checked={form.platforms.includes(p.value)}
                onChange={(e) => set("platforms", e.target.checked ? [...form.platforms, p.value] : form.platforms.filter((x) => x !== p.value))}
              />
            ))}
          </div>
          <p className="text-[12px] text-ink-3">Leave both unticked to cover all platforms.</p>
        </fieldset>
        {agency && (
          <Field label="Client or account" hint="Optional. The record applies only to reviews with this client label.">
            {(p) => <Input {...p} value={form.clientLabel} onChange={(e) => set("clientLabel", e.target.value.slice(0, 100))} />}
          </Field>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Valid from">
            {(p) => <Input {...p} type="date" value={form.validFrom} onChange={(e) => set("validFrom", e.target.value)} />}
          </Field>
          <Field label="Valid until">
            {(p) => <Input {...p} type="date" value={form.validUntil} onChange={(e) => set("validUntil", e.target.value)} />}
          </Field>
        </div>
        <Field label="Reference">
          {(p) => (
            <Input
              {...p}
              value={form.reference}
              onChange={(e) => set("reference", e.target.value.slice(0, 300))}
              placeholder="Licence ID, contract number or email date"
            />
          )}
        </Field>
        <Field label="Notes">
          {(p) => <Textarea {...p} value={form.notes} onChange={(e) => set("notes", e.target.value.slice(0, 2000))} rows={2} />}
        </Field>
        <Field label="Proof" hint={`Optional. PDF, PNG or JPEG up to ${PROOF_MAX_MB} MB: a contract, licence or screenshot of the agreement.`} error={proofError}>
          {(p) => <FilePicker {...p} accept={PROOF_ACCEPT} files={proof ? [proof] : []} onFiles={(f) => pickProof(f[0])} />}
        </Field>
        {error && (
          <Callout tone="danger" title="The record was not saved">
            {error}
          </Callout>
        )}
      </div>
    </Drawer>
  );
}
