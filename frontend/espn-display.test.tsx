import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";
import CitedAnswerText from "./components/CitedAnswerText";
import DataArtifacts from "./components/DataArtifacts";
import { capabilityLabel, evidenceNote, evidenceSources } from "./lib/evidence";
import type { AiMessage } from "./lib/chat";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost/",
});
const gx = globalThis as unknown as Record<string, unknown>;
gx.window = dom.window;
gx.document = dom.window.document;
gx.HTMLElement = dom.window.HTMLElement;
gx.Element = dom.window.Element;
gx.Node = dom.window.Node;
gx.Event = dom.window.MouseEvent;
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
gx.IS_REACT_ACT_ENVIRONMENT = true;

const BANNED = [
  "silver_",
  "warehouse",
  "evidence_id",
  "_season",
  "EvidenceEnvelope",
  "(missing)",
  "(rejected)",
  "live_external_no_warehouse_provenance",
];

const ESPN_META = {
  source: "espn",
  evidence_status: "ineligible",
  evidence_reason: "live_external_no_warehouse_provenance",
};

function espnAi(): AiMessage {
  return {
    text: "done",
    done: true,
    nodes: {
      tools: {
        status: "complete",
        thoughts: [],
        toolCalls: [],
        toolResults: [],
        tables: [
          {
            tool: "get_espn_scores",
            rows: [{ home: "LAL", away: "BOS", status: "Final" }],
            meta: ESPN_META,
          },
        ] as never[],
      },
    },
  };
}

test("espn tools have plain-words display names", () => {
  assert.equal(capabilityLabel("get_espn_scores"), "Live scores");
  assert.equal(capabilityLabel("get_espn_event_summary"), "Game recap");
  assert.equal(capabilityLabel("get_espn_odds"), "Odds");
});

test("ineligible evidence carries a plain-words note", () => {
  assert.equal(
    evidenceNote(ESPN_META),
    "ESPN live data — couldn't be traced to source data.",
  );
  assert.equal(evidenceNote({ evidence_status: "ok" }), null);
  assert.equal(evidenceNote({}), null);
  assert.equal(evidenceNote(null), null);
});

test("espn evidence row renders display name plus note, zero infra tokens", async () => {
  const sources = evidenceSources(espnAi());
  assert.equal(sources.length, 1);
  assert.equal(sources[0].stat, "Live scores");
  assert.ok(sources[0].note?.includes("couldn't be traced to source data."));
  for (const token of BANNED) {
    assert.ok(!sources[0].stat.includes(token), "leaked " + token);
    assert.ok(!(sources[0].note || "").includes(token), "leaked " + token);
  }
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<CitedAnswerText text="done" ai={espnAi()} />);
  });
  assert.ok(container.textContent?.includes("Live scores"));
  assert.ok(container.textContent?.includes("couldn't be traced to source data."));
  const html = container.innerHTML;
  for (const token of BANNED) assert.ok(!html.includes(token), "leaked " + token);
  await act(async () => {
    root.unmount();
  });
  container.remove();
});

test("evidence drawer titles the espn table in plain words", async () => {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<DataArtifacts ai={espnAi()} loading={false} />);
  });
  assert.ok(container.textContent?.includes("LIVE SCORES"));
  const html = container.innerHTML;
  for (const token of BANNED) assert.ok(!html.includes(token), "leaked " + token);
  await act(async () => {
    root.unmount();
  });
  container.remove();
});
