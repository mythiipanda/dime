import type { Metadata } from "next";
import { BACKEND } from "@/lib/chat";
import { loadSharedScenario } from "@/lib/shared";
import { SharedScenarioNotice, SharedScenarioView, SharedThreadView, SharedTradeView } from "@/components/dime/views/SharedScenarioView";
import { SharedBoardView } from "@/components/dime/views/SharedBoardView";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ token: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { token } = await params;
  const state = await loadSharedScenario(BACKEND, token);
  if (state.status === "ok" || state.status === "ok-trade" || state.status === "ok-thread" || state.status === "ok-board" || state.status === "archived") {
    const label = state.status === "ok-trade" ? "trade construction" : state.status === "ok-thread" ? "analysis thread" : state.status === "ok-board" ? "board" : "cap scenario";
    return { title: `${state.object.title} — dime shared ${label}` };
  }
  return { title: "shared object — dime" };
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
      return <SharedBoardView object={state.object} board={state.board} metrics={state.metrics} />;
    case "archived":
      return <SharedScenarioNotice tone="archived" />;
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
