import { describe, it, beforeEach, afterEach } from "node:test";
import * as assert from "node:assert";
import { JSDOM } from "jsdom";
import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import LineupPanel from "./components/LineupPanel";
import { panelShareUrl } from "./lib/exploreUrl";

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

type PanelProps = {
  initialTeam?: string;
  fetchTimeoutMs?: number;
  retryDelayMs?: number;
};

type Call = { url: string; signal?: AbortSignal };
type Behavior = (url: string, signal?: AbortSignal) => Promise<unknown>;

let calls: Call[] = [];
let roots: Root[] = [];
let mounts: HTMLElement[] = [];

const HONEST = "Lineup data is unavailable right now.";
const LEAKS = [
  "stats.nba.com",
  "read timeout",
  "TypeError",
  "AbortError",
  "Failed to fetch",
  "NetworkError",
];
const MADE_UP_UNIT =
  "Zelko Vrant - Pell Quist - Dax Morven - Rill Tabor - Hux Fenwick";

function setUrl(qs: string) {
  win.history.replaceState(null, "", qs ? `/${qs.startsWith("?") ? qs : `?${qs}`}` : "/");
}

function mockFetch(behaviors: Behavior[]) {
  calls = [];
  gx.fetch = ((url: string, init?: RequestInit) => {
    const signal = init?.signal as AbortSignal | undefined;
    calls.push({ url: String(url), signal });
    const fn = behaviors.length > 1 ? behaviors.shift()! : behaviors[0];
    return fn(String(url), signal);
  }) as unknown as typeof fetch;
}

function hang(url: string, signal?: AbortSignal): Promise<unknown> {
  void url;
  return new Promise((_resolve, reject) => {
    if (!signal) return;
    if (signal.aborted) reject(new DOMException("aborted", "AbortError"));
    else
      signal.addEventListener(
        "abort",
        () => reject(new DOMException("aborted", "AbortError")),
        { once: true },
      );
  });
}

function fail(url: string): Promise<unknown> {
  void url;
  return Promise.reject(new TypeError("fetch failed"));
}

function okLineups(url: string): Promise<unknown> {
  void url;
  return Promise.resolve({
    ok: true,
    json: async () => ({
      ok: true,
      data: [{ GROUP_NAME: MADE_UP_UNIT, MIN: 42.5, PLUS_MINUS: 7 }],
    }),
  });
}

async function mount(initialTeam?: string) {
  const el = win.document.createElement("div");
  win.document.body.appendChild(el);
  mounts.push(el);
  const root = createRoot(el);
  roots.push(root);
  await act(async () => {
    root.render(
      React.createElement(LineupPanel, {
        initialTeam,
        fetchTimeoutMs: 40,
        retryDelayMs: 10,
      } as PanelProps),
    );
  });
  return el;
}

async function settle(ms = 500) {
  await act(async () => {
    await new Promise((r) => setTimeout(r, ms));
  });
}

function lastLineupsCall() {
  const found = calls.filter((c) => c.url.includes("/datasets/lineups"));
  return found[found.length - 1];
}

beforeEach(() => {
  setUrl("");
});

afterEach(async () => {
  await act(async () => {
    for (const r of roots) r.unmount();
  });
  for (const m of mounts) m.remove();
  roots = [];
  mounts = [];
});

describe("lineups resilience", () => {
  it("timeout aborts, retries once, then shows honest error with no leak", async () => {
    mockFetch([hang, hang]);
    const el = await mount("DEN");
    await settle(600);
    const html = el.innerHTML;
    assert.ok(html.includes(HONEST), "honest error copy missing");
    for (const leak of LEAKS) assert.ok(!html.includes(leak), `leak: ${leak}`);
    assert.equal(calls.length, 2, "expected exactly one retry");
    assert.ok(!html.includes("<table"), "stale rows not cleared");
    assert.ok(html.includes("Try again"), "retry control missing");
    const btn = Array.from(el.querySelectorAll("button")).find(
      (b) => b.textContent === "Try again",
    );
    assert.ok(btn, "retry button missing");
    mockFetch([hang, hang]);
    await act(async () => {
      btn.dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
      await new Promise((r) => setTimeout(r, 400));
    });
    assert.equal(calls.length, 2, "retry control did not re-fire fetch");
    assert.ok(el.innerHTML.includes(HONEST), "error lost after retry");
  });

  it("retry success renders rows with no error", async () => {
    mockFetch([fail, okLineups]);
    const el = await mount("DEN");
    await settle();
    assert.equal(calls.length, 2, "expected one retry then success");
    assert.ok(el.innerHTML.includes("Vrant"), "retried rows missing");
    assert.ok(!el.innerHTML.includes(HONEST), "stale error shown");
  });

  it("teamAbbr URL round-trip: open, copy link, restore, full name, unknown", async () => {
    mockFetch([okLineups]);
    setUrl("?panel=lineups");
    await mount("nyk");
    await settle(300);
    assert.ok(
      win.location.search.includes("lineups_team=NYK"),
      "lineups_team missing from URL",
    );
    const shared = panelShareUrl(
      "http://localhost",
      "/",
      win.location.search,
      "lineups",
    );
    assert.ok(shared.includes("lineups_team=NYK"), "copy-link dropped team");
    setUrl(shared.slice(shared.indexOf("?")));
    await mount(undefined);
    await settle(300);
    assert.ok(
      (lastLineupsCall()?.url ?? "").includes("team_id=1610612752"),
      "copy-link URL did not restore NYK",
    );
    setUrl(`?panel=lineups&lineups_team=${encodeURIComponent("denver nuggets")}`);
    await mount(undefined);
    await settle(300);
    assert.ok(
      (lastLineupsCall()?.url ?? "").includes("team_id=1610612743"),
      "full team name did not map to DEN",
    );
    setUrl("?panel=lineups&lineups_team=ZZZ");
    await mount(undefined);
    await settle(300);
    assert.ok(
      (lastLineupsCall()?.url ?? "").includes("team_id=1610612738"),
      "unknown value did not fall back to BOS",
    );
  });
});
