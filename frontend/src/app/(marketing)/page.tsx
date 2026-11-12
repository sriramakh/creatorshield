import type { Metadata } from "next";
import { LandingPage } from "@/components/landing/LandingPage";

export const metadata: Metadata = {
  title: "CreatorShield AI — catch the strike before you post",
  description:
    "Pre-publication policy, copyright and disclosure review for YouTube Shorts and Instagram Reels, with timestamped evidence and citations to official rules.",
};

export default function Home() {
  return <LandingPage />;
}
