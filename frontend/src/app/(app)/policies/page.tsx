import type { Metadata } from "next";
import { PolicyLibrary } from "@/components/PolicyLibrary";

export const metadata: Metadata = { title: "Policy library" };

export default function PoliciesPage() {
  return <PolicyLibrary />;
}
