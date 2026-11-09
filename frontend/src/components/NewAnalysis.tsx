"use client";

import { useState } from "react";
import { ImportFromAccount } from "./ImportFromAccount";
import { SystemStatusBanner } from "./SystemStatusBanner";
import { UploadForm } from "./UploadForm";

type Tab = "upload" | "account";

export function NewAnalysis() {
  const [tab, setTab] = useState<Tab>("upload");
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">New analysis</h1>
        <p className="mt-1 text-sm text-slate-500">
          Check a video before you publish it, or audit a post you&apos;ve already published. Findings are reviewed against
          official platform policies.
        </p>
      </div>
      <SystemStatusBanner />
      <div role="tablist" className="inline-flex rounded-lg bg-slate-100 p-1">
        {(
          [
            ["upload", "Upload a file", "Full analysis · pre-publish"],
            ["account", "From your account", "Instagram / YouTube posts"],
          ] as const
        ).map(([key, label, sub]) => (
          <button
            key={key}
            role="tab"
            type="button"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`rounded-md px-4 py-2 text-left transition ${tab === key ? "bg-white shadow-sm" : "text-slate-600"}`}
          >
            <div className="text-sm font-semibold">{label}</div>
            <div className="text-[11px] text-slate-500">{sub}</div>
          </button>
        ))}
      </div>
      {tab === "upload" ? <UploadForm /> : <ImportFromAccount />}
    </div>
  );
}
