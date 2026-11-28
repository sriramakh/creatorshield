import { cn } from "@/lib/cn";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={cn("skeleton rounded-[6px]", className)} />;
}
