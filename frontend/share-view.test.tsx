import test from "node:test";
import assert from "node:assert/strict";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";
import { capScenarioFixture, type ScenarioMove, type ScenarioResponse } from "./lib/capsheet-fixture";

const sharedObject = {
  kind: "cap_scenario",
  title: "Waiver wire plan",
  payload: {
    team: "BOS",
    season: "2026-27",
    moves: [
      { kind: "waive", player: "Player One", stretch: true },
      { kind: "signing", label: "minimum signing", amount: 2300000 },
    ] as ScenarioMove[],
  },
  schema_version: 1,
  updated_at: "2026-11-27T12:00:00.000Z",
  archived: false,
};

const evaluation: ScenarioResponse = {
  ...capScenarioFixture,
  pay_after: 187400000,
  state: { over_tax: false, over_apron1: false, over_apron2: true, room_under_apron2: -1200000 },
};

async function mountView(element: React.ReactNode) {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost/s/token" });
  Object.assign(globalThis, {
    window: dom.window,
    document: dom.window.document,
    HTMLElement: dom.window.HTMLElement,
    Element: dom.window.Element,
    Node: dom.window.Node,
    IS_REACT_ACT_ENVIRONMENT: true,
  });
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  await act(async () => root.render(element));
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 20));
  });
  return {
    host,
    cleanup: async () => {
      await act(async () => root.unmount());
      dom.window.close();
    },
  };
}

test("shared cap scenario renders title, moves, evaluation and provenance read-only", async () => {
  const { SharedScenarioView } = await import("./components/dime/views/SharedScenarioView");
  const mounted = await mountView(<SharedScenarioView object={sharedObject} evaluation={evaluation} />);
  try {
    const text = mounted.host.textContent!;
    assert.match(text, /Waiver wire plan/);
    assert.match(text, /BOS/);
    assert.match(text, /waive Player One/);
    assert.match(text, /stretch/);
    assert.match(text, /sign minimum signing \(\$2\.3M\)/);
    assert.match(text, /187\.4/);
    const deltaCells = [...mounted.host.querySelectorAll("li")].map((li) => li.textContent ?? "");
    assert.ok(deltaCells.some((cell) => cell.includes("waive Player One") && /−\$|\+\$/.test(cell)), `expected a signed delta on the waive row, got: ${deltaCells.join(" | ")}`);
    assert.match(text, /second apron/);
    assert.match(text, /evaluated live/i);
    assert.match(text, /read-only/i);
    assert.equal(mounted.host.querySelectorAll("button").length, 0);
    assert.equal(mounted.host.querySelectorAll("input").length, 0);
    assert.equal(mounted.host.querySelectorAll("form").length, 0);
    const home = [...mounted.host.querySelectorAll("a")].find((a) => a.getAttribute("href") === "/");
    assert.ok(home, "expected a link back to the product");
  } finally {
    await mounted.cleanup();
  }
});

test("restricted states render honest notice blocks without controls", async () => {
  const { SharedScenarioNotice } = await import("./components/dime/views/SharedScenarioView");
  const archived = await mountView(<SharedScenarioNotice tone="archived" />);
  try {
    assert.match(archived.host.textContent!, /taken down|archived/i);
    assert.equal(archived.host.querySelectorAll("input").length, 0);
  } finally {
    await archived.cleanup();
  }
  const missing = await mountView(<SharedScenarioNotice tone="not_found" />);
  try {
    assert.match(missing.host.textContent!, /not found|no longer exists|never did/i);
  } finally {
    await missing.cleanup();
  }
  const invalid = await mountView(<SharedScenarioNotice tone="invalid" />);
  try {
    assert.match(invalid.host.textContent!, /invalid|malformed/i);
  } finally {
    await invalid.cleanup();
  }
});

test("evaluation failure renders the stored moves with an honest evaluation notice", async () => {
  const { SharedScenarioView } = await import("./components/dime/views/SharedScenarioView");
  const failed: ScenarioResponse = {
    ...evaluation,
    ok: false,
    errors: [{ move: "0", error: "Player One is not on the BOS roster" }],
    steps: [],
  };
  const mounted = await mountView(<SharedScenarioView object={sharedObject} evaluation={failed} />);
  try {
    const text = mounted.host.textContent!;
    assert.match(text, /waive Player One/);
    assert.match(text, /not on the BOS roster/);
  } finally {
    await mounted.cleanup();
  }
});

test("loadSharedScenario maps backend responses into the view states", async () => {
  const { loadSharedScenario } = await import("./lib/shared");
  const withFetch = async (impl: (url: string, init?: RequestInit) => Promise<Response>) =>
    loadSharedScenario("http://backend", "tok", impl as typeof fetch);

  const okResult = await withFetch(async (url) => {
    if (url.includes("/api/cap/scenario")) return Response.json(evaluation);
    return Response.json(sharedObject);
  });
  assert.equal(okResult.status, "ok");
  if (okResult.status === "ok") {
    assert.equal(okResult.object.title, "Waiver wire plan");
    assert.equal(okResult.evaluation?.pay_after, 187400000);
  }

  const evalOrder: string[] = [];
  await withFetch(async (url, init) => {
    evalOrder.push(url);
    if (url.includes("/api/cap/scenario")) {
      const body = JSON.parse(String(init?.body));
      assert.equal(body.team, "BOS");
      assert.equal(body.season, "2026-27");
      assert.equal(body.moves.length, 2);
      return Response.json(evaluation);
    }
    return Response.json(sharedObject);
  });
  assert.ok(evalOrder.some((url) => url.endsWith("/s/tok")));

  assert.equal((await withFetch(async () => new Response("x", { status: 404 }))).status, "not_found");
  assert.equal((await withFetch(async () => new Response("x", { status: 422 }))).status, "invalid");
  assert.equal((await withFetch(async () => { throw new Error("down"); })).status, "unavailable");
  assert.equal(
    (await withFetch(async () => Response.json({ ...sharedObject, archived: true }))).status,
    "archived",
  );
  assert.equal(
    (await withFetch(async () => Response.json({ ...sharedObject, kind: "board" }))).status,
    "unsupported",
  );
  const evalFailed = await withFetch(async (url) => {
    if (url.includes("/api/cap/scenario")) return new Response("x", { status: 422 });
    return Response.json(sharedObject);
  });
  assert.equal(evalFailed.status, "ok");
  if (evalFailed.status === "ok") assert.equal(evalFailed.evaluation, null);
});
const tradeObject = {
  kind: "trade_scenario",
  title: "DAL/NYK construction",
  payload: {
    legs: [
      { from: "DAL", to: "NYK", players: "Daniel Gafford", picks: [{ year: 2027, round: 1 }] },
      { from: "NYK", to: "DAL", players: "Mitchell Robinson" },
    ],
    season: "2026-27",
  },
  schema_version: 1,
  updated_at: "2026-11-27T12:00:00.000Z",
  archived: false,
};

const tradeEvaluation = {
  rows: [
    { team: "DAL", incoming: 5400000, outgoing: 12400000, matching_ok: true, match_rule: "over cap: incoming within 125% + 100k", allowed_incoming: 15600000, over_apron1: false, over_apron2: false, hard_cap: null, issues: [] },
    { team: "NYK", incoming: 12400000, outgoing: 5400000, matching_ok: false, match_rule: "apron team: exact matching required", allowed_incoming: 5400000, over_apron1: true, over_apron2: false, hard_cap: "apron1", issues: ["incoming salary exceeds apron matching"] },
  ],
  meta: { disclaimer: "Salary data as of snapshot", salary_date: "2026-06-15" },
};

test("shared trade construction renders legs, verdict, matching math and apron state read-only", async () => {
  const { SharedTradeView } = await import("./components/dime/views/SharedScenarioView");
  const mounted = await mountView(<SharedTradeView object={tradeObject} evaluation={tradeEvaluation} />);
  try {
    const text = mounted.host.textContent!;
    assert.match(text, /DAL\/NYK construction/);
    assert.match(text, /Daniel Gafford/);
    assert.match(text, /Mitchell Robinson/);
    assert.match(text, /Not legal as constructed/);
    assert.match(text, /out \$12\.4M/);
    assert.match(text, /in \$5\.4M/);
    assert.match(text, /incoming salary exceeds apron matching/);
    assert.match(text, /hard cap/);
    assert.equal(mounted.host.querySelectorAll("button, input, select, textarea").length, 0);
  }
  finally {
    await mounted.cleanup();
  }
});

test("shared trade construction without evaluation shows legs honestly labeled", async () => {
  const { SharedTradeView } = await import("./components/dime/views/SharedScenarioView");
  const mounted = await mountView(<SharedTradeView object={tradeObject} evaluation={null} />);
  try {
    const text = mounted.host.textContent!;
    assert.match(text, /Daniel Gafford/);
    assert.match(text, /without a legality verdict/);
    assert.doesNotMatch(text, /Legal under current/);
  }
  finally {
    await mounted.cleanup();
  }
});

test("loadSharedScenario dispatches trade_scenario to the legs evaluator with the stored legs", async () => {
  const { loadSharedScenario } = await import("./lib/shared");
  const seen: string[] = [];
  const result = await loadSharedScenario("http://backend", "tok", async (input, init) => {
    const url = String(input);
    seen.push(url);
    if (url.includes("/api/trade/legs")) {
      const body = JSON.parse(String(init?.body));
      assert.equal(body.legs.length, 2);
      assert.equal(body.legs[0].from, "DAL");
      assert.equal(body.season, "2026-27");
      return Response.json(tradeEvaluation);
    }
    return Response.json(tradeObject);
  });
  assert.equal(result.status, "ok-trade");
  if (result.status === "ok-trade") {
    assert.equal(result.object.payload.legs.length, 2);
    assert.equal(result.evaluation?.rows?.length, 2);
  }
  assert.ok(seen.some((url) => url.endsWith("/s/tok")));
});

test("loadSharedScenario treats malformed trade payloads as unavailable", async () => {
  const { loadSharedScenario } = await import("./lib/shared");
  const malformed = { ...tradeObject, payload: { legs: [{ from: "DAL" }], season: "2026-27" } };
  const result = await loadSharedScenario("http://backend", "tok", async () => Response.json(malformed));
  assert.equal(result.status, "unavailable");
});
