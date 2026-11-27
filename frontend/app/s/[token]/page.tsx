import type { Metadata } from "next";
import { BACKEND } from "@/lib/chat";
import { loadSharedScenario, loadSharedBoard } from "@/lib/shared";
import { SharedScenarioNotice, SharedScenarioView } from "@/components/dime/views/SharedScenarioView";
import { SharedBoardView } from "@/components/dime/views/SharedBoardView";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ token: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { token } = await params;
  const state = await loadSharedScenario(BACKEND, token);
  if (state.status === "ok" || state.status === "archived") {
    return { title: `${state.object.title} — dime shared cap scenario` };
  }
  if (state.status === "unsupported" && state.kind === "board") {
    const boardState = await loadSharedBoard(BACKEND, token);
    if (boardState.status === "ok" || boardState.status === "archived") {
      return { title: `${boardState.object.title} — dime shared board` };
    }
  }
  return { title: "shared — dime" };
}

export default async function SharedScenarioPage({ params }: Params) {
  const { token } = await params;
  const state = await loadSharedScenario(BACKEND, token);
  if (state.status === "unsupported" && state.kind === "board") {
    const boardState = await loadSharedBoard(BACKEND, token);
    switch (boardState.status) {
      case "ok":
        return <SharedBoardView object={boardState.object} board={boardState.board} metrics={boardState.metrics} />;
      case "archived":
        return <SharedScenarioNotice tone="archived" />;
      case "not_found":
        return <SharedScenarioNotice tone="not_found" />;
      case "invalid":
        return <SharedScenarioNotice tone="invalid" />;
      case "unavailable":
        return <SharedScenarioNotice tone="unavailable" />;
    }
  }
  switch (state.status) {
    case "ok":
      return <SharedScenarioView object={state.object} evaluation={state.evaluation} />;
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
