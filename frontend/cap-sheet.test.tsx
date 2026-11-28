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

const forceObjectError = { value: false };

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
    HTMLInputElement: dom.window.HTMLInputElement,
    Element: dom.window.Element,
    Node: dom.window.Node,
    NodeFilter: dom.window.NodeFilter,
    MutationObserver: dom.window.MutationObserver,
    Event: dom.window.Event,
    CustomEvent: dom.window.CustomEvent,
    KeyboardEvent: dom.window.KeyboardEvent,
    MouseEvent: dom.window.MouseEvent,
    getComputedStyle: dom.window.getComputedStyle.bind(dom.window),
    localStorage: dom.window.localStorage,
    IS_REACT_ACT_ENVIRONMENT: true,
  });
  const previousFetch = globalThis.fetch;
  const previousStorage = globalThis.localStorage;
  const scenarioRequests: ScenarioRequest[] = [];
  const objectRequests: { body: { kind: string; title: string; payload: { team: string; season: string; moves: ScenarioMove[] } }; headers: unknown }[] = [];
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    if (url.includes("/api/cap/sheet")) return Response.json(capSheetFixture);
    if (url.includes("/api/cap/scenario")) {
      const body = JSON.parse(String(init?.body)) as ScenarioRequest;
      scenarioRequests.push(body);
      return Response.json(scenarioResult(body));
    }
    if (url.includes("/api/objects")) {
      const body = JSON.parse(String(init?.body));
      objectRequests.push({ body, headers: init?.headers });
      if (forceObjectError.value) return new Response("x", { status: 503 });
      return Response.json({
        object_id: "obj-" + "ab".repeat(16),
        kind: body.kind,
        title: body.title,
        payload: body.payload,
        schema_version: 1,
        created_at: "2026-11-27T13:00:00.000Z",
        updated_at: "2026-11-27T13:00:00.000Z",
        archived: false,
        read_token: "testreadtoken" + "x".repeat(20),
        owner_token: "testownertoken" + "y".repeat(40),
      }, { status: 201 });
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
    objectRequests,
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
  const toggle = cell.querySelector("button");
  assert.ok(toggle, "option cells are native buttons — keyboard-operable without a key handler shim");
  assert.match(toggle.getAttribute("title") ?? "", /option/);
  assert.equal(toggle.getAttribute("aria-pressed") !== null, true, "toggle state is exposed to assistive tech");
  await click(toggle);
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

test("share minting creates a persistent object and surfaces the copyable link", async () => {
  const mounted = await mountCapSheet();
  try {
    assert.equal([...mounted.host.querySelectorAll("button")].some((button) => button.textContent?.trim() === "Share"), false, "no share entry before moves exist");
    await clickOption(mounted.host, "Jayson Tatum", "2028-29");
    const share = [...mounted.host.querySelectorAll("button")].find((button) => button.textContent?.trim() === "Share");
    assert.ok(share, "share entry point renders once moves exist");
    await click(share);
    assert.equal(mounted.objectRequests.length, 1);
    const mint = mounted.objectRequests[0];
    assert.equal(mint.body.kind, "cap_scenario");
    assert.equal(mint.body.payload.team, "BOS");
    assert.equal(mint.body.payload.moves.length, 1);
    assert.equal(mint.body.payload.moves[0].kind, "option_decision");
    assert.equal(mint.body.payload.moves[0].player, "Jayson Tatum");
    assert.ok(JSON.stringify(mint.headers).includes("x-dime-owner"), "owner header sent");
    assert.match(mounted.host.textContent!, /Snapshot link minted/, "confirmation copy rendered");
    const link = [...mounted.host.querySelectorAll("input[readonly],textarea")].find((el) => (el as HTMLInputElement).value.includes("/s/testreadtoken"));
    assert.ok(link, "copyable link field present");
    const stored = mounted.host.ownerDocument?.defaultView?.localStorage ?? globalThis.localStorage;
    assert.ok(Object.keys(stored).some((key) => key.includes("obj-") || key.includes("dime_owner")), "owner token retained client-side");
    const copyButton = [...mounted.host.querySelectorAll("button")].find((button) => /copy/i.test(button.textContent ?? ""));
    assert.ok(copyButton, "copy affordance present");
  } finally {
    await mounted.cleanup();
  }
});

test("share minting failure is honest and in-place", async () => {
  const mounted = await mountCapSheet();
  try {
    await clickOption(mounted.host, "Jayson Tatum", "2028-29");
    const share = [...mounted.host.querySelectorAll("button")].find((button) => button.textContent?.trim() === "Share")!;
    forceObjectError.value = true;
    await click(share);
    assert.equal(mounted.objectRequests.length, 1);
    assert.match(mounted.host.textContent!, /couldn'?t be shared|share failed|try again/i);
    assert.equal((mounted.host.textContent ?? "").includes("/s/testreadtoken"), false, "no phantom link on failure");
  } finally {
    forceObjectError.value = false;
    await mounted.cleanup();
  }
});

test("post-mint edits surface Share updated instead of a dead end", async () => {
  const mounted = await mountCapSheet();
  try {
    await clickOption(mounted.host, "Jayson Tatum", "2028-29");
    const share = [...mounted.host.querySelectorAll("button")].find((button) => button.textContent?.trim() === "Share")!;
    await click(share);
    assert.equal(mounted.objectRequests.length, 1);
    assert.equal([...mounted.host.querySelectorAll("button")].some((button) => button.textContent?.trim() === "Share"), false, "share hidden while snapshot matches");
    await clickOption(mounted.host, "Jaylen Brown", "2029-30");
    const again = [...mounted.host.querySelectorAll("button")].find((button) => button.textContent?.trim() === "Share updated");
    assert.ok(again, "Share updated appears once moves diverge");
    assert.match(mounted.host.textContent!, /changed since this link was minted/);
    await click(again);
    assert.equal(mounted.objectRequests.length, 2, "second mint creates a new object");
  } finally {
    await mounted.cleanup();
  }
});

test("payroll math explains labeled components, dead-money rows and room derivation", async () => {
  const mounted = await mountCapSheet();
  try {
    const trigger = [...mounted.host.querySelectorAll("button")].find((button) => button.getAttribute("aria-label") === "Payroll math for 2027-28");
    assert.ok(trigger, "payroll popover trigger renders");
    await click(trigger);
    const popover = mounted.host.ownerDocument.querySelector('[role="dialog"]');
    assert.ok(popover, "payroll popover opens");
    const text = popover.textContent ?? "";
    assert.match(text, /Roster payroll/);
    assert.match(text, /\$197,737,323/);
    assert.match(text, /Dead money/);
    assert.match(text, /\$7,660,317/);
    assert.match(text, /Dead-money example/);
    assert.match(text, /Committed salary subtotal/);
    assert.match(text, /\$205,397,640/);
    assert.match(text, /Cap holds/);
    assert.match(text, /\$4,100,000/);
    assert.match(text, /Minimum-roster charges/);
    assert.match(text, /\$1,234,567/);
    assert.match(text, /Payroll estimate/);
    assert.match(text, /\$210,732,207/);
    assert.match(text, /Team-option salary/);
    assert.match(text, /\$2,726,487/);
    assert.match(text, /Outside this estimate/);
    assert.match(text, /Salary cap/);
    assert.match(text, /\$176,508,270/);
    assert.match(text, /Cap room estimate/);
    assert.ok(text.includes("−$34,223,937"), "cap room derives exactly from cap minus payroll");
  } finally {
    await mounted.cleanup();
  }
});

test("waived players strike through in the waive season and all forward cells", async () => {
  const mounted = await mountCapSheet([{ kind: "waive", player: "Jayson Tatum" }]);
  try {
    await clickOption(mounted.host, "Jayson Tatum", "2028-29");
    const loadSaved = [...mounted.host.querySelectorAll("button")].find((button) => button.textContent?.trim() === "Load saved");
    assert.ok(loadSaved, "Load saved button present");
    await click(loadSaved);
    const rows = [...mounted.host.querySelectorAll("tbody tr")];
    const row = rows.find((tr) => (tr.textContent ?? "").includes("Jayson Tatum"));
    assert.ok(row, "player row renders");
    const cells = [...row.querySelectorAll("td")].slice(1);
    assert.ok(cells.length > 1, "year cells render");
    const struck = cells.filter((cell) => cell.className.includes("line-through"));
    assert.equal(struck.length, cells.length, `every year cell strikes from the waive season forward, got ${struck.length} of ${cells.length}`);
  } finally {
    await mounted.cleanup();
  }
});

test("roster rows without player_ids render distinctly — no key collapse for unsigned camp players", async () => {
  const errors: string[] = [];
  const originalError = console.error;
  console.error = (...args: unknown[]) => { errors.push(args.map(String).join(" ")); };
  const mounted = await mountCapSheet();
  try {
    const names = [...mounted.host.querySelectorAll("tbody tr th, tbody tr td:first-child")].map((cell) => cell.textContent ?? "");
    assert.ok(names.length > 0, "roster renders");
    const dupeKeyWarnings = errors.filter((line) => line.includes("same key"));
    assert.deepEqual(dupeKeyWarnings, [], "no duplicate-key warnings even with null player_ids in the roster");
  } finally {
    console.error = originalError;
    await mounted.cleanup();
  }
});


test("draft sync failure surfaces a sonner toast instead of dying silently", async () => {
  const mounted = await mountCapSheet();
  try {
    const { default: DimeToaster } = await import("./components/dime/DimeToaster");
    const toasterHost = mounted.host.ownerDocument.createElement("div");
    mounted.host.ownerDocument.body.appendChild(toasterHost);
    const toasterRoot = createRoot(toasterHost);
    await act(async () => toasterRoot.render(<DimeToaster />));
    forceObjectError.value = true;
    await clickOption(mounted.host, "Jayson Tatum", "2028-29");
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 1200));
    });
    const toastText = mounted.host.ownerDocument.body.textContent ?? "";
    assert.match(toastText, /aren't saving/i, "the sync failure surfaces as a toast");
    assert.match(toastText, /retries as you keep editing/i, "the toast states the honest recovery behavior");
    await act(async () => toasterRoot.unmount());
  } finally {
    forceObjectError.value = false;
    await mounted.cleanup();
  }
});
