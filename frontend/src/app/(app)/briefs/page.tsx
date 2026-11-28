import type { Metadata } from "next";
import { Suspense } from "react";
import { BriefsPage } from "@/components/BriefsPage";
import { Skeleton } from "@/components/ui";

export const metadata: Metadata = { title: "Brand briefs" };

export default function Page() {
  // useSearchParams() (?new=1) is request-time data, so it sits inside <Suspense>.
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full rounded-[10px]" />}>
      <BriefsPage />
    </Suspense>
  );
}
