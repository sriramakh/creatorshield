"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import { CornerDownLeft, Search } from "lucide-react";
import { useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Kbd } from "./Kbd";

export interface Command {
  id: string;
  label: string;
  group: string;
  icon?: ReactNode;
  keywords?: string;
  hint?: ReactNode;
  onSelect: () => void;
}

function matches(c: Command, query: string) {
  const hay = `${c.label} ${c.keywords ?? ""} ${c.group}`.toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => hay.includes(word));
}

/** Ctrl/⌘ K palette: a filterable list of commands (combobox + listbox, arrow keys, Enter). */
export function CommandPalette({
  open,
  onOpenChange,
  commands,
  footer,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  commands: Command[];
  footer?: ReactNode;
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  const visible = useMemo(() => commands.filter((c) => matches(c, query)), [commands, query]);
  const groups = useMemo(() => {
    const out: { name: string; items: { command: Command; index: number }[] }[] = [];
    visible.forEach((command, index) => {
      let g = out.find((x) => x.name === command.group);
      if (!g) {
        g = { name: command.group, items: [] };
        out.push(g);
      }
      g.items.push({ command, index });
    });
    return out;
  }, [visible]);
  const current = Math.min(active, Math.max(visible.length - 1, 0));

  function close() {
    onOpenChange(false);
  }

  function run(c: Command | undefined) {
    if (!c) return;
    close();
    c.onSelect();
  }

  function move(to: number) {
    const n = visible.length;
    if (!n) return;
    const next = (to + n) % n;
    setActive(next);
    requestAnimationFrame(() =>
      listRef.current?.querySelector(`[data-index="${next}"]`)?.scrollIntoView({ block: "nearest" }),
    );
  }

  function onKeyDown(e: KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      move(current + 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      move(current - 1);
    } else if (e.key === "Home") {
      e.preventDefault();
      move(0);
    } else if (e.key === "End") {
      e.preventDefault();
      move(visible.length - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      run(visible[current]);
    }
  }

  return (
    <RadixDialog.Root
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          setQuery("");
          setActive(0);
        }
        onOpenChange(o);
      }}
    >
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="anim-fade fixed inset-0 z-50 bg-overlay" />
        <RadixDialog.Content
          aria-describedby={undefined}
          className="anim-pop fixed top-[12vh] left-1/2 z-50 w-[calc(100vw-24px)] max-w-xl -translate-x-1/2 overflow-hidden rounded-[14px] border border-line bg-surface shadow-[var(--shadow-dialog)]"
        >
          <RadixDialog.Title className="sr-only">Command palette</RadixDialog.Title>
          <div className="flex items-center gap-2.5 border-b border-line px-4">
            <Search className="size-4 shrink-0 text-ink-3" aria-hidden />
            <input
              autoFocus
              role="combobox"
              aria-expanded
              aria-controls={listId}
              aria-autocomplete="list"
              aria-activedescendant={visible[current] ? `${listId}-${current}` : undefined}
              aria-label="Search commands"
              placeholder="Search pages, reviews and actions"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setActive(0);
              }}
              onKeyDown={onKeyDown}
              className="h-12 w-full bg-transparent text-[15px] text-ink outline-none placeholder:text-ink-3 focus-visible:outline-none"
            />
            <Kbd>Esc</Kbd>
          </div>
          <div ref={listRef} id={listId} role="listbox" aria-label="Commands" className="scroll-thin max-h-[min(420px,60vh)] overflow-y-auto p-1.5">
            {visible.length === 0 && <p className="px-3 py-8 text-center text-sm text-ink-3">Nothing matches “{query}”.</p>}
            {groups.map((g) => (
              <div key={g.name} role="group" aria-label={g.name} className="py-1">
                <div className="px-2.5 pt-1 pb-1.5 text-[11px] leading-4 font-semibold tracking-[0.06em] text-ink-3 uppercase">{g.name}</div>
                {g.items.map(({ command, index }) => (
                  <div
                    key={command.id}
                    id={`${listId}-${index}`}
                    data-index={index}
                    role="option"
                    aria-selected={index === current}
                    onMouseMove={() => index !== current && setActive(index)}
                    onClick={() => run(command)}
                    className={cn(
                      "flex h-10 cursor-pointer items-center gap-3 rounded-[6px] px-2.5 text-sm text-ink [&_svg]:size-4 [&_svg]:text-ink-3",
                      index === current && "bg-surface-3",
                    )}
                  >
                    {command.icon}
                    <span className="min-w-0 flex-1 truncate">{command.label}</span>
                    {command.hint && <span className="shrink-0 text-[12px] text-ink-3">{command.hint}</span>}
                    {index === current && <CornerDownLeft className="shrink-0" aria-hidden />}
                  </div>
                ))}
              </div>
            ))}
          </div>
          {footer && <div className="flex items-center gap-3 border-t border-line px-4 py-2 text-[12px] text-ink-3">{footer}</div>}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
