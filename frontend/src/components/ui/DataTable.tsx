"use client";

import Link from "next/link";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Skeleton } from "./Skeleton";

export interface Column<T> {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  /** Makes the column sortable. */
  sortValue?: (row: T) => string | number;
  align?: "left" | "right";
  className?: string;
  /** The cell that carries the row link (one per table). */
  primary?: boolean;
}

type Sort = { key: string; dir: "asc" | "desc" } | null;

/**
 * Table with sticky header, sortable columns, row hover and a whole-row link. Below 720 px it
 * becomes a list of stacked cards rendered by `card`.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  rowHref,
  card,
  loading,
  empty,
  caption,
  initialSort = null,
  maxHeight,
}: {
  columns: Column<T>[];
  rows: T[] | null;
  rowKey: (row: T) => string;
  rowHref?: (row: T) => string;
  card: (row: T) => ReactNode;
  loading?: boolean;
  empty?: ReactNode;
  caption: string;
  initialSort?: Sort;
  maxHeight?: string;
}) {
  const [sort, setSort] = useState<Sort>(initialSort);
  const sorted = useMemo(() => {
    if (!rows) return null;
    const col = sort && columns.find((c) => c.key === sort.key);
    if (!sort || !col?.sortValue) return rows;
    const get = col.sortValue;
    const out = [...rows].sort((a, b) => {
      const x = get(a);
      const y = get(b);
      return typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
    });
    return sort.dir === "asc" ? out : out.reverse();
  }, [rows, sort, columns]);

  function toggle(key: string) {
    setSort((s) => (s?.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" }));
  }

  const showEmpty = !loading && sorted && sorted.length === 0;

  return (
    <div>
      <div className={cn("scroll-thin overflow-auto max-[719px]:hidden")} style={maxHeight ? { maxHeight } : undefined}>
        <table className="w-full border-separate border-spacing-0 text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr>
              {columns.map((c) => {
                const active = sort?.key === c.key;
                return (
                  <th
                    key={c.key}
                    scope="col"
                    aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}
                    className={cn(
                      "sticky top-0 z-10 border-b border-line bg-surface-2 px-4 py-2.5 text-[12px] leading-4 font-medium whitespace-nowrap text-ink-3",
                      c.align === "right" ? "text-right" : "text-left",
                      c.className,
                    )}
                  >
                    {c.sortValue ? (
                      <button
                        type="button"
                        onClick={() => toggle(c.key)}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-[4px] hover:text-ink",
                          c.align === "right" && "flex-row-reverse",
                          active && "text-ink",
                        )}
                      >
                        {c.header}
                        {active ? (
                          sort.dir === "asc" ? <ArrowUp className="size-3.5" aria-hidden /> : <ArrowDown className="size-3.5" aria-hidden />
                        ) : (
                          <ChevronsUpDown className="size-3.5 opacity-60" aria-hidden />
                        )}
                      </button>
                    ) : (
                      c.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {loading &&
              !sorted &&
              [0, 1, 2, 3].map((i) => (
                <tr key={`s${i}`}>
                  {columns.map((c) => (
                    <td key={c.key} className="border-b border-line px-4 py-3.5">
                      <Skeleton className="h-4 w-3/4" />
                    </td>
                  ))}
                </tr>
              ))}
            {sorted?.map((row) => (
              <tr key={rowKey(row)} className={cn("group", rowHref && "relative hover:bg-surface-2")}>
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={cn(
                      "border-b border-line px-4 py-3 align-middle group-last:border-b-0",
                      c.align === "right" && "text-right",
                      c.className,
                    )}
                  >
                    {c.primary && rowHref ? (
                      <Link
                        href={rowHref(row)}
                        className="block after:absolute after:inset-0 after:content-[''] focus-visible:outline-none focus-visible:after:rounded-[4px] focus-visible:after:outline-2 focus-visible:after:outline-offset-[-2px] focus-visible:after:outline-[var(--focus)]"
                      >
                        {c.cell(row)}
                      </Link>
                    ) : (
                      c.cell(row)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {showEmpty && empty}
      </div>

      <ul className="divide-y divide-line min-[720px]:hidden" aria-label={caption}>
        {loading &&
          !sorted &&
          [0, 1, 2].map((i) => (
            <li key={i} className="space-y-2 px-4 py-4">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-1/3" />
            </li>
          ))}
        {sorted?.map((row) => (
          <li key={rowKey(row)}>
            {rowHref ? (
              <Link href={rowHref(row)} className="block px-4 py-3.5 hover:bg-surface-2 focus-visible:outline-offset-[-2px]">
                {card(row)}
              </Link>
            ) : (
              <div className="px-4 py-3.5">{card(row)}</div>
            )}
          </li>
        ))}
      </ul>
      {showEmpty && <div className="min-[720px]:hidden">{empty}</div>}
    </div>
  );
}
