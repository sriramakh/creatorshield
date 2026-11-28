import type { Metadata } from "next";
import { CataloguePage } from "@/components/CataloguePage";

export const metadata: Metadata = { title: "Catalogue" };

export default function Catalogue() {
  return <CataloguePage />;
}
