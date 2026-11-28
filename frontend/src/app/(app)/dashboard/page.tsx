import type { Metadata } from "next";
import { AnalysesDashboard } from "@/components/AnalysesDashboard";

export const metadata: Metadata = { title: "Overview" };

export default function DashboardPage() {
  return <AnalysesDashboard />;
}
