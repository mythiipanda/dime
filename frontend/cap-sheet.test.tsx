import test from "node:test";
import assert from "node:assert/strict";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";
import {
  capScenarioFixture,
  capSheetFixture,
  type ScenarioMove,
  type ScenarioResponse,
} from "./lib/capsheet-fixture";

type ScenarioRequest = {
  season?: string;
  moves?: ScenarioMove[];
};

function scenarioResult(body: ScenarioRequest): ScenarioResponse {
  const moves = body.moves ?? [];
  const mixed = moves.some((move) => move.kind !== "option_decision");
  const errors = moves.flatMap((move, index) => {
    if (!mixed || move.kind !== "option_decision" || !move.season || move.season === body.season) return [];
    return [{
      move: String(index),
      error: `option decision for ${move.season} cannot be combined with moves evaluated in ${body.season}; evaluate one season at a time`,
    }];
  });
  return { ...capScenarioFixture, season: body.season ?? "2026-27", errors };
}

async function flush() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 30));
  });
}

async function mountCapSheet(seededMoves?: ScenarioMove[]) {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost/?tab=cap" });
  Object.assign(globalThis, {
    window: dom.window,
    document: dom.window.document,
    HTMLElement: dom.window.HTMLElement,
    Element: dom.window.Element,
    Node: dom.window.Node,
    localStorage: dom.window.localStorage,
    IS_REACT_ACT_ENVIRONMENT: true,
  });
  const previousFetch = globalThis.fetch;
  const previousStorage = globalThis.localStorage;
  const scenarioRequests: ScenarioRequest[] = [];
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    if (url.includes("/api/cap/sheet")) return Response.json(capSheetFixture);
    if (url.includes("/api/cap/scenario")) {
      const body = JSON.parse(String(init?.body)) as ScenarioRequest;
      scenarioRequests.push(body);
      return Response.json(scenarioResult(body));
    }
    throw new Error(`Unexpected fetch ${url}`);
  };
  if (seededMoves) {
    const { newBoard, pinArtifact, saveBoard } = await import("./lib/boards");
    const artifact = {
      kind: "cap_scenario",
      title: "Seeded cap scenario",
      team: "BOS",
      season: "2026-27",
      moves: seededMoves,
      pay_after: null,
      pinned_from: "cap_sheet_test",
    };
    saveBoard(pinArtifact(newBoard(), artifact as never));
  }
  const { default: CapSheetView } = await import("./components/dime/views/CapSheetView");
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  await act(async () => root.render(<CapSheetView />));
  await flush();
  return {
    host,
    scenarioRequests,
    cleanup: async () => {
      await act(async () => root.unmount());
      globalThis.fetch = previousFetch;
      globalThis.localStorage = previousStorage;
      dom.window.close();
    },
  };
}

async function click(element: Element) {
  await act(async () => {
    (element as HTMLElement).click();
    await new Promise((resolve) => setTimeout(resolve, 30));
  });
}

async function clickOption(host: ParentNode, playerName: string, season: string) {
  const player = capSheetFixture.players.find((entry) => entry.player === playerName)!;
  const yearIndex = player.years.findIndex((year) => year.season === season);
  const row = [...host.querySelectorAll("tr")].find((entry) => entry.textContent?.includes(playerName))!;
  const cell = row.querySelectorAll("td")[yearIndex + 1];
  assert.ok(cell);
  assert.match(cell.getAttribute("title") ?? "", /option/);
  await click(cell);
}

test("mixed signing and future option stays in the current season and surfaces the backend rejection", async () => {
  const signing = { kind: "signing", label: "Contract Test", amount: 5_000_000 } satisfies ScenarioMove;
  const option = { kind: "option_decision", player: "Jayson Tatum", season: "2028-29", exercise: false } satisfies ScenarioMove;
  const mounted = await mountCapSheet([signing, option]);
  try {
    assert.match(mounted.host.textContent!, /Jayson Tatum/);
    await clickOption(mounted.host, "Jayson Tatum", "2028-29");
    const loadSaved = [...mounted.host.querySelectorAll("button")].find((button) => button.textContent?.trim() === "Load saved")!;
    await click(loadSaved);
    const request = mounted.scenarioRequests.at(-1)!;
    assert.equal(request.season, "2026-27");
    assert.deepEqual(request.moves, [
      { kind: "signing", label: "Contract Test", amount: 5_000_000 },
      { kind: "option_decision", player: "Jayson Tatum", season: "2028-29", exercise: false },
    ]);
    assert.match(
      mounted.host.textContent!,
      /option decision for 2028-29 cannot be combined with moves evaluated in 2026-27; evaluate one season at a time/,
    );
  } finally {
    await mounted.cleanup();
  }
});

test("same-season option-only scenarios derive the future option season", async () => {
  const mounted = await mountCapSheet();
  try {
    await clickOption(mounted.host, "Jaylen Brown", "2029-30");
    await clickOption(mounted.host, "Sam Hauser", "2029-30");
    const request = mounted.scenarioRequests.at(-1)!;
    assert.equal(request.season, "2029-30");
    assert.equal(request.moves?.length, 2);
    assert.ok(request.moves?.every((move) => move.kind === "option_decision" && move.season === "2029-30"));
    assert.match(mounted.host.textContent!, /evaluation season 2029-30/);
  } finally {
    await mounted.cleanup();
  }
});
