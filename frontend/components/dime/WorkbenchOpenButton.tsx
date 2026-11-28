"use client";

import { ArrowUpRight } from "lucide-react";
import type { DimeArtifact } from "@/lib/dime-stream";
import { openCapScenarioInWorkbench, openTradeInWorkbench } from "@/lib/workbench-navigation";

export function WorkbenchOpenButton({ artifact }: { artifact: DimeArtifact }) {
  if (artifact.kind === "trade_verdict" && artifact.construction) {
    const construction = artifact.construction;
    return (
      <button
        className="inline-flex items-center gap-1 text-[12px] text-ink-3 transition-colors hover:text-ink"
        onClick={() => openTradeInWorkbench(construction)}
      >
        Open in war room
        <ArrowUpRight width={12} height={12} aria-hidden="true" />
      </button>
    );
  }
  if (artifact.kind === "cap_summary" && artifact.construction) {
    const construction = artifact.construction;
    return (
      <button
        className="inline-flex items-center gap-1 text-[12px] text-ink-3 transition-colors hover:text-ink"
        onClick={() => openCapScenarioInWorkbench(construction)}
      >
        Open in cap sheet
        <ArrowUpRight width={12} height={12} aria-hidden="true" />
      </button>
    );
  }
  return null;
}
