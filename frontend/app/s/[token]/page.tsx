import type { Metadata } from "next";
import { BACKEND } from "@/lib/chat";
import { loadSharedScenario } from "@/lib/shared";
import { SharedArtifactView, SharedScenarioNotice, SharedScenarioView, SharedThreadView, SharedTradeView } from "@/components/dime/views/SharedScenarioView";
import { SharedBoardView } from "@/components/dime/views/SharedBoardView";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ token: string }> };

const OG_DESCRIPTIONS: Record<string, string> = {
  artifact: "A capture-time snapshot from a Dime analysis, pinned to the exact evidence rows it was built from.",
  "cap scenario": "A cap scenario constructed in the Dime workbench, evaluated live against current cap rules.",
  "trade construction": "A trade construction from the Dime workbench, evaluated against current salary-matching rules.",
  "analysis thread": "A snapshot of a Dime analysis thread as it existed when shared.",
  board: "A player board from the Dime workbench.",
};

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { token } = await params;
  const state = await loadSharedScenario(BACKEND, token);
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL;
  const metadataBase = siteUrl ? { metadataBase: new URL(siteUrl) } : {};
  if (state.status === "ok" || state.status === "ok-trade" || state.status === "ok-thread" || state.status === "ok-board" || state.status === "ok-artifact" || state.status === "archived") {
    const label = state.status === "ok-trade" ? "trade construction" : state.status === "ok-thread" ? "analysis thread" : state.status === "ok-board" ? "board" : state.status === "ok-artifact" ? "artifact" : "cap scenario";
    const title = `${state.object.title} — dime shared ${label}`;
    const description = OG_DESCRIPTIONS[label] ?? "Shared from dime — an AI analyst workbench for NBA data.";
    return {
      ...metadataBase,
      title,
      description,
      openGraph: {
        title,
        description,
        type: "article",
        images: [{ url: "/og-share.png", width: 1200, height: 630, alt: "dime — an AI analyst workbench for NBA data" }],
      },
      twitter: {
        card: "summary_large_image",
        title,
        description,
      },
    };
  }
  return { ...metadataBase, title: "shared object — dime" };
}

export default async function SharedScenarioPage({ params }: Params) {
  const { token } = await params;
  const state = await loadSharedScenario(BACKEND, token);
  switch (state.status) {
    case "ok":
      return <SharedScenarioView object={state.object} evaluation={state.evaluation} />;
    case "ok-trade":
      return <SharedTradeView object={state.object} evaluation={state.evaluation} />;
    case "ok-thread":
      return <SharedThreadView object={state.object} transcript={state.transcript} />;
    case "ok-board":
      return <SharedBoardView object={state.object} board={state.board} metrics={state.metrics} pins={state.pins} />;
    case "ok-artifact":
      return <SharedArtifactView object={state.object} artifact={state.artifact} evidence={state.evidence} capturedAt={state.captured_at} unavailable={state.unavailable} />;
    case "archived":
      return <SharedScenarioNotice tone="archived" kind={state.object.kind} />;
    case "not_found":
      return <SharedScenarioNotice tone="not_found" />;
    case "invalid":
      return <SharedScenarioNotice tone="invalid" />;
    case "unsupported":
      return <SharedScenarioNotice tone="unsupported" />;
    case "unavailable":
      return <SharedScenarioNotice tone="unavailable" />;
  }
}
