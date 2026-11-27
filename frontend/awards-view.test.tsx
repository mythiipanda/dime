import test from "node:test";
import assert from "node:assert/strict";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";

const awardsPayload = {
  ok: true,
  season: "2026-27",
  awards: [
    {
      award: "MVP",
      ok: true,
      season: "2026-27",
      candidates: [
        {
          rank: 1,
          player: "Current Alpha",
          team: "BOS",
          score: 1.42,
          drivers: [
            { stat: "team win%", value: 0.78, z: 1.4 },
            { stat: "TS%", value: 0.62, z: 1.1 },
            { stat: "PPG", value: 25.0, z: 0.8 },
          ],
          case_for: "leads the pool in team win% at 78.0",
          case_against: "weakest edge is RPG (10.0 vs pool avg 8.0)",
        },
      ],
    },
  ],
};

async function flush() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 30));
  });
}

test("awards renders fraction-scale percentage drivers as percents", async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost/?tab=awards" });
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
    if (url.includes("/api/awards")) return Response.json(awardsPayload);
    throw new Error(`Unexpected fetch ${url}`);
  };
  const { default: AwardsView } = await import("./components/dime/views/AwardsView");
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  try {
    await act(async () => root.render(<AwardsView />));
    await flush();
    const text = host.textContent ?? "";
    assert.match(text, /2026-27/);
    assert.match(text, /78\.0 team win%/);
    assert.match(text, /62\.0 ts%/);
    assert.match(text, /team win% at 78\.0/);
    assert.doesNotMatch(text, /0\.78 team win%/);
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = previousFetch;
    dom.window.close();
  }
});
