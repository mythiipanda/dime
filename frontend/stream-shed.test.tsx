import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { Profiler } from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";
import AgentActivity from "./components/AgentActivity";
import CitedAnswerText from "./components/CitedAnswerText";
import type { AiMessage } from "./lib/chat";

const dom = new JSDOM("<!doctype html><html><body></body></html>");
(globalThis as Record<string, unknown>).window = dom.window;
(globalThis as Record<string, unknown>).document = dom.window.document;
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
(dom.window.Element as unknown as { prototype: { scrollIntoView: () => void } }).prototype.scrollIntoView = () => {};
(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const VALUES = ["27.5", "112", "38", "9.4", "51", "7.8", "64", "102"];
const NAMES = ["Points", "Possessions", "Starts", "Assists", "Games", "Rebounds", "Minutes", "Rating"];

function anchoredText(): string {
  return VALUES.map((v, i) => `Claim ${i} measured ${v} units.`).join(" ");
}

function anchoredAi(done: boolean): AiMessage {
  return {
    text: anchoredText(),
    nodes: {
      analytics: {
        status: done ? "complete" : "running",
        thoughts: [
          "pulled the scoring leaders for the window",
          "checked the possession counts against the totals",
          "confirmed the window covers the full season",
        ],
        liveThought: "reading the last evidence batch into the answer",
        toolCalls: [
          { name: "get_leaders", args: {}, label: "Scoring leaders", summary: "Top 30 scorers with per-game marks.", sql: "select a, b from c", status: done ? "ok" : "running", rows: 30 },
          { name: "get_totals", args: {}, label: "Season totals", summary: "Possession and minute totals for the window.", status: done ? "ok" : "running", rows: 12 },
          { name: "get_lineups", args: {}, label: "Lineup splits", summary: "Five-man units over the same window.", status: done ? "ok" : "running", rows: 8 },
        ],
        toolResults: [],
        tables: VALUES.map((v, i) => ({
          output_id: `STAT${i}`,
          value: v,
          display_name: NAMES[i],
          provenance: { capability: "get_leaders", season: "2024-25" },
        })) as never[],
      },
    },
    done,
    streaming: !done,
    carry: {
      verification: "partial",
      verified_claims: 6,
      output_statuses: [
        { output_id: "STAT6", status: "incomplete" },
        { output_id: "STAT7", status: "incomplete" },
      ],
      gaps: [{ kind: "missing_evidence" }],
    } as never,
  };
}

function countNodes(container: Element): number {
  return container.querySelectorAll("*").length;
}

async function mountTurn(ai: AiMessage, settled: boolean, commits: { n: number }) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const t0 = performance.now();
  await act(async () => {
    root.render(
      <Profiler id="shed" onRender={() => commits.n++}>
        <AgentActivity ai={ai} />
        {settled ? (
          <CitedAnswerText text={ai.text} ai={ai} />
        ) : (
          <div style={{ fontSize: 14, lineHeight: 1.64 }}>{ai.text}</div>
        )}
      </Profiler>,
    );
  });
  const ms = performance.now() - t0;
  return { container, root, ms };
}

test("shed streaming DOM after settle keeps the settled turn light", async () => {
  const liveCommits = { n: 0 };
  const live = await mountTurn(anchoredAi(false), false, liveCommits);
  const peak = countNodes(live.container);
  const settledCommits = { n: 0 };
  const settled = await mountTurn(anchoredAi(true), true, settledCommits);
  const after = countNodes(settled.container);
  console.log(`stream-shed: peak=${peak} settled=${after} liveCommits=${liveCommits.n} settledCommits=${settledCommits.n} settledMs=${settled.ms.toFixed(1)}`);
  assert.ok(peak <= 20, `live activity shell should stay gated, saw ${peak} nodes`);
  assert.ok(after <= 60, `settled turn should shed transient activity DOM, saw ${after} nodes`);
  assert.ok(settledCommits.n <= 4, `settled turn should commit in a small budget, saw ${settledCommits.n}`);
  await act(async () => {
    live.root.unmount();
    settled.root.unmount();
  });
  live.container.remove();
  settled.container.remove();
});

test("settled turn keeps anchors pills markers and flag flow", async () => {
  const ai = anchoredAi(true);
  const commits = { n: 0 };
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(
      <Profiler id="shed-keep" onRender={() => commits.n++}>
        <AgentActivity ai={ai} />
        <CitedAnswerText text={ai.text} ai={ai} />
      </Profiler>,
    );
  });
  const anchors = container.querySelectorAll("button.cite-marker");
  assert.equal(anchors.length, 8);
  assert.ok(container.textContent?.includes("2024-25"));
  assert.ok(container.textContent?.includes("numbers couldn't be traced to source data."));
  const first = anchors[0] as HTMLElement;
  await act(async () => {
    first.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  });
  assert.equal(container.querySelectorAll("table").length, 1);
  const buttons = Array.from(container.querySelectorAll("button")).filter(
    (b) => b.textContent === "Accept" || b.textContent === "Flag",
  );
  assert.ok(buttons.length >= 2);
  const flag = buttons.find((b) => b.textContent === "Flag") as HTMLElement;
  await act(async () => {
    flag.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  });
  assert.ok(container.textContent?.includes("Download log (1)"));
  await act(async () => {
    root.unmount();
  });
  container.remove();
});
