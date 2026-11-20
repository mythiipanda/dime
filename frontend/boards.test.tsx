import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { addRow, boardTemplates, getBoard, listBoards, newBoard, saveBoard, type BoardMetric } from "./lib/boards";

const metrics: BoardMetric[] = boardTemplates[0].columns.map((id) => ({ id, label: id === "ppg" ? "Points" : id, category: "Scoring", unit: "per_game", table: "silver_player_season", column: id.toUpperCase(), higher_is_better: true, definition: `${id} definition` }));
const players = { "201939": { name: "Stephen Curry", team: "GSW" }, "203999": { name: "Nikola Jokić", team: "DEN" } };
const requests: { path: string; body: Record<string, unknown> }[] = [];
const asks: string[] = [];

async function mount(options: { failure?: boolean; seedEmpty?: boolean; boardId?: string; nullReason?: string; notebookError?: boolean } = {}) {
  const dom = new JSDOM("<!doctype html><html><body><div id='root'></div></body></html>", { url: "http://localhost", pretendToBeVisual: true });
  const gx = globalThis as unknown as Record<string, unknown>;
  Object.assign(gx, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, HTMLElement: dom.window.HTMLElement, Element: dom.window.Element, Node: dom.window.Node, DocumentFragment: dom.window.DocumentFragment, ShadowRoot: dom.window.ShadowRoot, requestAnimationFrame: dom.window.requestAnimationFrame.bind(dom.window), cancelAnimationFrame: dom.window.cancelAnimationFrame.bind(dom.window), getComputedStyle: dom.window.getComputedStyle.bind(dom.window), IS_REACT_ACT_ENVIRONMENT: true });
  Object.assign(dom.window.HTMLElement.prototype, { attachEvent() {}, detachEvent() {}, scrollIntoView() {} });
  const { BoardsPanel } = await import("./components/BoardsPanel");
  const opened: string[] = [];
  function Harness() { const [id, setId] = useState<string | null>(null); return <BoardsPanel boardId={id} onOpen={setId} onAsk={(p) => asks.push(p)} onOpenNotebook={(id) => opened.push(id)} />; }
  const previous = globalThis.fetch;
  requests.length = 0; asks.length = 0;
  globalThis.fetch = async (url, init) => {
    const path = String(url); const body = init?.body ? JSON.parse(String(init.body)) : {};
    requests.push({ path, body });
    if (path.endsWith("/notebooks")) return options.notebookError ? Response.json({ detail: "Notebook backend unavailable" }, { status: 503 }) : Response.json({ id: "b".repeat(32) });
    if (path.endsWith("/metrics")) return Response.json({ ok: true, metrics });
    if (path.endsWith("/seed")) return Response.json({ ok: true, player_ids: options.seedEmpty ? [] : [201939, 203999], cells: {}, players });
    if (path.endsWith("/fill")) {
      if (options.failure) return Response.json({ detail: "Boards warehouse unavailable" }, { status: 503 });
      const cells = Object.fromEntries((body.player_ids as number[]).map((pid) => [pid, Object.fromEntries((body.metric_ids as string[]).map((id) => [id, { value: 25.5, citation: { table: "silver_player_season", column: id.toUpperCase(), season: body.season, source: "warehouse-test", fetched_at: "2026-09-01", sql: "SELECT * FROM silver_player_season WHERE _season = ?", params: [body.season], row_key: { PLAYER_ID: pid } } }]))]));
      if (options.nullReason) for (const row of Object.values(cells)) for (const cell of Object.values(row)) Object.assign(cell, { value: null, reason: options.nullReason });
      return Response.json({ ok: true, cells, players });
    }
    return Response.json({ rows: { players: [] } });
  };
  const root = createRoot(dom.window.document.getElementById("root")!);
  await act(async () => { root.render(options.boardId ? <BoardsPanel boardId={options.boardId} onOpen={() => {}} onAsk={() => {}} /> : <Harness />); });
  const host = dom.window.document.getElementById("root")!;
  return { dom, host, options, root, opened, cleanup: async () => { await act(async () => root.unmount()); globalThis.fetch = previous; dom.window.close(); } };
}
const button = (host: ParentNode, text: string) => [...host.querySelectorAll("button")].find((b) => b.textContent?.includes(text))!;
async function click(el: HTMLElement) { assert.ok(el); await act(async () => { el.click(); await new Promise((r) => setTimeout(r, 25)); }); }

test("board notebook action posts a scoped seed and opens only after creation succeeds", async () => {
  const m = await mount();
  try {
    await click(button(m.host, "Scoring guards"));
    await click(button(m.host, "Open as notebook"));
    const body = requests.find((request) => request.path.endsWith("/notebooks"))!.body;
    assert.deepEqual(body.origin, { kind: "board", ref: listBoards()[0].id });
    const cells = body.cells as { kind: string; source: string }[];
    assert.match(cells.find((cell) => cell.kind === "sql")!.source, /VALUES \(201939,[\s\S]*\(203999,/);
    assert.deepEqual(m.opened, ["b".repeat(32)]);
  } finally { await m.cleanup(); }
});

test("board notebook backend errors show a dismissible toast without navigating or losing the board", async () => {
  const m = await mount({ notebookError: true });
  try {
    await click(button(m.host, "Scoring guards"));
    await click(button(m.host, "Open as notebook"));
    assert.match(m.host.querySelector('[role="alert"]')!.textContent!, /Notebook not created[\s\S]*backend unavailable/);
    assert.deepEqual(m.opened, []);
    assert.match(m.host.textContent!, /Stephen Curry/);
    await click(m.host.querySelector<HTMLButtonElement>('[aria-label="Dismiss notebook error"]')!);
    assert.equal(m.host.querySelector('[role="alert"]'), null);
  } finally { await m.cleanup(); }
});

test("creates a template, fills real row ids, saves its cache and opens a source card", async () => {
  const m = await mount();
  try {
    await click(button(m.host, "Scoring guards"));
    assert.ok(m.host.textContent?.includes("Stephen Curry"));
    assert.ok(m.host.textContent?.includes("25.5"));
    assert.doesNotMatch(m.host.textContent!, /Warehouse only|No model required/);
    const fill = requests.find((r) => r.path.endsWith("/fill"))!;
    assert.deepEqual(fill.body.player_ids, [201939, 203999]);
    assert.equal(fill.body.season, "2025-26");
    const saved = listBoards()[0]; assert.equal(getBoard(saved.id)?.cells["201939"].ppg.value, 25.5);
    await click(m.host.querySelector<HTMLButtonElement>('[aria-label="Source: Stephen Curry · Points"]')!);
    assert.match(m.dom.window.document.body.textContent!, /warehouse-test/);
    assert.match(m.dom.window.document.body.textContent!, /SELECT \* FROM silver_player_season/);
    assert.match(m.dom.window.document.body.textContent!, /2026-09-01/);
  } finally { await m.cleanup(); }
});

test("blank boards do not seed or fill and Ask only receives a prefill prompt", async () => {
  const m = await mount();
  try {
    await click(button(m.host, "Blank board"));
    assert.ok(m.host.textContent?.includes("Make room for a better decision"));
    assert.equal(requests.filter((r) => /\/(fill|seed)$/.test(r.path)).length, 0);
    await click(button(m.host, "Ask Dime about this board"));
    assert.equal(asks.length, 1); assert.match(asks[0], /Blank board/);
    assert.equal(requests.filter((r) => r.path.includes("chat")).length, 0);
  } finally { await m.cleanup(); }
});

test("fill errors remain visible and retry fills without reseeding", async () => {
  const m = await mount({ failure: true });
  try {
    await click(button(m.host, "Scoring guards"));
    assert.match(m.host.querySelector('[role="alert"]')!.textContent!, /Boards warehouse unavailable/);
    m.options.failure = false;
    await click(button(m.host, "Retry"));
    assert.equal(m.host.querySelector('[role="alert"]'), null);
    assert.equal(requests.filter((r) => r.path.endsWith("/seed")).length, 1);
    assert.equal(requests.filter((r) => r.path.endsWith("/fill")).length, 2);
    assert.ok(m.host.textContent?.includes("25.5"));
  } finally { await m.cleanup(); }
});

test("an empty seed is explicit, not fabricated player rows", async () => {
  const m = await mount({ seedEmpty: true });
  try { await click(button(m.host, "Scoring guards")); assert.match(m.host.querySelector('[role="alert"]')!.textContent!, /No players matched/); assert.equal(listBoards()[0].rows.length, 0); } finally { await m.cleanup(); }
});

test("metric picker shows definitions and Library reuses saved-board links", async () => {
  const m = await mount();
  try {
    await click(button(m.host, "Blank board"));
    await click(button(m.host, "Add metric"));
    assert.match(m.dom.window.document.body.textContent!, /ppg definition/);
    const saved = saveBoard(addRow(newBoard(), { player_id: 201939, name: "Curry", team: "GSW" }));
    const opened: string[] = [];
    const { SavedBoards } = await import("./components/SavedBoards");
    await act(async () => m.root.render(<SavedBoards onOpen={(id) => opened.push(id)} />));
    await click(button(m.host, "Open"));
    assert.ok(opened.length === 1);
    assert.ok(listBoards().some((b) => b.id === saved.id));
  } finally { await m.cleanup(); }
});

test("Library opens a memory-only board through client navigation", async () => {
  const m = await mount();
  try {
    Object.defineProperty(m.dom.window, "localStorage", { configurable: true, get() { throw new Error("Storage blocked"); } });
    const saved = saveBoard(newBoard());
    const pushed: string[] = [];
    const { AppRouterContext } = await import("next/dist/shared/lib/app-router-context.shared-runtime");
    const { default: BriefsPage } = await import("./app/briefs/page");
    const router = { push: (url: string) => pushed.push(url), replace() {}, refresh() {}, back() {}, forward() {}, prefetch: async () => {}, bfcacheId: "test" };
    await act(async () => m.root.render(<AppRouterContext.Provider value={router}><BriefsPage /></AppRouterContext.Provider>));
    assert.match(m.host.textContent!, /Session only/);
    await click(button(m.host, "Open"));
    assert.deepEqual(pushed, [`/?tab=boards&board=${encodeURIComponent(saved.id)}`]);
    assert.equal(getBoard(saved.id)?.id, saved.id);
  } finally { await m.cleanup(); }
});

test("reopening a board replaces cached nulls with a fresh warehouse fill", async () => {
  const m = await mount({ nullReason: "unmatched_salary_name" });
  try {
    await click(button(m.host, "Scoring guards"));
    const saved = listBoards()[0];
    assert.equal(getBoard(saved.id)?.cells[201939].ppg.value, null);
    await click(button(m.host, "All boards"));
    m.options.nullReason = undefined;
    await click(button(m.host, "Open"));
    assert.equal(requests.filter((r) => r.path.endsWith("/fill")).length, 2);
    assert.equal(getBoard(saved.id)?.cells[201939].ppg.value, 25.5);
  } finally { await m.cleanup(); }
});

for (const [reason, words] of [["unmatched_salary_name", "No 2026-27 salary row for this player"], ["ambiguous_salary_name", "Name matches multiple players"]]) {
  test(`null ${reason} explains the reason on keyboard focus`, async () => {
    const m = await mount({ nullReason: reason });
    try {
      await click(button(m.host, "Scoring guards"));
      const trigger = m.host.querySelector<HTMLButtonElement>('[aria-label^="Source: Stephen Curry · Points"]')!;
      assert.ok(trigger.getAttribute("aria-label")?.includes(words));
      await act(async () => { trigger.focus(); });
      assert.ok(m.dom.window.document.querySelector('[role="status"]')?.textContent?.includes(words));
    } finally { await m.cleanup(); }
  });
}
=======
import { testDom } from "./test-dom";
import test from "node:test";
import assert from "node:assert/strict";
import { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { addRow, boardTemplates, getBoard, listBoards, newBoard, saveBoard, type BoardMetric } from "./lib/boards";

const metrics: BoardMetric[] = boardTemplates[0].columns.map((id) => ({ id, label: id === "ppg" ? "Points" : id, category: "Scoring", unit: id === "salary_2026_27" ? "usd" : id.endsWith("_pct") ? "pct" : "per_game", table: "silver_player_season", column: id.toUpperCase(), higher_is_better: true, definition: `${id} definition` }));
const players = { "201939": { name: "Stephen Curry", team: "GSW" }, "203999": { name: "Nikola Jokić", team: "DEN" } };
const requests: { path: string; body: Record<string, unknown> }[] = [];
const asks: string[] = [];

test("compact salary formatting explicitly omits unnecessary fractional zeros", async () => {
  const { formatBoardValue } = await import("./components/BoardsTable");
  const presentation = { label: "Salary", unit: "usd", format: "currency" } as const;
  assert.equal(formatBoardValue(2500000, presentation), "$2.5M");
  assert.equal(formatBoardValue(2000000, presentation), "$2M");
  assert.equal(formatBoardValue(2560000, presentation), "$2.56M");
});

async function mount(options: { failure?: boolean; seedEmpty?: boolean; boardId?: string; nullReason?: string; teamState?: "null" | "missing"; catalogFailure?: boolean } = {}) {
  const dom = testDom;
  dom.window.document.body.innerHTML = "<div id='root'></div>";
  dom.window.localStorage.clear();
  dom.window.history.replaceState({}, "", "/");
  Object.assign(globalThis, { localStorage: dom.window.localStorage, IS_REACT_ACT_ENVIRONMENT: true });
  Object.assign(dom.window.HTMLElement.prototype, { attachEvent() {}, detachEvent() {}, scrollIntoView() {} });
  const { BoardsPanel } = await import("./components/BoardsPanel");
  function Harness() { const [id, setId] = useState<string | null>(null); return <BoardsPanel boardId={id} onOpen={setId} onAsk={(p) => asks.push(p)} />; }
  const previous = globalThis.fetch;
  requests.length = 0; asks.length = 0;
  globalThis.fetch = async (url, init) => {
    const path = String(url); const body = init?.body ? JSON.parse(String(init.body)) : {};
    requests.push({ path, body });
    if (path.endsWith("/metrics")) return options.catalogFailure ? Response.json({ detail: "Metric catalog unavailable" }, { status: 503 }) : Response.json({ ok: true, metrics });
    if (path.endsWith("/seed")) return Response.json({ ok: true, player_ids: options.seedEmpty ? [] : [201939, 203999], cells: {}, players });
    if (path.endsWith("/fill")) {
      if (options.failure) return Response.json({ detail: "Boards warehouse unavailable" }, { status: 503 });
      const cells = Object.fromEntries((body.player_ids as number[]).map((pid) => [pid, Object.fromEntries((body.metric_ids as string[]).map((id) => [id, { value: 25.5, citation: { table: "silver_player_season", column: id.toUpperCase(), season: body.season, source: "warehouse-test", fetched_at: "2026-09-01", sql: "SELECT * FROM silver_player_season WHERE _season = ?", params: [body.season], row_key: { PLAYER_ID: pid } } }]))]));
      if (options.nullReason) for (const row of Object.values(cells)) for (const cell of Object.values(row)) Object.assign(cell, { value: null, reason: options.nullReason });
      const filledPlayers = options.teamState === "missing" ? {} : options.teamState === "null" ? Object.fromEntries(Object.entries(players).map(([id, player]) => [id, { ...player, team: null }])) : players;
      return Response.json({ ok: true, cells, players: filledPlayers });
    }
    return Response.json({ rows: { players: [] } });
  };
  const root = createRoot(dom.window.document.getElementById("root")!);
  await act(async () => { root.render(options.boardId ? <BoardsPanel boardId={options.boardId} onOpen={() => {}} onAsk={() => {}} /> : <Harness />); });
  const host = dom.window.document.getElementById("root")!;
  return { dom, host, options, root, cleanup: async () => { await act(async () => { root.unmount(); await new Promise(resolve => setTimeout(resolve, 25)); }); globalThis.fetch = previous; } };
}
const button = (host: ParentNode, text: string) => [...host.querySelectorAll("button")].find((b) => b.textContent?.includes(text))!;
async function click(el: HTMLElement) { assert.ok(el); await act(async () => { el.click(); await new Promise((r) => setTimeout(r, 25)); }); }

test("creates a template, fills real row ids, saves its cache and opens a source card", async () => {
  const m = await mount();
  try {
    await click(button(m.host, "Scoring guards"));
    assert.ok(m.host.textContent?.includes("Stephen Curry"));
    assert.ok(m.host.textContent?.includes("25.5"));
    assert.doesNotMatch(m.host.textContent!, /Warehouse only|No model required/);
    const fill = requests.find((r) => r.path.endsWith("/fill"))!;
    assert.deepEqual(fill.body.player_ids, [201939, 203999]);
    assert.equal(fill.body.season, "2025-26");
    const saved = listBoards()[0]; assert.equal(getBoard(saved.id)?.cells["201939"].ppg.value, 25.5);
    await click(m.host.querySelector<HTMLButtonElement>('[aria-label="Source: Stephen Curry · Points"]')!);
    assert.match(m.dom.window.document.body.textContent!, /warehouse-test/);
    assert.match(m.dom.window.document.body.textContent!, /SELECT \* FROM silver_player_season/);
    assert.match(m.dom.window.document.body.textContent!, /2026-09-01/);
  } finally { await m.cleanup(); }
});

test("blank boards do not seed or fill and Ask only receives a prefill prompt", async () => {
  const m = await mount();
  try {
    await click(button(m.host, "Blank board"));
    assert.ok(m.host.textContent?.includes("Make room for a better decision"));
    assert.equal(requests.filter((r) => /\/(fill|seed)$/.test(r.path)).length, 0);
    await click(button(m.host, "Ask Dime about this board"));
    assert.equal(asks.length, 1); assert.match(asks[0], /Blank board/);
    assert.equal(requests.filter((r) => r.path.includes("chat")).length, 0);
  } finally { await m.cleanup(); }
});

test("fill errors remain visible and retry fills without reseeding", async () => {
  const m = await mount({ failure: true });
  try {
    await click(button(m.host, "Scoring guards"));
    assert.match(m.host.querySelector('[role="alert"]')!.textContent!, /Boards warehouse unavailable/);
    m.options.failure = false;
    await click(button(m.host, "Retry"));
    assert.equal(m.host.querySelector('[role="alert"]'), null);
    assert.equal(requests.filter((r) => r.path.endsWith("/seed")).length, 1);
    assert.equal(requests.filter((r) => r.path.endsWith("/fill")).length, 2);
    assert.ok(m.host.textContent?.includes("25.5"));
  } finally { await m.cleanup(); }
});

test("an empty seed is explicit, not fabricated player rows", async () => {
  const m = await mount({ seedEmpty: true });
  try { await click(button(m.host, "Scoring guards")); assert.match(m.host.querySelector('[role="alert"]')!.textContent!, /No players matched/); assert.equal(listBoards()[0].rows.length, 0); } finally { await m.cleanup(); }
});

for (const teamState of ["null", "missing"] as const) {
  test(`season changes clear previous teams when new identities are ${teamState}`, async () => {
    const m = await mount();
    try {
      await click(button(m.host, "Scoring guards"));
      assert.equal(listBoards()[0].rows[0].team, "GSW");
      m.options.teamState = teamState;
      await click([...m.host.querySelectorAll<HTMLButtonElement>('[role="radio"]')].find(el => el.textContent === "2024-25")!);
      assert.equal(listBoards()[0].season, "2024-25");
      assert.ok(listBoards()[0].rows.every(row => row.team === ""));
      assert.match(m.host.querySelector("tbody")!.textContent!, /Team not recorded/);
      assert.doesNotMatch(m.host.querySelector("tbody")!.textContent!, /GSW|DEN/);
    } finally { await m.cleanup(); }
  });
}

test("metric picker shows definitions and Library reuses saved-board links", async () => {
  const m = await mount();
  try {
    await click(button(m.host, "Blank board"));
    await click(button(m.host, "Add metric"));
    assert.match(m.dom.window.document.body.textContent!, /ppg definition/);
    const saved = saveBoard(addRow(newBoard(), { player_id: 201939, name: "Curry", team: "GSW" }));
    const opened: string[] = [];
    const { SavedBoards } = await import("./components/SavedBoards");
    await act(async () => m.root.render(<SavedBoards onOpen={(id) => opened.push(id)} />));
    await click(button(m.host, "Open"));
    assert.ok(opened.length === 1);
    assert.ok(listBoards().some((b) => b.id === saved.id));
  } finally { await m.cleanup(); }
});

test("Library opens local boards even when server research fails", async () => {
  const m = await mount();
  try {
    const saved = saveBoard(newBoard());
    globalThis.fetch = async () => Response.json({ detail: "offline" }, { status: 503 });
    const opened: string[] = [];
    const { LibraryView } = await import("./components/shell/WorkspaceViews");
    await act(async () => m.root.render(<LibraryView onThread={() => {}} onBoard={id => opened.push(id)} />));
    assert.match(m.host.textContent!, /Blank board/);
    await click(button(m.host, "Open board"));
    assert.deepEqual(opened, [saved.id]);
    assert.match(m.host.textContent!, /Conversations could not be loaded/);
  } finally { await m.cleanup(); }
});

test("Boards URL opens in the shell and Ask restores a prefill without auto-sending", async () => {
  const m = await mount();
  try {
    const saved = saveBoard(addRow(newBoard(boardTemplates[0]), { player_id: 201939, name: "Stephen Curry", team: "GSW" }));
    m.dom.window.history.replaceState({}, "", `/?tab=boards&board=${saved.id}`);
    Object.defineProperty(m.dom.window, "matchMedia", { value: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }) });
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url, init) => {
      if (String(url).includes("/api/boards/")) return originalFetch(url, init);
      requests.push({ path: String(url), body: {} });
      return Response.json({ ok: true, rows: [], threads: [], projects: [], models: [], providers: {} });
    };
    const { DimeShell } = await import("./components/shell/DimeShell");
    await act(async () => m.root.render(<DimeShell />));
    assert.ok(m.host.querySelector('table[aria-label="Scoring guards"]'));
    await click(button(m.host, "Ask Dime about this board"));
    assert.equal(m.dom.window.location.search.includes("tab=chat"), true);
    const composer = m.host.querySelector("textarea")!;
    assert.match(composer.value, /Scoring guards/);
    assert.match(composer.value, /Stephen Curry/);
    assert.equal(requests.filter(request => request.path.includes("chat/stream") || request.path.includes("analyst/sessions")).length, 0);
    assert.ok(!m.dom.window.location.search.includes("board="));
  } finally { await m.cleanup(); }
});

test("reopening a board replaces cached nulls with a fresh warehouse fill", async () => {
  const m = await mount({ nullReason: "unmatched_salary_name" });
  try {
    await click(button(m.host, "Scoring guards"));
    const saved = listBoards()[0];
    assert.equal(getBoard(saved.id)?.cells[201939].ppg.value, null);
    await click(button(m.host, "All boards"));
    m.options.nullReason = undefined;
    await click(button(m.host, "Open"));
    assert.equal(requests.filter((r) => r.path.endsWith("/fill")).length, 2);
    assert.equal(getBoard(saved.id)?.cells[201939].ppg.value, 25.5);
  } finally { await m.cleanup(); }
});

for (const nullReason of [undefined, "no_metric_row"]) {
  test(`cached ${nullReason ? "missing" : "numeric"} values retain evidence when catalog and fill fail`, async () => {
    const m = await mount({ nullReason });
    try {
      await click(button(m.host, "Scoring guards"));
      const saved = listBoards()[0];
      m.options.catalogFailure = true;
      m.options.failure = true;
      const { BoardsPanel } = await import("./components/BoardsPanel");
      await act(async () => { m.root.render(<BoardsPanel boardId={saved.id} onOpen={() => {}} onAsk={() => {}} />); });
      assert.match(m.host.querySelector('[role="alert"]')!.textContent!, /Metric catalog unavailable/);
      const trigger = m.host.querySelector<HTMLButtonElement>('[aria-label^="Source: Stephen Curry · Points"]')!;
      assert.ok(trigger);
      assert.equal(trigger.textContent, nullReason ? "—" : "25.5");
      assert.doesNotMatch(m.host.querySelector("tbody")!.textContent!, /Not filled/);
      await click(trigger);
      const evidence = m.dom.window.document.querySelector('[role="dialog"]')!;
      assert.match(evidence.textContent!, /warehouse-test/);
      assert.match(evidence.textContent!, /SELECT \* FROM silver_player_season/);
      assert.match(evidence.textContent!, /2025-26/);
      if (nullReason) assert.match(evidence.textContent!, /No data for this player/);
    } finally { await m.cleanup(); }
  });
}

test("saved column metadata preserves labels, currency and percent units through a catalog outage", async () => {
  const m = await mount();
  try {
    await click(button(m.host, "Scoring guards"));
    const saved = listBoards()[0];
    assert.deepEqual(saved.columns.find(column => column.metric_id === "salary_2026_27")?.presentation, { label: "salary_2026_27", unit: "usd", format: "currency" });
    saved.cells[201939].salary_2026_27.value = 2500000;
    saved.cells[201939].ts_pct.value = 62.5;
    await act(async () => { saveBoard(saved); });
    m.options.catalogFailure = true;
    m.options.failure = true;
    const { BoardsPanel } = await import("./components/BoardsPanel");
    await act(async () => { m.root.render(<BoardsPanel boardId={saved.id} onOpen={() => {}} onAsk={() => {}} />); });
    assert.match(m.host.querySelector("thead")!.textContent!, /Points/);
    assert.match(m.host.querySelector("thead")!.textContent!, /Percent/);
    assert.match(m.host.querySelector("thead")!.textContent!, /USD/);
    for (const [id, formatted, evidenceValue] of [["ts_pct", "62.5%", "62.5%"], ["salary_2026_27", "$2.5M", "2,500,000 USD"]]) {
      const trigger = m.host.querySelector<HTMLButtonElement>(`[aria-label="Source: Stephen Curry · ${id}"]`)!;
      assert.equal(trigger.textContent, formatted);
      await click(trigger);
      const evidence = m.dom.window.document.querySelector('[role="dialog"]')!;
      assert.ok(evidence.textContent!.includes(evidenceValue));
      await act(async () => { evidence.dispatchEvent(new m.dom.window.KeyboardEvent("keydown", { key: "Escape", bubbles: true })); await new Promise(resolve => setTimeout(resolve, 25)); });
    }
  } finally { await m.cleanup(); }
});

for (const [reason, words] of [["unmatched_salary_name", "No 2026-27 salary row for this player"], ["ambiguous_salary_name", "Name matches multiple players"]]) {
  test(`null ${reason} retains a hover reason and opens evidence only on activation`, async () => {
    const m = await mount({ nullReason: reason });
    try {
      await click(button(m.host, "Scoring guards"));
      const trigger = m.host.querySelector<HTMLButtonElement>('[aria-label^="Source: Stephen Curry · Points"]')!;
      assert.ok(trigger.getAttribute("aria-label")?.includes(words));
      assert.ok(trigger.title.includes(words));
      await act(async () => { trigger.focus(); });
      assert.equal(m.dom.window.document.querySelector('[role="dialog"]'), null);
      await act(async () => { trigger.dispatchEvent(new m.dom.window.MouseEvent("pointerenter", { bubbles: true })); await new Promise(resolve => setTimeout(resolve, 200)); });
      assert.equal(m.dom.window.document.querySelector('[role="dialog"]'), null);
      await click(trigger);
      assert.ok(m.dom.window.document.querySelector('[role="status"]')?.textContent?.includes(words));
      assert.ok(m.dom.window.document.querySelector('[role="dialog"]')!.contains(m.dom.window.document.activeElement));
      await act(async () => { m.dom.window.document.activeElement!.dispatchEvent(new m.dom.window.KeyboardEvent("keydown", { key: "Escape", bubbles: true })); await new Promise(resolve => setTimeout(resolve, 25)); });
      assert.equal(m.dom.window.document.querySelector('[role="dialog"]'), null);
      assert.equal(m.dom.window.document.activeElement === trigger, true);
    } finally { await m.cleanup(); }
  });
}

test("column sorting is reflected in semantic headers and row order", async () => {
  const m = await mount();
  try {
    await click(button(m.host, "Scoring guards"));
    const saved = listBoards()[0];
    saved.cells["201939"].ppg.value = 20; saved.cells["203999"].ppg.value = 30;
    saveBoard(saved);
    const { BoardsTable } = await import("./components/BoardsTable");
    const { sortByColumn } = await import("./lib/boards");
    function Grid() {
      const [board, setBoard] = useState(saved);
      const [sort, setSort] = useState<{ id: string; best: boolean } | null>(null);
      return <BoardsTable board={board} metrics={metrics} loading={false} sort={sort} onSort={metric => { setSort({ id: metric.id, best: true }); setBoard(sortByColumn(board, metric)); }} onRemoveRow={() => {}} onRemoveColumn={() => {}} onMoveRow={() => {}} onMoveColumn={() => {}} />;
    }
    await act(async () => m.root.render(<Grid />));
    await click(button(m.host, "Points"));
    assert.match(m.host.querySelector("tbody tr")!.textContent!, /Nikola Jokić/);
    assert.equal(m.host.querySelector('[aria-sort="descending"]')?.textContent?.includes("Points"), true);
  } finally { await m.cleanup(); }
});

test("citation activation moves focus inside and makes the saved row key reachable", async () => {
  const m = await mount();
  try {
    await click(button(m.host, "Scoring guards"));
    const trigger = m.host.querySelector<HTMLButtonElement>('[aria-label="Source: Stephen Curry · Points"]')!;
    await act(async () => trigger.focus());
    await click(trigger);
    const evidence = m.dom.window.document.querySelector('[role="dialog"]')!;
    assert.ok(evidence.contains(m.dom.window.document.activeElement));
    const summary = evidence.querySelector("summary")!;
    await act(async () => { summary.focus(); summary.click(); });
    assert.equal(m.dom.window.document.activeElement === summary, true);
    assert.equal(summary.parentElement!.hasAttribute("open"), true);
    assert.match(summary.parentElement!.textContent!, /201939/);
    await act(async () => { summary.dispatchEvent(new m.dom.window.KeyboardEvent("keydown", { key: "Escape", bubbles: true })); await new Promise(resolve => setTimeout(resolve, 25)); });
    assert.equal(m.dom.window.document.querySelector('[role="dialog"]'), null);
    assert.equal(m.dom.window.document.activeElement === trigger, true);
  } finally { await m.cleanup(); }
});
>>>>>>> origin/dev
