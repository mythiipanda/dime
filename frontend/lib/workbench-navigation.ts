export type TradeConstructionSeed = {
  legs: { from: string; to: string; players?: string | string[]; picks?: Record<string, unknown>[] }[];
  season: string;
};

export type CapScenarioSeed = {
  team: string;
  season: string;
  moves: Record<string, unknown>[];
  waiver_date?: string;
};

export type WorkbenchSeed =
  | { kind: "trade"; construction: TradeConstructionSeed }
  | { kind: "cap_scenario"; construction: CapScenarioSeed };

export const WORKBENCH_EVENT = "dime:workbench";

export function openTradeInWorkbench(construction: TradeConstructionSeed) {
  window.dispatchEvent(new CustomEvent<WorkbenchSeed>(WORKBENCH_EVENT, {
    detail: { kind: "trade", construction },
  }));
}

export function openCapScenarioInWorkbench(construction: CapScenarioSeed) {
  window.dispatchEvent(new CustomEvent<WorkbenchSeed>(WORKBENCH_EVENT, {
    detail: { kind: "cap_scenario", construction },
  }));
}
