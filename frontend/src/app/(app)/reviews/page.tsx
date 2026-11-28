import type { Metadata } from "next";
import { ReviewsPage } from "@/components/ReviewsPage";

export const metadata: Metadata = { title: "Reviews" };

export default function Page() {
  return <ReviewsPage />;
}
