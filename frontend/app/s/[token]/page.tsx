import type { Metadata } from "next";
import { BACKEND } from "@/lib/chat";
import { loadSharedScenario } from "@/lib/shared";
import { SharedScenarioNotice, SharedScenarioView } from "@/components/dime/views/SharedScenarioView";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ token: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { token } = await params;
  const state = await loadSharedScenario(BACKEND, token);
  if (state.status === "ok" || state.status === "archived") {
    return { title: `${state.object.title} — dime shared cap scenario` };
  }
  return { title: "shared scenario — dime" };
}

export default async function SharedScenarioPage({ params }: Params) {
  const { token } = await params;
  const state = await loadSharedScenario(BACKEND, token);
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
