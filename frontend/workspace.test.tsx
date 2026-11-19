import test from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { JSDOM } from "jsdom";
import { HomeContent, HomeView } from "./components/shell/WorkspaceViews";
import WarehouseView from "./components/dime/views/WarehouseView";
import { PromptBar } from "./components/ds/PromptBar";
import { ShotsExplorer } from "./components/shell/ShotsExplorer";
import TradesView from "./components/dime/views/TradesView";
import type { HomeSnapshot } from "./lib/warehouse";
import { clearEnvelopeCache } from "./lib/api";

const snapshot: HomeSnapshot = { date: "2026-11-19", schedule: { available: false, table: "silver_scoreboard", games: [], next_date: null, seasons: [], last_fetch: null }, snapshot: { table: "silver_team_ratings", season: "2025-26", rows: [{ TEAM_NAME: "Boston", GP: 82, NET_RATING: 10.3 }], last_fetch: "2026-04-13" } };

async function mount(element: React.ReactElement, fetcher: typeof fetch, check: (host: HTMLElement, dom: JSDOM) => Promise<void>) {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, IS_REACT_ACT_ENVIRONMENT: true });
  Object.assign(dom.window.HTMLElement.prototype, { attachEvent() {}, detachEvent() {} });
  const previous = globalThis.fetch;
  globalThis.fetch = fetcher;
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  try { await act(async () => root.render(element)); await check(host, dom); }
  finally { await act(async () => root.unmount()); globalThis.fetch = previous; dom.window.close(); }
}

test("Home distinguishes absent and empty schedules, renders next date and cites real snapshots", () => {
  const html = renderToStaticMarkup(<HomeContent data={snapshot} />);
  assert.match(html, /No games today/); assert.match(html, /No schedule source/); assert.match(html, /silver_team_ratings/); assert.match(html, /2025-26/); assert.match(html, /2026-04-13/); assert.match(html, /\+10.3/); assert.doesNotMatch(html, /Sample data|injur/i);
  const scheduled = { ...snapshot, schedule: { ...snapshot.schedule, available: true, next_date: "2026-11-20" } };
  assert.match(renderToStaticMarkup(<HomeContent data={scheduled} />), /Next scheduled date in the warehouse: 2026-11-20/);
  const games = { ...snapshot, schedule: { ...snapshot.schedule, available: true, games: [{ GAME_ID: "1", VISITOR_TEAM_ABBREVIATION: "BOS", HOME_TEAM_ABBREVIATION: "NYK", _season: "2026-27", GAME_STATUS_TEXT: "7:30 PM" }] } };
  const slate = renderToStaticMarkup(<HomeContent data={games} />);
  assert.match(slate, /BOS at NYK/); assert.match(slate, /silver_scoreboard/); assert.match(slate, /2026-27/); assert.doesNotMatch(slate, /No games today/);
  const calendar = { ...snapshot, schedule: { ...snapshot.schedule, available: true, table: "silver_schedule", games: [{ id: "2", name: "Atlanta Hawks at Toronto Raptors", date: "2026-11-20T01:30Z", _season: "2026-27" }] } };
  const calendarHtml = renderToStaticMarkup(<HomeContent data={calendar} />);
  assert.match(calendarHtml, /Atlanta Hawks at Toronto Raptors/); assert.match(calendarHtml, /8:30 PM ET/); assert.match(calendarHtml, /silver_schedule/);
  assert.match(renderToStaticMarkup(<HomeContent data={{ ...snapshot, snapshot: { ...snapshot.snapshot, rows: [] } }} />), /No team ratings are cached/);
});

test("Home errors never substitute invented data", async () => {
  await mount(<HomeView onAsk={() => {}} />, async () => new Response("offline", { status: 503 }), async host => {
    assert.match(host.textContent!, /Could not load the warehouse snapshot/); assert.match(host.textContent!, /No sample data is substituted/); assert.ok(host.querySelector('[role="alert"]'));
  });
});

test("Data uses actual schema and types for arbitrary silver tables, including empty and error states", async () => {
  const calls: string[] = [];
  await mount(<WarehouseView />, async input => {
    const url = String(input); calls.push(url);
    if (url.includes("freshness")) return Response.json({ ok: true, rows: ["silver_advanced", "silver_empty", "silver_broken"].map(table => ({ table, rows: 3, last_fetch: "2026-04-13", data_through: "2026-04-12" })) });
    if (url.includes("silver_broken")) return new Response("offline", { status: 500 });
    if (url.includes("/warehouse/tables/")) return Response.json({ ok: true, table: "silver_advanced", columns: [{ name: "NET_RATING", type: "DECIMAL(10,2)" }], count: 3, rows: url.includes("silver_empty") ? [] : [{ NET_RATING: 10.3 }], seasons: ["2025-26"], limit: 50 });
    return Response.json({ ok: true, revision: "revision" });
  }, async host => {
    assert.match(host.textContent!, /DECIMAL\(10,2\)/); assert.match(host.textContent!, /10.3/); assert.match(host.textContent!, /Data through 2026-04-12/);
    assert.ok(calls.some(url => url.includes("/warehouse/tables/silver_advanced"))); assert.ok(!calls.some(url => url.includes("/datasets/advanced")));
    await act(async () => [...host.querySelectorAll("button")].find(button => button.textContent?.includes("silver_empty"))!.click());
    assert.match(host.textContent!, /No rows for this selection/); assert.match(host.textContent!, /DECIMAL/);
    await act(async () => [...host.querySelectorAll("button")].find(button => button.textContent?.includes("silver_broken"))!.click());
    assert.match(host.textContent!, /Could not load this table/);
  });
});

test("Ask explains supported provider keys and prevents form and keyboard sends without models", async () => {
  let sent = 0;
  const props = { value: "Question", onChange() {}, onSend() { sent++; }, onStop() {}, busy: false, models: [], model: null, onModelChange() {}, onRetry() {}, providers: ["gemini", "nvidia", "openrouter", "mistral", "cerebras"] };
  await mount(<PromptBar {...props} />, async () => Response.json({}), async (host, dom) => {
    for (const key of ["GEMINI_API_KEY", "GOOGLE_API_KEY", "NVIDIA_NIM_API_KEY", "OPENROUTER_API_KEY", "MISTRAL_API_KEY", "CEREBRAS_API_KEY"]) assert.match(host.textContent!, new RegExp(key));
    assert.match(host.textContent!, /Restart the Node analyst backend/); assert.match(host.querySelector("a")!.href, /README.md#quickstart/);
    assert.equal(host.querySelector<HTMLButtonElement>('[aria-label="Send message"]')!.disabled, true);
    await act(async () => { host.querySelector("textarea")!.focus(); host.querySelector("form")!.dispatchEvent(new dom.window.Event("submit", { bubbles: true, cancelable: true })); host.querySelector("textarea")!.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Enter", bubbles: true })); });
    assert.equal(sent, 0);
  });
  const enabled = renderToStaticMarkup(<PromptBar {...props} models={[{ id: "gemini:flash", label: "Flash", available: true }]} model="gemini:flash" />);
  assert.doesNotMatch(enabled, /no models are configured/);
  const error = renderToStaticMarkup(<PromptBar {...props} modelError />); assert.match(error, /Models unavailable/); assert.doesNotMatch(error, /no models are configured/);
});

test("Shots explorer preserves zone data even if shot coordinates are unavailable", async () => {
  const previous = globalThis.fetch;
  await mount(<ShotsExplorer season="2025-26" initialPlayer="2544" />, async input => {
    const url = String(input);
    if (url.includes("zone_splits")) return Response.json({ ok: true, data: [{ zone: "rim", FGM: 1, FGA: 2, FG_PCT: 0.5, share: 1 }], meta: { source: "warehouse:silver_zone_splits" } });
    return Response.json({ ok: false, error: "No shot coordinates" });
  }, async (host, dom) => {
    await act(async () => host.querySelector("form")!.dispatchEvent(new dom.window.Event("submit", { bubbles: true, cancelable: true })));
    assert.match(host.textContent!, /No shot coordinates/); assert.match(host.textContent!, /50.0%/); assert.match(host.textContent!, /warehouse:silver_zone_splits/);
  });
  globalThis.fetch = previous;
});

test("Trades renders the backend's readable domain error on HTTP 422", async () => {
  await mount(<TradesView />, async () => Response.json({ ok: false, error: "Salary data lists Luka with LAL, not DAL" }, { status: 422 }), async host => {
    await act(async () => [...host.querySelectorAll("button")].find(item => item.textContent?.includes("Luka"))!.click());
    const button = [...host.querySelectorAll("button")].find(item => item.textContent?.includes("Check with real cap rules"));
    assert.ok(button);
    await act(async () => button.click());
    assert.match(host.textContent!, /Salary data lists Luka with LAL, not DAL/);
    assert.doesNotMatch(host.textContent!, /Could not reach the backend/);
  });
});

test("Shots queries follow asynchronously loaded and subsequently selected seasons", async () => {
  const calls: string[] = [];
  function Seasons() {
    const [season, setSeason] = React.useState("");
    return <><button onClick={() => setSeason("2022-23")}>Loaded season</button><button onClick={() => setSeason("2023-24")}>Selected season</button><ShotsExplorer season={season} initialPlayer="2544" /></>;
  }
  await mount(<Seasons />, async input => { calls.push(String(input)); return Response.json({ ok: true, data: [] }); }, async (host, dom) => {
    const input = host.querySelector<HTMLInputElement>('[aria-label="Shots season"]')!;
    assert.equal(input.value, "");
    assert.equal([...host.querySelectorAll("button")].find(button => button.textContent === "Load shots")!.disabled, true);
    for (const [label, season] of [["Loaded season", "2022-23"], ["Selected season", "2023-24"]]) {
      await act(async () => [...host.querySelectorAll("button")].find(button => button.textContent === label)!.click());
      assert.equal(input.value, season);
      await act(async () => host.querySelector("form")!.dispatchEvent(new dom.window.Event("submit", { bubbles: true, cancelable: true })));
      assert.ok(calls.slice(-2).every(url => new URL(url).searchParams.get("season") === season));
    }
  });
});

test("Warehouse passes loaded seasons and table filter changes to Shots", async () => {
  clearEnvelopeCache();
  let resolveDetail!: (response: Response) => void;
  let first = true;
  const detail = { ok: true, columns: [], rows: [], seasons: ["2022-23", "2021-22"], count: 0 };
  await mount(<WarehouseView />, async input => {
    const url = String(input);
    if (url.includes("freshness")) return Response.json({ ok: true, rows: [{ table: "silver_shots", rows: 0, last_fetch: null }] });
    if (url.includes("/warehouse/tables/")) {
      if (first) { first = false; return new Promise<Response>(resolve => { resolveDetail = resolve; }); }
      return Response.json(detail);
    }
    return Response.json({});
  }, async (host, dom) => {
    const input = () => host.querySelector<HTMLInputElement>('[aria-label="Shots season"]')!;
    assert.equal(input().value, "");
    await act(async () => resolveDetail(Response.json(detail)));
    assert.equal(input().value, "2022-23");
    await act(async () => {
      const filter = host.querySelector<HTMLSelectElement>('[aria-label="Table season"]')!;
      filter.value = "2021-22";
      filter.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
    });
    assert.equal(input().value, "2021-22");
  });
});
