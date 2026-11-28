"use client";

import { OpenNewWindow } from "iconoir-react";
import { Button } from "@/components/ds/Button";
import type { DimeArtifact } from "@/lib/dime-stream";
import { navigateToView, viewTargetForArtifact } from "@/lib/open-in-view";

const VIEW_LABELS = { cap: "cap sheet", trades: "trades", matchups: "matchups", scout: "scout", awards: "awards", compare: "compare" } as const;

export default function OpenInViewButton({ artifact }: { artifact: DimeArtifact }) {
  const target = viewTargetForArtifact(artifact);
  if (!target) return null;
  const label = `Open in ${VIEW_LABELS[target.tab]}`;
  return (
    <Button
      size="icon"
      variant="quiet"
      aria-label={label}
      title={label}
      onClick={() => navigateToView(target)}
    >
      <OpenNewWindow width={14} height={14} aria-hidden="true" />
    </Button>
  );
}
