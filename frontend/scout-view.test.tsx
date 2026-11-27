import test from "node:test";
import assert from "node:assert/strict";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";

test("scout rotation renders per-game points rather than season totals", async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost/?tab=scout" });
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
    if (url.includes("/scout-dossier")) {
      return Response.json({
        ok: true,
        season: "2025-26",
        sections: {
          rotation: {
            source: "rotation_check",
            ok: true,
            rows: {
              tiers: {
                core: [{ PLAYER: "Jaylen Brown", PLAYER_ID: 1627759, GP: 71, MPG: 34.4, PPG: 28.7, PTS: 2037.7 }],
                bench: [],
                fringe: [],
              },
            },
          },
        },
      });
    }
    throw new Error(`Unexpected fetch ${url}`);
  };
  const { default: ScoutView } = await import("./components/dime/views/ScoutView");
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  try {
    await act(async () => root.render(<ScoutView />));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 30));
    });
    assert.match(host.textContent!, /Jaylen Brown/);
    assert.match(host.textContent!, /34\.4 mpg/);
    assert.match(host.textContent!, /28\.7 ppg/);
    assert.doesNotMatch(host.textContent!, /2037\.7 ppg/);
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = previousFetch;
    dom.window.close();
  }
});
