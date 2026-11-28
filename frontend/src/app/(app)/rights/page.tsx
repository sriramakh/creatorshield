import type { Metadata } from "next";
import { RightsLedger } from "@/components/RightsLedger";

export const metadata: Metadata = { title: "Rights ledger" };

export default function RightsPage() {
  return <RightsLedger />;
}
