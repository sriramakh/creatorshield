import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { BRAND } from "@/lib/brand";
import { cn } from "@/lib/cn";

/** Product mark + wordmark. `compact` hides the wordmark (collapsed sidebar). */
export function BrandMark({
  href = "/dashboard",
  compact = false,
  className,
  wordmarkClassName,
}: {
  href?: string;
  compact?: boolean;
  className?: string;
  wordmarkClassName?: string;
}) {
  return (
    <Link href={href} className={cn("flex min-w-0 items-center gap-2.5 rounded-[6px]", className)} aria-label={`${BRAND.name} home`}>
      <span className="flex size-8 shrink-0 items-center justify-center rounded-[8px] bg-accent text-on-accent">
        <ShieldCheck className="size-[18px]" strokeWidth={2} aria-hidden />
      </span>
      {!compact && (
        <span className={cn("truncate text-[15px] font-semibold tracking-tight text-ink", wordmarkClassName)}>
          {BRAND.wordmark[0]}
          <span className="text-accent">{BRAND.wordmark[1]}</span>
        </span>
      )}
    </Link>
  );
}
