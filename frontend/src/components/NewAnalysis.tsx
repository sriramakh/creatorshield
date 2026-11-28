"use client";

import { Link2, Upload } from "lucide-react";
import { useState } from "react";
import { AiLimitCallout } from "./AiLimitCallout";
import { ImportFromAccount } from "./ImportFromAccount";
import { PageContainer } from "./shell/AppShell";
import { PageHeader, Tabs, TabsContent, TabsList, TabsTrigger } from "./ui";
import { UploadForm } from "./UploadForm";

type Source = "upload" | "account";

export function NewAnalysis() {
  const [source, setSource] = useState<Source>("upload");
  return (
    <PageContainer className="space-y-6">
      <PageHeader
        title="New review"
        description="Check a video before you publish it, or audit a post you have already published. Findings cite official platform policies."
      />
      <AiLimitCallout />
      <Tabs value={source} onValueChange={(v) => setSource(v as Source)}>
        <TabsList aria-label="Video source">
          <TabsTrigger value="upload">
            <Upload className="size-4" aria-hidden /> Upload a file
          </TabsTrigger>
          <TabsTrigger value="account">
            <Link2 className="size-4" aria-hidden /> From your account
          </TabsTrigger>
        </TabsList>
        {/* Kept mounted so switching tabs never cancels an upload in progress. */}
        <TabsContent value="upload" forceMount className="data-[state=inactive]:hidden">
          <UploadForm />
        </TabsContent>
        <TabsContent value="account">
          <ImportFromAccount />
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
