"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { BriefcaseBusiness, Pencil, Plus, Trash } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, errorMessage, type Brief, type BriefInput } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useWorkspace } from "@/lib/workspace";
import { briefCounts } from "./creator/BriefPicker";
import { PageContainer } from "./shell/AppShell";
import {
  Button,
  Callout,
  Card,
  ConfirmDialog,
  DataTable,
  Drawer,
  EmptyState,
  ErrorNotice,
  Field,
  IconButton,
  Input,
  PageHeader,
  TagInput,
  Textarea,
  useToast,
  type Column,
} from "./ui";

const EMPTY: BriefInput = {
  name: "",
  brand: "",
  must_say: [],
  must_not_say: [],
  required_hashtags: [],
  required_mentions: [],
  competitors: [],
  required_disclosure: null,
  notes: "",
};

/** A worked example the user can load into the form. */
export const EXAMPLE_BRIEF: BriefInput = {
  name: "GlowUp serum launch",
  brand: "GlowUp",
  must_say: ["patch test first", "dermatologist tested"],
  must_not_say: ["cures acne", "miracle"],
  required_hashtags: ["GlowUpPartner"],
  required_mentions: ["glowup.official"],
  competitors: ["Lumina"],
  required_disclosure: "Ad",
  notes: "Reel goes live in the first week of the campaign.",
};

const LISTS: { key: keyof Pick<BriefInput, "must_say" | "must_not_say" | "required_hashtags" | "required_mentions" | "competitors">; label: string; hint: string; prefix?: string; placeholder: string }[] = [
  { key: "must_say", label: "Must say", hint: "Lines that must appear in the caption, speech or on-screen text.", placeholder: "patch test first" },
  { key: "must_not_say", label: "Must not say", hint: "Wording that must not appear anywhere.", placeholder: "cures acne" },
  { key: "required_hashtags", label: "Required hashtags", hint: "Must be in the caption or hashtags.", prefix: "#", placeholder: "BrandPartner" },
  { key: "required_mentions", label: "Required mentions", hint: "Accounts that must be tagged in the caption.", prefix: "@", placeholder: "brand.official" },
  { key: "competitors", label: "Competitors", hint: "Brands that must not be named anywhere.", placeholder: "Competitor name" },
];

export function BriefsPage() {
  const router = useRouter();
  const params = useSearchParams();
  const toast = useToast();
  const [briefs, setBriefs] = useState<Brief[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ id: string | null; input: BriefInput } | null>(null);
  const [deleting, setDeleting] = useState<Brief | null>(null);

  const load = useCallback(() => {
    api
      .briefs()
      .then((b) => {
        setBriefs(b);
        setError(null);
      })
      .catch((e: unknown) => setError(errorMessage(e)));
  }, []);
  useEffect(load, [load]);

  // /briefs?new=1 (from quick actions and the command palette) opens the form.
  const wantsNew = params.get("new") === "1";
  const [handledNew, setHandledNew] = useState(false);
  if (wantsNew && !handledNew) {
    setHandledNew(true);
    setEditing({ id: null, input: EMPTY });
  }

  const columns: Column<Brief>[] = [
    {
      key: "name",
      header: "Brief",
      sortValue: (b) => b.name.toLowerCase(),
      cell: (b) => (
        <button type="button" onClick={() => setEditing({ id: b.id, input: b })} className="text-left font-medium text-ink hover:text-accent hover:underline">
          {b.name}
        </button>
      ),
    },
    { key: "brand", header: "Brand", sortValue: (b) => b.brand.toLowerCase(), cell: (b) => <span className="text-ink-2">{b.brand || "—"}</span> },
    { key: "asks", header: "Asks for", cell: (b) => <span className="text-[13px] text-ink-2">{briefCounts(b).join(" · ") || "Nothing yet"}</span> },
    { key: "updated", header: "Updated", align: "right", sortValue: (b) => b.updated_at, cell: (b) => <span className="tabular text-[13px] whitespace-nowrap text-ink-3">{fmtDate(b.updated_at)}</span> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (b) => (
        <span className="inline-flex gap-1">
          <IconButton size="sm" label={`Edit ${b.name}`} icon={<Pencil />} onClick={() => setEditing({ id: b.id, input: b })} />
          <IconButton size="sm" label={`Delete ${b.name}`} icon={<Trash />} onClick={() => setDeleting(b)} />
        </span>
      ),
    },
  ];

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        title="Brand briefs"
        description="What each sponsor asked for. Attach a brief to a review or a caption check and every requirement is checked."
        actions={
          briefs && briefs.length > 0 ? (
            <Button variant="primary" leadingIcon={<Plus />} onClick={() => setEditing({ id: null, input: EMPTY })}>
              New brief
            </Button>
          ) : undefined
        }
      />
      {error && <ErrorNotice title="Could not load briefs" message={error} onRetry={load} />}
      <Card>
        <DataTable
          caption="Brand briefs"
          columns={columns}
          rows={briefs}
          loading={!briefs && !error}
          rowKey={(b) => b.id}
          initialSort={{ key: "updated", dir: "desc" }}
          empty={
            <EmptyState
              icon={<BriefcaseBusiness />}
              title="No briefs yet"
              description="Add what a sponsor asked you to say, tag, disclose and avoid. Try the worked example to see how it looks."
              action={
                <div className="flex flex-wrap justify-center gap-2">
                  <Button variant="primary" leadingIcon={<Plus />} onClick={() => setEditing({ id: null, input: EMPTY })}>
                    New brief
                  </Button>
                  <Button onClick={() => setEditing({ id: null, input: EXAMPLE_BRIEF })}>Load an example</Button>
                </div>
              }
            />
          }
          card={(b) => (
            <div className="flex items-start justify-between gap-3">
              <button type="button" onClick={() => setEditing({ id: b.id, input: b })} className="min-w-0 text-left">
                <div className="truncate font-medium text-ink">{b.name}</div>
                <div className="mt-0.5 text-[12px] text-ink-3">
                  {b.brand || "No brand"} · {briefCounts(b).join(" · ") || "Nothing yet"}
                </div>
              </button>
              <IconButton size="sm" label={`Delete ${b.name}`} icon={<Trash />} onClick={() => setDeleting(b)} />
            </div>
          )}
        />
      </Card>

      <BriefDrawer
        key={editing ? `${editing.id ?? "new"}-${editing.input.name}` : "closed"}
        editing={editing}
        onClose={() => {
          setEditing(null);
          if (wantsNew) router.replace("/briefs");
        }}
        onSaved={(b, created) => {
          toast({ tone: "success", title: created ? `Saved “${b.name}”` : `Updated “${b.name}”` });
          setEditing(null);
          if (wantsNew) router.replace("/briefs");
          load();
        }}
      />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete “${deleting?.name ?? ""}”?`}
        description="Reviews that used this brief keep their own copy. This cannot be undone."
        confirmLabel="Delete brief"
        onConfirm={async () => {
          if (!deleting) return;
          await api.deleteBrief(deleting.id);
          toast({ tone: "success", title: "Brief deleted" });
          load();
        }}
      />
    </PageContainer>
  );
}

function BriefDrawer({
  editing,
  onClose,
  onSaved,
}: {
  editing: { id: string | null; input: BriefInput } | null;
  onClose: () => void;
  onSaved: (b: Brief, created: boolean) => void;
}) {
  const { config } = useWorkspace();
  const maxItems = config?.limits.brief_items_max ?? 20;
  const maxItem = config?.limits.brief_item_max ?? 200;
  const [form, setForm] = useState<BriefInput>(editing?.input ?? EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = <K extends keyof BriefInput>(k: K, v: BriefInput[K]) => setForm((f) => ({ ...f, [k]: v }));

  async function save() {
    if (!editing) return;
    setBusy(true);
    setError(null);
    const body: BriefInput = {
      ...form,
      name: form.name.trim(),
      brand: form.brand.trim(),
      notes: form.notes.trim(),
      required_disclosure: form.required_disclosure?.trim() || null,
    };
    try {
      const saved = editing.id ? await api.updateBrief(editing.id, body) : await api.createBrief(body);
      onSaved(saved, !editing.id);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  }

  return (
    <Drawer
      open={editing !== null}
      onOpenChange={(o) => !o && !busy && onClose()}
      title={editing?.id ? "Edit brief" : "New brief"}
      description="Every list takes Enter or a comma between entries."
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" onClick={save} loading={busy} disabled={!form.name.trim()}>
            Save brief
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Name" required>
            {(p) => <Input {...p} value={form.name} onChange={(e) => set("name", e.target.value.slice(0, maxItem))} placeholder="Q4 launch" />}
          </Field>
          <Field label="Brand">
            {(p) => <Input {...p} value={form.brand} onChange={(e) => set("brand", e.target.value.slice(0, maxItem))} placeholder="GlowUp" />}
          </Field>
        </div>
        {LISTS.map((l) => (
          <Field key={l.key} label={l.label} hint={l.hint} counter={{ value: form[l.key].length, max: maxItems }}>
            {(p) => (
              <TagInput
                {...p}
                value={form[l.key]}
                onChange={(v) => set(l.key, v)}
                max={maxItems}
                maxLength={maxItem}
                prefix={l.prefix}
                placeholder={l.placeholder}
              />
            )}
          </Field>
        ))}
        <Field label="Required disclosure" hint="Optional. The label the caption must open with, for example “Ad” or “#ad”.">
          {(p) => (
            <Input
              {...p}
              value={form.required_disclosure ?? ""}
              onChange={(e) => set("required_disclosure", e.target.value.slice(0, maxItem))}
              placeholder="Ad"
            />
          )}
        </Field>
        <Field label="Notes" hint="For you and your team. Not checked.">
          {(p) => <Textarea {...p} rows={3} value={form.notes} onChange={(e) => set("notes", e.target.value.slice(0, 2000))} />}
        </Field>
        {error && (
          <Callout tone="danger" title="The brief was not saved">
            {error}
          </Callout>
        )}
      </div>
    </Drawer>
  );
}
