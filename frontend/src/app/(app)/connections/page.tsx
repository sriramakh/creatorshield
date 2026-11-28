import type { Metadata } from "next";
import { Suspense } from "react";
import { ConnectionsPage } from "@/components/ConnectionsPage";
import { Skeleton } from "@/components/ui";

export const metadata: Metadata = { title: "Connected accounts" };

export default function Page() {
  // useSearchParams() reads request-time data, so it must sit inside <Suspense>.
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <ConnectionsPage />
    </Suspense>
  );
}
