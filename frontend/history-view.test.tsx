import test from "node:test";
import assert from "node:assert/strict";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";

const careerPayload = {
  ok: true,
  rows: [
    { season: "1996-97", end_year: 1997, pts: 28.2, reb: 6.5, ast: 5.9, fg_pct: 0.49, fg3_pct: 0.37, min: 2555, gp: 80, raptor: 5.1 },
    { season: "1997-98", end_year: 1998, pts: 26.4, reb: 6.0, ast: 4.3, fg_pct: 0.47, fg3_pct: 0.3, min: 300, gp: 12, raptor: 3.2 },
    { season: "1998-99", end_year: 1999, pts: 27.1, reb: 6.2, ast: 4.6, fg_pct: 0.48, fg3_pct: 0.32, min: 1900, gp: 50, raptor: 4.4 },
  ],
  meta: { player_id: 893, player: "Michael Jordan" },
};

const compsPayload = {
  ok: true,
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
  meta: { features: ["PTS36"], feature_labels: { PTS36: "scoring volume (PTS/36)" } },
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
  act(() => {
    (row as HTMLElement).click();
  });
}

async function boot(compsResponder: (url: string) => unknown) {
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
    if (url.includes("/history/era-comps")) return compsResponder(url) as Response;
    if (url.includes("/history/leaders")) return Response.json({ ok: true, rows: [], meta: {} });
    throw new Error(`Unexpected fetch ${url}`);
  };
  const { default: HistoryView } = await import("./components/dime/views/HistoryView");
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  return { host, root, HistoryView, restore: () => { globalThis.fetch = previousFetch; } };
}

test("history comp cards lead with drivers, percent-format efficiency stats", async () => {
  const { host, root, HistoryView, restore } = await boot(() => Response.json(compsPayload));
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

test("history comp qualification shortfall renders honest-empty with qualifying seasons", async () => {
  const { host, root, HistoryView, restore } = await boot(() =>
    Response.json({ ok: false, error: "no qualifying season for player 893 in 1997-98; era comps pool covers 1996-97 through 2024-25 with gp>=25, min>=500" }, { status: 422 }));
  try {
    await act(async () => root.render(<HistoryView />));
    await flush();
    clickSeasonRow(host, "1997-98");
    await flush();
    const text = host.textContent ?? "";
    assert.match(text, /doesn't meet the era comps qualification|does not meet the era comps qualification/i);
    assert.match(text, /1996-97/);
    assert.match(text, /1998-99/);
    assert.ok(!text.includes("No substitute data is shown"), "qualification shortfall must not render the generic error state");
  } finally {
    await act(async () => root.unmount());
    restore();
  }
});
