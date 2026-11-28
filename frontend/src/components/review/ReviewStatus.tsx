import { CircleCheck, CircleX, FileUp, LoaderCircle } from "lucide-react";
import type { AnalysisSummary } from "@/lib/api";
import { STAGE_LABEL } from "@/lib/format";
import { Badge } from "../ui";

/** Review lifecycle status: icon + word, never colour alone. */
export function ReviewStatusBadge({ a }: { a: Pick<AnalysisSummary, "status" | "stage" | "progress"> }) {
  if (a.status === "completed") return <Badge tone="success" icon={CircleCheck}>Completed</Badge>;
  if (a.status === "failed") return <Badge tone="critical" icon={CircleX}>Failed</Badge>;
  if (a.status === "awaiting_file") return <Badge tone="medium" icon={FileUp}>Needs your file</Badge>;
  return (
    <Badge tone="accent">
      <LoaderCircle className="size-3.5 animate-spin" aria-hidden />
      {STAGE_LABEL[a.stage] ?? a.stage} · <span className="tabular">{a.progress}%</span>
    </Badge>
  );
}

export const isInFlight = (a: Pick<AnalysisSummary, "status">) => a.status === "queued" || a.status === "processing";
