import type { Metadata } from "next";
import { NewAnalysis } from "@/components/NewAnalysis";

export const metadata: Metadata = { title: "New review" };

export default function NewAnalysisPage() {
  return <NewAnalysis />;
}
