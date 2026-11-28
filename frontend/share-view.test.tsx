import test from "node:test";
import assert from "node:assert/strict";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";
import type { ScenarioMove } from "./lib/capsheet-fixture";
import type { ProjectionResponse } from "./lib/planner";

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

const evaluation: ProjectionResponse = {
  ok: true,
  team: "BOS",
  base_season: "2026-27",
  seasons: [
    {
      season: "2026-27",
      pay_before: 190000000,
      pay_after: 187400000,
      cap_room: -22439000,
      players: [],
      roster_before: 15,
      roster_after: 15,
      roster_issues: [],
      hard_cap: "",
      hard_cap_violation: "",
      exception_usage: [],
      effects: [
        { move: 0, kind: "waive", detail: "waive Player One", delta: -4900000, exactness: "exact" },
        { move: 1, kind: "signing", detail: "sign minimum signing", delta: 2300000, exactness: "exact" },
      ],
      moves_in_season: 2,
      ordering_notes: [],
      lines: { cap: 164961000, tax: 200428000, apron1: 209015000, apron2: 221686000 },
      lines_projected: false,
    },
  ],
  errors: [],
  warnings: [],
  disclosures: [],
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
    const effectCells = [...mounted.host.querySelectorAll("li")].map((li) => li.textContent ?? "");
    assert.ok(effectCells.some((cell) => cell.includes("waive Player One")), `expected the waive move, got: ${effectCells.join(" | ")}`);
    assert.ok(effectCells.some((cell) => cell.includes("waive Player One") && /\$4\.9M/.test(cell)), `expected the waive effect delta, got: ${effectCells.join(" | ")}`);
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
  const failed: ProjectionResponse = {
    ...evaluation,
    ok: false,
    errors: [{ move: "0", error: "Player One is not on the BOS roster" }],
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
    if (url.includes("/api/cap/projection")) return Response.json(evaluation);
    return Response.json(sharedObject);
  });
  assert.equal(okResult.status, "ok");
  if (okResult.status === "ok") {
    assert.equal(okResult.object.title, "Waiver wire plan");
    assert.equal(okResult.evaluation?.seasons[0]?.pay_after, 187400000);
  }

  const evalOrder: string[] = [];
  await withFetch(async (url, init) => {
    evalOrder.push(url);
    if (url.includes("/api/cap/projection")) {
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
    (await withFetch(async () => Response.json({ ...sharedObject, kind: "widget" }))).status,
    "unsupported",
  );
  assert.equal(
    (await withFetch(async () => Response.json({ ...sharedObject, kind: "board" }))).status,
    "unavailable",
    "a board-kind envelope carrying a non-board payload is a integrity failure, not unsupported",
  );
  const evalFailed = await withFetch(async (url) => {
    if (url.includes("/api/cap/projection")) return new Response("x", { status: 422 });
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
    const controls = [...mounted.host.querySelectorAll("button, input, select, textarea")].filter(el => !/download/i.test(el.getAttribute("aria-label") || ""));
    assert.equal(controls.length, 0);
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
const threadShared = {
  kind: "thread_grant",
  title: "shared analysis",
  payload: { thread: true },
  transcript: [
    { question: "Who won the MVP race?", answer: "The case for the frontrunner rests on\nefficiency and team success.", tables: [{ tool: "get_awards", meta: { source: "warehouse", season: "2025-26" } }], created_at: "2026-11-27T10:00:00.000Z" },
    { question: "Compare their shooting", answer: "Shot profiles diverge at the rim.", tables: [], created_at: "2026-11-27T10:05:00.000Z" },
  ],
  schema_version: 1,
  updated_at: "2026-11-27T12:00:00.000Z",
  archived: false,
};

test("shared thread renders transcript read-only with evidence attribution", async () => {
  const { SharedThreadView } = await import("./components/dime/views/SharedScenarioView");
  const mounted = await mountView(<SharedThreadView object={threadShared} transcript={threadShared.transcript} />);
  try {
    const text = mounted.host.textContent!;
    assert.match(text, /shared analysis/);
    assert.match(text, /Who won the MVP race\?/);
    assert.match(text, /efficiency and team success/);
    assert.match(text, /Compare their shooting/);
    assert.match(text, /get_awards/);
    assert.match(text, /snapshot of the thread/);
    const controls = [...mounted.host.querySelectorAll("button, input, select, textarea")].filter(el => !/download/i.test(el.getAttribute("aria-label") || ""));
    assert.equal(controls.length, 0);
  }
  finally {
    await mounted.cleanup();
  }
});

test("shared thread with empty transcript renders honest empty state", async () => {
  const { SharedThreadView } = await import("./components/dime/views/SharedScenarioView");
  const mounted = await mountView(<SharedThreadView object={threadShared} transcript={[]} />);
  try {
    assert.match(mounted.host.textContent!, /no analyses to show/);
  }
  finally {
    await mounted.cleanup();
  }
});

test("loadSharedScenario dispatches thread_grant to the transcript shape", async () => {
  const { loadSharedScenario } = await import("./lib/shared");
  const result = await loadSharedScenario("http://backend", "tok", async () => Response.json(threadShared));
  assert.equal(result.status, "ok-thread");
  if (result.status === "ok-thread") {
    assert.equal(result.transcript.length, 2);
    assert.equal(result.object.title, "shared analysis");
  }
});

test("loadSharedScenario filters malformed transcript entries", async () => {
  const { loadSharedScenario } = await import("./lib/shared");
  const malformed = { ...threadShared, transcript: [...threadShared.transcript, { question: 42 }] };
  const result = await loadSharedScenario("http://backend", "tok", async () => Response.json(malformed));
  assert.equal(result.status, "ok-thread");
  if (result.status === "ok-thread") assert.equal(result.transcript.length, 2);
});
const artifactShared = {
  kind: "artifact_ref",
  title: "pinned cap ledger",
  payload: { artifact_index: 0 },
  artifact: {
    kind: "memo",
    title: "The locked ledger",
    sections: [{ heading: "Ledger case", body: "The ledger case rests on capture-time figures." }],
    provenance: { capability: "sql_exec", dataset: "silver_salaries", season: "2026-27" },
  },
  evidence: [
    { ref: "r1", tool: "sql_exec", meta: { source: "warehouse", season: "2026-27", fetched_at: "2026-11-27T10:00:00Z" }, rows: [{ player: "Player One" }] },
    { ref: "r2", missing: true },
  ],
  captured_at: "2026-11-27T10:00:00.000Z",
  schema_version: 1,
  updated_at: "2026-11-27T12:00:00.000Z",
  archived: false,
};

test("shared artifact renders body, provenance, evidence and capture honesty read-only", async () => {
  const { SharedArtifactView } = await import("./components/dime/views/SharedScenarioView");
  const mounted = await mountView(<SharedArtifactView object={artifactShared} artifact={artifactShared.artifact} evidence={artifactShared.evidence} capturedAt={artifactShared.captured_at} unavailable={false} />);
  try {
    const text = mounted.host.textContent!;
    assert.match(text, /pinned cap ledger/);
    assert.match(text, /capture-time figures/);
    assert.match(text, /sql_exec/);
    assert.match(text, /silver_salaries/);
    assert.match(text, /no longer resolvable/);
    assert.match(text, /capture-time snapshot/);
    const controls = [...mounted.host.querySelectorAll("button, input, select, textarea")].filter(el => !/download/i.test(el.getAttribute("aria-label") || ""));
    assert.equal(controls.length, 0);
  }
  finally {
    await mounted.cleanup();
  }
});

test("shared artifact unavailable state renders honestly", async () => {
  const { SharedArtifactView } = await import("./components/dime/views/SharedScenarioView");
  const mounted = await mountView(<SharedArtifactView object={artifactShared} artifact={null} evidence={[]} capturedAt={null} unavailable={true} />);
  try {
    assert.match(mounted.host.textContent!, /no longer available/);
  }
  finally {
    await mounted.cleanup();
  }
});

test("loadSharedScenario dispatches artifact_ref with evidence and capture time", async () => {
  const { loadSharedScenario } = await import("./lib/shared");
  const result = await loadSharedScenario("http://backend", "tok", async () => Response.json(artifactShared));
  assert.equal(result.status, "ok-artifact");
  if (result.status === "ok-artifact") {
    assert.equal(result.evidence.length, 2);
    assert.equal(result.unavailable, false);
    assert.equal(result.captured_at, "2026-11-27T10:00:00.000Z");
  }
});

test("shared artifact view normalizes object-shaped table rows into rendered cell values", async () => {
  const { SharedArtifactView } = await import("./components/dime/views/SharedScenarioView");
  const tableArtifact = {
    ...artifactShared,
    artifact: {
      kind: "table",
      title: "Cap table",
      columns: [
        { key: "team", label: "Team" },
        { key: "salary", label: "Salary", numeric: true },
      ],
      rows: [
        { team: "Fixture Team", salary: 218062392 },
        { team: "Second Team", salary: 150000000 },
      ],
    },
  };
  const mounted = await mountView(<SharedArtifactView object={artifactShared} artifact={tableArtifact.artifact} evidence={artifactShared.evidence} capturedAt={artifactShared.captured_at} unavailable={false} />);
  try {
    const text = mounted.host.textContent!;
    assert.match(text, /Fixture Team/);
    assert.match(text, /218062392/);
  }
  finally {
    await mounted.cleanup();
  }
});


test("board share render shows pin cards with live evaluations and honest degradation", async () => {
  const { SharedBoardView } = await import("./components/dime/views/SharedBoardView");
  const boardObject = {
    kind: "board",
    title: "Guards board",
    schema_version: 1,
    updated_at: "2026-11-27T12:00:00.000Z",
    archived: false,
    payload: {
      season: "2026-27",
      rows: [{ player_id: 1628369 }],
      columns: [{ metric_id: "ppg" }],
    },
  };
  const pins = [
    {
      kind: "trade_scenario",
      object_id: "obj-trade-1",
      status: "ok" as const,
      title: "Fixture trade",
      note: "summer idea",
      payload: { season: "2026-27", legs: [{ from: "BOS", to: "DAL", players: ["Fixture Player"] }] },
      tradeEvaluation: { rows: [{ team: "BOS", matching_ok: true }] },
    },
    {
      kind: "cap_scenario",
      object_id: "obj-cap-1",
      status: "archived" as const,
    },
  ];
  const mounted = await mountView(<SharedBoardView object={boardObject} board={null} metrics={[]} pins={pins} />);
  try {
    const text = mounted.host.textContent!;
    assert.match(text, /Pinned to this board/);
    assert.match(text, /Fixture trade/);
    assert.match(text, /summer idea/);
    assert.match(text, /Legal under current salary-matching rules/);
    assert.match(text, /removed by its owner/);
  }
  finally {
    await mounted.cleanup();
  }
});

test("loadSharedScenario board dispatch parses pins and evaluates cap and trade targets", async () => {
  const { loadSharedScenario } = await import("./lib/shared");
  const envelope = {
    kind: "board",
    title: "b",
    schema_version: 1,
    updated_at: "2026-11-27T12:00:00.000Z",
    archived: false,
    payload: {
      season: "2026-27",
      rows: [{ player_id: 1628369 }],
      columns: [{ metric_id: "ppg" }],
      pins: [
        { kind: "cap_scenario", object_id: "obj-cap", note: "n", status: "ok", title: "cap pin", payload: { team: "BOS", season: "2026-27", moves: [{ kind: "waive" }] } },
        { kind: "trade_scenario", object_id: "obj-trade", status: "ok", title: "trade pin", payload: { season: "2026-27", legs: [{ from: "BOS", to: "DAL" }] } },
        { kind: "artifact_ref", object_id: "obj-art", status: "missing" },
      ],
    },
    pins: [
      { kind: "cap_scenario", object_id: "obj-cap", note: "n", status: "ok", title: "cap pin", payload: { team: "BOS", season: "2026-27", moves: [{ kind: "waive" }] } },
      { kind: "trade_scenario", object_id: "obj-trade", status: "ok", title: "trade pin", payload: { season: "2026-27", legs: [{ from: "BOS", to: "DAL" }] } },
      { kind: "artifact_ref", object_id: "obj-art", status: "missing" },
    ],
  };
  const responses = new Map<string, unknown>([
    ["/s/", envelope],
    ["/api/cap/projection", { ok: true, seasons: [], errors: [], warnings: [], disclosures: [] }],
    ["/api/trade/legs", { rows: [{ team: "BOS", matching_ok: true }] }],
    ["/api/boards/fill", null],
    ["/api/boards/metrics", null],
  ]);
  const result = await loadSharedScenario("http://backend", "tok", async (url) => {
    const key = [...responses.keys()].find(k => String(url).includes(k));
    return Response.json(key ? responses.get(key) : null);
  });
  assert.equal(result.status, "ok-board");
  if (result.status === "ok-board") {
    assert.equal(result.pins.length, 3);
    assert.equal(result.pins[0].capEvaluation !== null && result.pins[0].capEvaluation !== undefined, true);
    assert.equal(result.pins[1].tradeEvaluation?.rows?.length, 1);
    assert.equal(result.pins[2].status, "missing");
  }
});
