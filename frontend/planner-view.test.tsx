import test from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";
import { act } from "react";

const PROJECTION = {
  ok: true,
  team: "BOS",
  base_season: "2026-27",
  seasons: [
    {
      season: "2026-27", pay_before: 198_000_000, pay_after: 198_000_000, cap_room: -33_000_000,
      players: [{ player: "Fixture Wing", salary: 30_000_000 }, { player: "Fixture Guard", salary: 20_000_000, option: "team" }],
      roster_before: 14, roster_after: 14, roster_issues: [],
      hard_cap: "", hard_cap_violation: "", exception_usage: [],
      effects: [], moves_in_season: 0, ordering_notes: [],
      lines: { cap: 164_961_000, tax: 200_428_000, apron1: 209_015_000, apron2: 221_686_000 },
      lines_projected: false,
    },
    {
      season: "2027-28", pay_before: 150_000_000, pay_after: 162_000_000, cap_room: 14_000_000,
      players: [{ player: "Fixture Wing", salary: 30_000_000 }],
      roster_before: 10, roster_after: 11, roster_issues: [],
      hard_cap: "mle apron", hard_cap_violation: "", exception_usage: ["mle"],
      effects: [
        { move: 0, kind: "signing", detail: "sign $12M signing", delta: 12_000_000, exactness: "exact", exception: "mle" },
        { move: 1, kind: "waive_dead", detail: "Fixture Guard dead money (approximate allocation)", delta: 6_000_000, exactness: "proxy", disclosure: "per-year guarantee allocations unavailable" },
      ],
      moves_in_season: 2, ordering_notes: [],
      lines: { cap: 176_000_000, tax: 214_000_000, apron1: 223_000_000, apron2: 237_000_000 },
      lines_projected: true,
    },
  ],
  errors: [],
  warnings: [],
  disclosures: ["signings project as one-year deals"],
};

test("planner grid renders multi-year cells, summaries, effects with exactness, and disclosures", async () => {
  const { default: PlannerView } = await import("./components/dime/views/PlannerView");
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (input) => {
    const url = String(input);
    if (url.includes("/api/cap/projection")) return Response.json(PROJECTION);
    return Response.json(null, { status: 404 });
  };
  try {
    const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost/" });
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
    await act(async () => root.render(<PlannerView />));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 40));
    });
    const text = host.textContent!;
    assert.match(text, /Cap planner/);
    assert.match(text, /Fixture Wing/);
    assert.match(text, /\$30\.0M/);
    assert.match(text, /over the cap/);
    assert.match(text, /\$14\.0M room/);
    assert.match(text, /hard-capped/);
    assert.match(text, /projected/);
    assert.match(text, /proxy/);
    assert.match(text, /per-year guarantee allocations unavailable/);
    assert.match(text, /one-year deals/);
    root.unmount();
  }
  finally {
    globalThis.fetch = originalFetch;
  }
});
