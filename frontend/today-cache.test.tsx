import { describe, it, afterEach } from "node:test";
import * as assert from "node:assert";
import { JSDOM } from "jsdom";
import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import TodayPanel from "./components/TodayPanel";
import { HomeView } from "./components/shell/HomeView";
import { addWatchlist, clearEnvelopeCache, getWatchlist } from "./lib/api";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost/",
});
const win = dom.window as unknown as Window & typeof globalThis;
const gx = globalThis as unknown as Record<string, unknown>;
gx.window = win;
gx.document = win.document;
Object.defineProperty(globalThis, "navigator", {
  value: win.navigator,
  configurable: true,
  writable: true,
});
gx.HTMLElement = win.HTMLElement;
gx.Element = win.Element;
gx.Node = win.Node;
gx.DocumentFragment = win.DocumentFragment;
gx.Text = win.Text;
gx.Comment = win.Comment;
gx.Event = win.Event;
gx.MouseEvent = win.MouseEvent;
gx.CustomEvent = win.CustomEvent;
gx.getComputedStyle = win.getComputedStyle.bind(win);
gx.requestAnimationFrame = (cb: FrameRequestCallback) => setTimeout(cb, 0);
gx.IS_REACT_ACT_ENVIRONMENT = true;

type Call = { url: string; method: string };

let calls: Call[] = [];
let roots: Root[] = [];
let mounts: HTMLElement[] = [];

const TODAY_ROWS = {
  last_night: [],
  tonight: [
    {
      HOME_TEAM_ABBREVIATION: "BOS",
      VISITOR_TEAM_ABBREVIATION: "NYK",
      HOME_TEAM_PTS: 100,
      VISITOR_TEAM_PTS: 98,
      GAME_STATUS_TEXT: "Final",
    },
  ],
  movers: [],
  streaks: [],
};

function envelope(rows: unknown) {
  return {
    ok: true,
    json: async () => ({ ok: true, rows }),
  };
}

function mockFetch({ empty = false, offline = false } = {}) {
  calls = [];
  clearEnvelopeCache();
  gx.fetch = ((url: string, init?: RequestInit) => {
    const u = String(url);
    const method = init?.method || "GET";
    calls.push({ url: u, method });
    if (offline) return Promise.reject(new TypeError("offline"));
    if (u.includes("/today?") && method === "GET") {
      return Promise.resolve(envelope(empty ? { ...TODAY_ROWS, tonight: [] } : TODAY_ROWS));
    }
    if (u.includes("/movers?")) {
      return Promise.resolve(envelope({ climbers: empty ? [] : [{ player: "Shai Gilgeous-Alexander", team: "OKC", rank_change: 2, rank_base: 3, rank_now: 1, pts_change: 1.4 }], fallers: [], new_entries: [] }));
    }
    if (u.includes("/watchlist") && method === "GET" && !u.includes("entity_type")) {
      return Promise.resolve(envelope([]));
    }
    if (u.includes("/watchlist") && method === "POST") {
      return Promise.resolve(envelope({ added: true }));
    }
    if (u.includes("/watchlist") && method === "DELETE") {
      return Promise.resolve(envelope({ removed: true }));
    }
    return Promise.reject(new TypeError("unexpected " + method + " " + u));
  }) as unknown as typeof fetch;
}

function todayCalls() {
  return calls.filter((c) => c.url.includes("/today?") && c.method === "GET");
}

function watchlistGets() {
  return calls.filter(
    (c) => c.url.includes("/watchlist") && c.method === "GET" && !c.url.includes("entity_type"),
  );
}

async function mountToday(element: React.ReactElement = React.createElement(TodayPanel)) {
  const el = win.document.createElement("div");
  win.document.body.appendChild(el);
  mounts.push(el);
  const root = createRoot(el);
  roots.push(root);
  await act(async () => {
    root.render(element);
  });
  return { el, root };
}

async function unmountAll() {
  await act(async () => {
    for (const r of roots) r.unmount();
  });
  for (const m of mounts) m.remove();
  roots = [];
  mounts = [];
}

async function tick(ms = 50) {
  await act(async () => {
    await new Promise((r) => setTimeout(r, ms));
  });
}

afterEach(async () => {
  await unmountAll();
});

describe("today tab caching", () => {
  it("does not refetch today when the panel remounts", async () => {
    mockFetch();
    const first = await mountToday();
    await tick();
    assert.ok(first.el.textContent?.includes("BOS"), "slate missing:\n" + first.el.textContent);
    assert.equal(todayCalls().length, 1);
    await unmountAll();
    const second = await mountToday();
    await tick();
    assert.ok(second.el.textContent?.includes("BOS"), "slate missing after remount");
    assert.equal(todayCalls().length, 1);
  });

  it("watchlist mutations bust the cache", async () => {
    mockFetch();
    await act(async () => {
      await getWatchlist();
      await addWatchlist("player", "Test Player");
      await getWatchlist();
    });
    assert.equal(watchlistGets().length, 2);
  });
});

describe("Home design-system views", () => {
  it("renders scores, mover rows, and the workflow entry point", async () => {
    mockFetch();
    let opened = false;
    const { el } = await mountToday(React.createElement(HomeView, { onWorkflows: () => { opened = true; } }));
    await tick();
    assert.ok(el.textContent?.includes("BOS"));
    assert.ok(el.textContent?.includes("Shai Gilgeous-Alexander"));
    const buttons = [...el.querySelectorAll("button")];
    await act(async () => buttons.find((button) => button.textContent?.includes("Open workflows"))!.click());
    assert.equal(opened, true);
    await act(async () => buttons.find((button) => button.textContent === "14d")!.click());
    await tick();
    assert.ok(calls.some((call) => call.url.includes("/movers?") && call.url.includes("days=14")));
  });

  it("has useful empty states and an accessible watchlist form", async () => {
    mockFetch({ empty: true });
    const { el } = await mountToday(React.createElement(HomeView, { onWorkflows: () => {} }));
    await tick();
    assert.ok(el.textContent?.includes("No games today"));
    assert.ok(el.textContent?.includes("No movers yet"));
    assert.ok(el.textContent?.includes("Your watchlist is empty"));
    const add = [...el.querySelectorAll("button")].find((button) => button.textContent === "Add")!;
    assert.equal(add.disabled, true);
    const input = el.querySelector<HTMLInputElement>('input[aria-label="Name"]')!;
    let focused = false;
    input.focus = () => { focused = true; };
    await act(async () => [...el.querySelectorAll("button")].find((button) => button.textContent === "Add your first player")!.click());
    assert.equal(focused, true);
  });

  it("isolates unavailable data without hiding navigation or controls", async () => {
    mockFetch({ offline: true });
    const { el } = await mountToday(React.createElement(HomeView, { onWorkflows: () => {} }));
    await tick();
    assert.ok(el.textContent?.includes("Today is unavailable"));
    assert.ok(el.textContent?.includes("Movers are unavailable"));
    assert.ok(el.querySelector('[role="alert"]')?.textContent?.includes("Watchlist is unavailable"));
    assert.ok(!el.textContent?.includes("Your watchlist is empty"));
    assert.ok([...el.querySelectorAll("button")].some((button) => button.textContent?.includes("Open workflows")));
  });
});
