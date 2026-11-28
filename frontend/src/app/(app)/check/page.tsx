import type { Metadata } from "next";
import { CaptionCheckPage } from "@/components/CaptionCheckPage";

export const metadata: Metadata = { title: "Caption check" };

export default function Page() {
  return <CaptionCheckPage />;
}
