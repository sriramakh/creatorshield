import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { Fragment } from "react";

export function Breadcrumbs({ items }: { items: { href?: string; label: string }[] }) {
  if (items.length === 0) return null;
  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="flex min-w-0 items-center gap-1.5 text-sm">
        {items.map((item, i) => {
          const last = i === items.length - 1;
          return (
            <Fragment key={`${item.label}-${i}`}>
              {i > 0 && (
                <li aria-hidden className="text-ink-3">
                  <ChevronRight className="size-3.5" />
                </li>
              )}
              <li className="min-w-0 truncate">
                {item.href && !last ? (
                  <Link href={item.href} className="text-ink-3 hover:text-ink">
                    {item.label}
                  </Link>
                ) : (
                  <span aria-current={last ? "page" : undefined} className={last ? "font-medium text-ink" : "text-ink-3"}>
                    {item.label}
                  </span>
                )}
              </li>
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
