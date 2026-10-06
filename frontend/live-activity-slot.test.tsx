import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";
import AgentActivity from "./components/AgentActivity";
import ActivityTimeline from "./components/ActivityTimeline";
import type { ActivityRecord, AiMessage } from "./lib/chat";

const dom = new JSDOM("<!doctype html><html><body></body></html>");
(globalThis as Record<string, unknown>).window = dom.window;
(globalThis as Record<string, unknown>).document = dom.window.document;
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
(dom.window.Element as unknown as { prototype: { scrollIntoView: () => void } }).prototype.scrollIntoView = () => {};
(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

function liveAi(n: number): AiMessage {
  return {
    text: "",
    nodes: {
      tools: {
        status: "running",
        thoughts: [],
        toolCalls: Array.from({ length: n }, (_, i) => ({
          name: `get_stat_${i}`,
          args: {},
          label: `Stat fetch ${i}`,
          summary: `Batch ${i} rows.`,
          status: "running" as const,
        })),
        toolResults: [],
        tables: [],
      },
    },
    done: false,
    streaming: true,
  };
}

function settledAi(n: number): AiMessage {
  const ai = liveAi(n);
  ai.done = true;
  ai.streaming = false;
  for (const node of Object.values(ai.nodes)) {
    node!.status = "complete";
    for (const c of node!.toolCalls) c.status = "ok";
  }
  return ai;
}

function rec(partial: Record<string, unknown>): ActivityRecord {
  return {
    eventId: "e0",
    sequence: 0,
    kind: "tool_call",
    title: "t",
    data: {},
    ...partial,
  } as ActivityRecord;
}

function click(el: Element) {
  (el as HTMLElement).dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
}

test("live slot keeps one stable element across phase changes", async () => {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<AgentActivity ai={liveAi(1)} />);
  });
  const slot = container.querySelector("[data-activity-slot]");
  assert.ok(slot);
  await act(async () => {
    root.render(<AgentActivity ai={liveAi(2)} />);
  });
  await act(async () => {
    root.render(<AgentActivity ai={liveAi(3)} />);
  });
  assert.equal(container.querySelector("[data-activity-slot]"), slot);
  assert.ok(container.textContent?.includes("Did 3 things"));
  await act(async () => {
    root.unmount();
  });
  container.remove();
});

test("two or more live phases collapse into an expanding disclosure", async () => {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<AgentActivity ai={liveAi(3)} />);
  });
  assert.ok(container.textContent?.includes("Did 3 things"));
  assert.equal(container.querySelectorAll("summary").length, 1);
  assert.ok(!container.textContent?.includes("Batch 0 rows."));
  const summary = container.querySelector("summary") as HTMLElement;
  assert.ok(summary);
  await act(async () => {
    click(summary);
  });
  assert.ok(container.textContent?.includes("Batch 0 rows."));
  assert.ok(container.textContent?.includes("Batch 2 rows."));
  await act(async () => {
    root.render(<AgentActivity ai={liveAi(4)} />);
  });
  assert.ok(container.textContent?.includes("Did 4 things"));
  assert.ok(container.textContent?.includes("Batch 3 rows."));
  await act(async () => {
    root.unmount();
  });
  container.remove();
});

test("single live phase stays flat with no disclosure", async () => {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<AgentActivity ai={liveAi(1)} />);
  });
  assert.ok(!container.textContent?.includes("Did "));
  assert.ok(!container.querySelector("summary"));
  assert.ok(container.textContent?.includes("Batch 0 rows."));
  await act(async () => {
    root.unmount();
  });
  container.remove();
});

test("settled turns keep the collapsed shed shape", async () => {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<AgentActivity ai={settledAi(3)} />);
  });
  assert.ok(container.textContent?.includes("Used 3 tools"));
  assert.ok(!container.textContent?.includes("Batch 0 rows."));
  const summary = container.querySelector("summary") as HTMLElement;
  assert.ok(summary);
  await act(async () => {
    click(summary);
  });
  assert.ok(container.textContent?.includes("Batch 0 rows."));
  await act(async () => {
    root.unmount();
  });
  container.remove();
});

test("timeline path labels two live rows as Did N things", async () => {
  const items: ActivityRecord[] = [
    rec({ eventId: "e1", sequence: 1, kind: "tool_call", title: "Tool call", status: "running", node: "tools", data: { name: "get_leaders", argument_count: 1 } }),
    rec({ eventId: "e2", sequence: 2, kind: "tool_result", title: "Tool result", status: "complete", transition: "succeeded", node: "tools", data: { name: "get_leaders", rows: 30 } }),
    rec({ eventId: "e3", sequence: 3, kind: "tool_call", title: "Tool call", status: "running", node: "tools", data: { name: "get_totals", argument_count: 2 } }),
    rec({ eventId: "e4", sequence: 4, kind: "tool_result", title: "Tool result", status: "complete", transition: "succeeded", node: "tools", data: { name: "get_totals", rows: 12 } }),
  ];
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<ActivityTimeline items={items} running={true} />);
  });
  assert.ok(container.textContent?.includes("Did 2 things"));
  const summary = container.querySelector("button") as HTMLElement;
  assert.ok(summary);
  await act(async () => {
    click(summary);
  });
  assert.ok(container.textContent?.includes("30 rows"));
  await act(async () => {
    root.unmount();
  });
  container.remove();
});
