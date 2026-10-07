import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { Profiler } from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";
import AgentActivity from "./components/AgentActivity";
import CitedAnswerText from "./components/CitedAnswerText";
import type { AiMessage } from "./lib/chat";
import { callKey, groupKey } from "./lib/renderPlan";

const dom = new JSDOM("<!doctype html><html><body></body></html>");
(globalThis as Record<string, unknown>).window = dom.window;
(globalThis as Record<string, unknown>).document = dom.window.document;
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
(dom.window.Element as unknown as { prototype: { scrollIntoView: () => void } }).prototype.scrollIntoView = () => {};
(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

function call(name: string, i: number, status: "running" | "ok" = "running") {
  return { name, args: {}, label: `Call ${i}`, summary: `Batch ${i} rows.`, status, rows: 10 + i };
}

function liveAiCalls(calls: unknown[]): AiMessage {
  return {
    text: "",
    nodes: {
      tools: {
        status: "running",
        thoughts: [],
        toolCalls: calls as never[],
        toolResults: [],
        tables: [],
      },
    },
    done: false,
    streaming: true,
  };
}

function liveAi(n: number): AiMessage {
  return liveAiCalls(Array.from({ length: n }, (_, i) => call("get_stat", i)));
}

function click(el: Element) {
  (el as HTMLElement).dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
}

test("phase identity keys stay stable per call object", () => {
  const a = { name: "get_x", args: {}, status: "ok" } as never;
  const b = { name: "get_x", args: {}, status: "ok" } as never;
  assert.equal(callKey(a as never), callKey(a as never));
  assert.notEqual(callKey(a as never), callKey(b as never));
  assert.equal(groupKey("get_x", undefined, a as never), groupKey("get_x", undefined, a as never));
  const withId = { id: "corr-1", name: "get_x", args: {} } as never;
  assert.equal(callKey(withId as never), "corr-1");
});

test("compact runs group while distinct tools stay standalone", async () => {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<AgentActivity ai={liveAi(3)} />);
  });
  assert.ok(container.textContent?.includes("Did 3 things"));
  const summary = container.querySelector("summary") as HTMLElement;
  await act(async () => {
    click(summary);
  });
  assert.ok(container.textContent?.includes("3 runs"));
  const group = [...container.querySelectorAll("button")].find((b) =>
    (b.textContent || "").includes("runs"),
  ) as HTMLElement;
  assert.ok(group);
  await act(async () => {
    click(group);
  });
  assert.ok(container.textContent?.includes("Batch 0 rows."));
  assert.ok(container.textContent?.includes("Batch 2 rows."));
  await act(async () => {
    root.unmount();
  });
  container.remove();
});

test("appended phases do not remount settled rows", async () => {
  const calls = [call("get_stat", 0), call("get_stat", 1)];
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<AgentActivity ai={liveAiCalls(calls)} />);
  });
  const summary = container.querySelector("summary") as HTMLElement;
  await act(async () => {
    click(summary);
  });
  const group = [...container.querySelectorAll("button")].find((b) =>
    (b.textContent || "").includes("runs"),
  ) as HTMLElement;
  assert.ok(group);
  await act(async () => {
    click(group);
  });
  assert.ok(container.textContent?.includes("Batch 0 rows."));
  calls.push(call("get_stat", 2));
  await act(async () => {
    root.render(<AgentActivity ai={liveAiCalls(calls)} />);
  });
  assert.ok(container.textContent?.includes("Batch 0 rows."));
  assert.ok(container.textContent?.includes("Batch 2 rows."));
  assert.ok(container.textContent?.includes("Did 3 things"));
  await act(async () => {
    root.unmount();
  });
  container.remove();
});

const VALUES = ["27.5", "112", "38", "9.4", "51", "7.8", "64", "102"];
const NAMES = ["Points", "Possessions", "Starts", "Assists", "Games", "Rebounds", "Minutes", "Rating"];

test("long anchored answer keeps markers pills and the shed budget", async () => {
  const ai: AiMessage = {
    text: VALUES.map((v, i) => `Claim ${i} measured ${v} units.`).join(" "),
    nodes: {
      analytics: {
        status: "complete",
        thoughts: ["checked totals"],
        toolCalls: [
          { name: "get_leaders", args: {}, label: "Leaders", summary: "Top 30.", status: "ok", rows: 30 },
          { name: "get_totals", args: {}, label: "Totals", summary: "Totals.", status: "ok", rows: 12 },
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
    done: true,
  };
  const commits = { n: 0 };
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(
      <Profiler id="plan" onRender={() => commits.n++}>
        <AgentActivity ai={ai} />
        <CitedAnswerText text={ai.text} ai={ai} />
      </Profiler>,
    );
  });
  assert.equal(container.querySelectorAll("button.cite-marker").length, 8);
  assert.ok(container.textContent?.includes("2024-25"));
  assert.ok(commits.n <= 4);
  const nodes = container.querySelectorAll("*").length;
  console.log(`render-plan: settled=${nodes} commits=${commits.n}`);
  assert.ok(nodes <= 60);
  await act(async () => {
    root.unmount();
  });
  container.remove();
});
