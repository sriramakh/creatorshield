import { Suspense } from "react";
import { AnalysisView } from "@/components/review/AnalysisView";
import { Skeleton } from "@/components/ui";

export default function AnalysisPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full rounded-xl" />}>
      <AnalysisView />
    </Suspense>
  );
}
