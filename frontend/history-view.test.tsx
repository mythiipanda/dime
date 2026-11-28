import test from "node:test";
import assert from "node:assert/strict";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";

const careerPayload = {
  ok: true,
  rows: [
    { season: "1996-97", end_year: 1997, pts: 28.2, reb: 6.5, ast: 5.9, fg_pct: 0.49, fg3_pct: 0.37, min: 31.9, gp: 80, raptor: 5.1 },
    { season: "2009-10", end_year: 2010, pts: 0.0, reb: 0.0, ast: 0.0, fg_pct: 0.0, fg3_pct: 0.0, min: 0.1, gp: 1, raptor: null },
  ],
  meta: { player_id: 893, player: "Michael Jordan" },
};

const compsPayload = {
  ok: true,
  qualified: true,
  player: { name: "Michael Jordan", id: 893, season: "1996-97", archetype: "high-usage creator" },
  rows: [
    {
      PLAYER: "Kobe Bryant",
      PLAYER_ID: 977,
      TEAM: "LAL",
      season: "2008-09",
      age: 30,
      similarity: 90.9,
      archetype: "high-usage creator",
      shared_archetype: true,
      drivers: [
        { stat: "scoring volume (PTS/36)", target: 31.2, comp: 30.8 },
        { stat: "free-throw efficiency", target: 0.833, comp: 0.856 },
        { stat: "usage rate", target: 0.336, comp: 0.321 },
      ],
    },
  ],
  meta: { features: ["PTS36", "REB36", "AST36"], feature_labels: { PTS36: "scoring volume (PTS/36)", REB36: "rebounding (REB/36)", AST36: "playmaking (AST/36)" } },
};
(compsPayload.player as Record<string, unknown>).z = { PTS36: 2.1, REB36: -0.4, AST36: 1.2 };
(compsPayload.rows[0] as Record<string, unknown>).z = { PTS36: 2.0, REB36: -0.3, AST36: 0.9 };

const unqualifiedPayload = {
  ok: true,
  qualified: false,
  player: { name: "Michael Jordan", id: 893, season: "2009-10" },
  rows: [],
  qualification: { gp: 1, min_pg: 0.1, total_min: 0.1, rule: "gp>=25 and gp*min>=500 total minutes" },
  qualifying_seasons: ["1996-97"],
  meta: { source: "warehouse:silver_hist_player_seasons", season: "2009-10" },
};

async function flush() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 30));
  });
}

function clickSeasonRow(host: ParentNode, season: string) {
  const rows = Array.from(host.querySelectorAll("tr")) as Element[];
  const row = rows.find((r: Element) => (r.textContent ?? "").startsWith(season) && r.className.includes("cursor-pointer"));
  assert.ok(row, `season row ${season} should render in the arc table`);
  const toggle = row.querySelector("button[aria-pressed]");
  assert.ok(toggle, "season rows expose a native button — keyboard-operable, pressed state exposed");
  act(() => {
    (toggle as HTMLElement).click();
  });
}

async function boot(compsFor: (season: string) => unknown) {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost/?tab=history" });
  Object.assign(globalThis, {
    window: dom.window,
    document: dom.window.document,
    HTMLElement: dom.window.HTMLElement,
    Element: dom.window.Element,
    Node: dom.window.Node,
    IS_REACT_ACT_ENVIRONMENT: true,
  });
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (input) => {
    const url = String(input);
    if (url.includes("/history/career")) return Response.json(careerPayload);
    if (url.includes("/history/era-comps")) {
      const season = new URL(url).searchParams.get("season") ?? "";
      return Response.json(compsFor(season));
    }
    if (url.includes("/history/leaders")) return Response.json({ ok: true, rows: [], meta: {} });
    throw new Error(`Unexpected fetch ${url}`);
  };
  const { default: HistoryView } = await import("./components/dime/views/HistoryView");
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  return { host, root, HistoryView, restore: () => { globalThis.fetch = previousFetch; } };
}

test("history comp cards lead with drivers, percent-format efficiency stats", async () => {
  const { host, root, HistoryView, restore } = await boot(() => compsPayload);
  try {
    await act(async () => root.render(<HistoryView />));
    await flush();
    clickSeasonRow(host, "1996-97");
    await flush();
    const text = host.textContent ?? "";
    assert.match(text, /Kobe Bryant/);
    assert.match(text, /90\.9/);
    assert.match(text, /scoring volume/);
    assert.match(text, /31\.2/);
    assert.match(text, /30\.8/);
    assert.match(text, /83\.3%/);
    assert.match(text, /85\.6%/);
    assert.doesNotMatch(text, /0\.833/);
    assert.match(text, /33\.6%/);
    assert.match(text, /high-usage creator/);
  } finally {
    await act(async () => root.unmount());
    restore();
  }
});

test("history unqualified season renders the server-disclosed honest-empty, no comp rows", async () => {
  const { host, root, HistoryView, restore } = await boot(() => unqualifiedPayload);
  try {
    await act(async () => root.render(<HistoryView />));
    await flush();
    clickSeasonRow(host, "2009-10");
    await flush();
    const text = host.textContent ?? "";
    assert.match(text, /does not meet the era comps qualification/i);
    assert.match(text, /gp>=25 and gp\*min>=500/);
    assert.match(text, /1 gp/);
    assert.ok(text.includes("0 total minutes") || text.includes("minutes unavailable") === false);
    assert.match(text, /qualifying seasons/);
    assert.match(text, /1996-97/);
    assert.doesNotMatch(text, /Kobe Bryant/);
    assert.ok(!text.includes("No substitute data is shown"), "server-disclosed shortfall must not render the generic error state");
  } finally {
    await act(async () => root.unmount());
    restore();
  }
});

test("history shape chart renders paired z-profile bars for the selected comp", async () => {
  const { host, root, HistoryView, restore } = await boot(() => compsPayload);
  try {
    await act(async () => root.render(<HistoryView />));
    await flush();
    clickSeasonRow(host, "1996-97");
    await flush();
    const region = host.querySelector("[data-testid='shape-chart']");
    assert.ok(region, "shape chart should render with the comp cards");
    const text = region.textContent ?? "";
    assert.match(text, /scoring volume/);
    assert.match(text, /rebounding/);
    assert.match(text, /playmaking/);
    const bars = region.querySelectorAll("[data-z]");
    assert.ok(bars.length >= 6, "each feature renders a target and a comp bar");
    const target = Array.from(bars).find((b) => b.getAttribute("data-z") === "2.1" && b.getAttribute("data-side") === "target");
    assert.ok(target, "target bar carries its z value");
    const width = (target as HTMLElement).style.width;
    assert.ok(width.endsWith("%"), "bar width is proportional");
    const pct = parseFloat(width);
    assert.ok(pct > 30 && pct <= 50, `z=2.1 clamped-at-3 width should be ~35% of the full track, got ${width}`);
    assert.match(host.textContent ?? "", /shape profile/);
    const targetBar = Array.from(bars).find((b) => b.getAttribute("data-side") === "target" && b.getAttribute("data-z") === "2.1") as HTMLElement;
    const compBar = Array.from(bars).find((b) => b.getAttribute("data-side") === "comp" && b.getAttribute("data-z") === "2.0") as HTMLElement;
    assert.ok(compBar, "comp bar carries its z value");
    assert.equal(targetBar.style.left, compBar.style.left, "same-sign bars must anchor on the same side of center — overlap is the match");
    assert.equal(targetBar.style.right, compBar.style.right);
    assert.notEqual(targetBar.style.left, "", "positive z anchors left edge at center (extends right)");
  } finally {
    await act(async () => root.unmount());
    restore();
  }
});

test("browser back restores the surface from the URL spine", async () => {
  const { host, root, HistoryView, restore } = await boot(() => compsPayload);
  try {
    await act(async () => root.render(<HistoryView />));
    await flush();
    clickSeasonRow(host, "1996-97");
    await flush();
    const walk = host.querySelector("[data-testid='walk-comp']");
    act(() => { (walk as HTMLElement).click(); });
    await flush();
    assert.match(host.textContent ?? "", /Kobe Bryant 2008-09/);
    const params = new URLSearchParams((globalThis as any).window.location.search);
    params.set("player", "Michael Jordan");
    params.set("season", "1996-97");
    (globalThis as any).window.history.replaceState(null, "", `?${params.toString()}`);
    act(() => {
      (globalThis as any).window.dispatchEvent(new (globalThis as any).window.Event("popstate"));
    });
    await flush();
    assert.match(host.textContent ?? "", /Era-relative neighbors · Michael Jordan 1996-97/, "popstate recenters the surface on the URL position");
  } finally {
    await act(async () => root.unmount());
    restore();
  }
});

test("walking a comp recenters the surface on that player-season and updates the URL", async () => {
  const { host, root, HistoryView, restore } = await boot(() => compsPayload);
  try {
    await act(async () => root.render(<HistoryView />));
    await flush();
    clickSeasonRow(host, "1996-97");
    await flush();
    const walk = host.querySelector("[data-testid='walk-comp']");
    assert.ok(walk, "comp cards carry a walk affordance");
    act(() => { (walk as HTMLElement).click(); });
    await flush();
    const text = host.textContent ?? "";
    assert.match(text, /Era-relative neighbors · Kobe Bryant 2008-09/, "surface recenters on the comp player-season");
    const url = (globalThis as any).window.location.href;
    assert.ok(url.includes("player=Kobe"), `URL carries the spine position, got ${url}`);
    assert.ok(url.includes("season=2008-09"), `URL carries the season, got ${url}`);
  } finally {
    await act(async () => root.unmount());
    restore();
  }
});

test("pin mode: pinning a season keeps it as the shape anchor while walking, URL carries the pin", async () => {
  const { host, root, HistoryView, restore } = await boot(() => compsPayload);
  try {
    await act(async () => root.render(<HistoryView />));
    await flush();
    clickSeasonRow(host, "1996-97");
    await flush();
    const pinBtn = host.querySelector("[data-testid='pin-season']");
    assert.ok(pinBtn, "comps panel carries a pin affordance");
    act(() => { (pinBtn as HTMLElement).click(); });
    await flush();
    assert.match(host.textContent ?? "", /pinned: Jayson Tatum 1996-97/, "pin chip names the pinned player-season");
    let url = (globalThis as any).window.location.href;
    assert.ok(url.includes("pin_player=Jayson"), `URL carries the pin, got ${url}`);
    assert.ok(url.includes("pin_season=1996-97"));
    const walk = host.querySelector("[data-testid='walk-comp']");
    act(() => { (walk as HTMLElement).click(); });
    await flush();
    assert.match(host.textContent ?? "", /pinned: Jayson Tatum 1996-97/, "pin survives the walk");
    assert.match(host.textContent ?? "", /Kobe Bryant 2008-09/, "surface recentered");
    const chart = host.querySelector("[data-testid='shape-chart']");
    assert.ok(chart, "shape chart still renders after walking with a pin");
    assert.equal(chart.getAttribute("data-mode"), "pin", "shape chart anchors to the pin once walked away");
    assert.match(host.textContent ?? "", /vs pinned Jayson Tatum/, "pin overlay is labeled honestly");
    const unpin = host.querySelector("[data-testid='unpin']");
    assert.ok(unpin, "pin chip carries an unpin affordance");
    act(() => { (unpin as HTMLElement).click(); });
    await flush();
    assert.doesNotMatch(host.textContent ?? "", /pinned:/, "unpin clears the anchor");
    url = (globalThis as any).window.location.href;
    assert.ok(!url.includes("pin_player"), "unpin clears the URL pin");
  } finally {
    await act(async () => root.unmount());
    restore();
  }
});

test("era-window lens narrows the comp pool and rides the URL", async () => {
  const seen: string[] = [];
  const { host, root, HistoryView, restore } = await boot(() => compsPayload);
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (input) => {
    seen.push(String(input));
    return originalFetch(input);
  };
  try {
    await act(async () => root.render(<HistoryView />));
    await flush();
    clickSeasonRow(host, "1996-97");
    await flush();
    assert.ok(host.querySelector("[data-testid='window-start']"), "window start control renders");
    assert.ok(host.querySelector("[data-testid='window-end']"), "window end control renders");
    const win = (globalThis as any).window;
    const startSel = host.querySelector("[data-testid='window-start']") as any;
    const endSel = host.querySelector("[data-testid='window-end']") as any;
    const setSel = (sel: any, value: string) => {
      (Object.getOwnPropertyDescriptor(win.HTMLSelectElement.prototype, "value") as any).set.call(sel, value);
      sel.dispatchEvent(new win.Event("change", { bubbles: true }));
    };
    act(() => { setSel(startSel, "2003-04"); });
    await flush();
    act(() => { setSel(endSel, "2010-11"); });
    await flush();
    const compsCalls = seen.filter((u) => u.includes("/history/era-comps"));
    assert.ok(
      compsCalls.some((u) => u.includes("start=2003-04") && u.includes("end=2010-11")),
      `comps refetch carries the window, got ${compsCalls.join(" | ")}`,
    );
    const url = win.location.href;
    assert.ok(url.includes("window=2003-04"), `URL carries the window lens, got ${url}`);
    assert.ok(url.includes("2010-11"));
    assert.match(host.textContent ?? "", /window 2003-04/);
  } finally {
    globalThis.fetch = originalFetch;
    await act(async () => root.unmount());
    restore();
  }
});

test("compare handoff: pinned pair writes compare picks and navigates; ask envelope carries the match", async () => {
  const asks: Array<{ text: string; context: unknown }> = [];
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost/?tab=history" });
  Object.assign(globalThis, {
    window: dom.window,
    document: dom.window.document,
    HTMLElement: dom.window.HTMLElement,
    Element: dom.window.Element,
    Node: dom.window.Node,
    IS_REACT_ACT_ENVIRONMENT: true,
  });
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (input) => {
    const url = String(input);
    if (url.includes("/history/career")) return Response.json(careerPayload);
    if (url.includes("/history/era-comps")) return Response.json(compsPayload);
    if (url.includes("/history/leaders")) return Response.json({ ok: true, rows: [], meta: {} });
    throw new Error(`Unexpected fetch ${url}`);
  };
  const { default: HistoryView } = await import("./components/dime/views/HistoryView");
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  try {
    await act(async () => root.render(<HistoryView onAsk={(text: string, context: unknown) => asks.push({ text, context })} />));
    await flush();
    clickSeasonRow(host, "1996-97");
    await flush();
    const askBtn = host.querySelector("[data-testid='ask-match']");
    assert.ok(askBtn, "comps panel carries an ask-about-the-match entry");
    act(() => { (askBtn as HTMLElement).click(); });
    await flush();
    assert.equal(asks.length, 1);
    assert.match(asks[0].text, /match/i);
    const ctx = asks[0].context as { kind?: string; entities?: Record<string, unknown> };
    assert.equal(ctx.kind, "era_comps", "envelope carries the era-comps kind");
    assert.ok(ctx.entities?.player, "envelope carries the target player");
    assert.ok(ctx.entities?.comp, "envelope carries the comp player-season");
    const pinBtn = host.querySelector("[data-testid='pin-season']");
    act(() => { (pinBtn as HTMLElement).click(); });
    await flush();
    assert.ok(!host.querySelector("[data-testid='compare-pair']"), "compare handoff is meaningless before walking away — pin IS the target");
    const walkBtn = host.querySelector("[data-testid='walk-comp']");
    act(() => { (walkBtn as HTMLElement).click(); });
    await flush();
    const compareBtn = host.querySelector("[data-testid='compare-pair']");
    assert.ok(compareBtn, "pin chip carries a compare handoff once walked away");
    act(() => { (compareBtn as HTMLElement).click(); });
    await flush();
    const picks = JSON.parse((globalThis as any).window.localStorage.getItem("dime_compare_v1") ?? "[]");
    assert.equal(picks.length, 2, "compare handoff writes the pair into the compare surface's own state contract");
    assert.ok(picks.every((p: { id?: number; season?: string }) => typeof p.id === "number" && typeof p.season === "string"), "picks carry ids and seasons");
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = previousFetch;
  }
});

