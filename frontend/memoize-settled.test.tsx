import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { Profiler } from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";
import AgentActivity from "./components/AgentActivity";
import CitedAnswerText from "./components/CitedAnswerText";
import { AiTurnBody } from "./components/ChatPanel";
import type { AiMessage, ChatMessage } from "./lib/chat";

const dom = new JSDOM("<!doctype html><html><body></body></html>");
(globalThis as Record<string, unknown>).window = dom.window;
(globalThis as Record<string, unknown>).document = dom.window.document;
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
(dom.window.Element as unknown as { prototype: { scrollIntoView: () => void } }).prototype.scrollIntoView = () => {};
(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const VALUES = ["27.5", "112"];
const NAMES = ["Points", "Assists"];

function settledMessage(): ChatMessage {
  const text = VALUES.map((v, i) => `Claim ${i} measured ${v} units.`).join(" ");
  return {
    role: "ai",
    text,
    ai: {
      text,
      nodes: {
        analytics: {
          status: "complete",
          thoughts: ["checked totals"],
          toolCalls: [
            { name: "get_leaders", args: {}, label: "Leaders", summary: "Top 30.", status: "ok", rows: 30 },
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
    },
  };
}

function streamingMessage(text: string): ChatMessage {
  return {
    role: "ai",
    text,
    ai: {
      text,
      nodes: {
        tools: {
          status: "running",
          thoughts: [],
          toolCalls: [{ name: "get_stat", args: {}, label: "Stat", status: "running" }],
          toolResults: [],
          tables: [],
        },
      },
      done: false,
      streaming: true,
    },
  };
}

function click(el: Element) {
  (el as HTMLElement).dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
}

test("settled turns skip all re-renders across fifty tail chunks", async () => {
  const settled = settledMessage();
  let tail = "";
  const settledMs = { total: 0 };
  const streamingCommits = { n: 0 };
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const renderShell = (streaming: ChatMessage) =>
    root.render(
      <>
        <Profiler
          id="settled"
          onRender={(_id, _phase, actualDuration) => {
            settledMs.total += actualDuration;
          }}
        >
          <AiTurnBody m={settled} />
        </Profiler>
        <Profiler id="streaming" onRender={() => streamingCommits.n++}>
          <AiTurnBody m={streaming} />
        </Profiler>
      </>,
    );
  await act(async () => {
    renderShell(streamingMessage(tail));
  });
  const mountMs = settledMs.total;
  settledMs.total = 0;
  for (let i = 0; i < 50; i++) {
    tail += "chunk text. ";
    await act(async () => {
      renderShell(streamingMessage(tail));
    });
  }
  console.log(`memoize-settled: mountMs=${mountMs.toFixed(2)} tailMs=${settledMs.total.toFixed(2)} streamingCommits=${streamingCommits.n}`);
  assert.equal(streamingCommits.n, 51);
  assert.ok(settledMs.total < mountMs);
  assert.ok(container.textContent?.includes("chunk text."));
  assert.ok(container.textContent?.includes("Claim 0 measured"));
  const anchors = container.querySelectorAll("button.cite-marker");
  assert.equal(anchors.length, 2);
  await act(async () => {
    root.unmount();
  });
  container.remove();
});

test("memoized settled answer keeps anchors pills and flag flow", async () => {
  const settled = settledMessage();
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<CitedAnswerText text={settled.text} ai={settled.ai!} />);
  });
  const anchors = container.querySelectorAll("button.cite-marker");
  assert.equal(anchors.length, 2);
  assert.ok(container.textContent?.includes("2024-25"));
  const first = anchors[0] as HTMLElement;
  await act(async () => {
    click(first);
  });
  assert.equal(container.querySelectorAll("table").length, 1);
  const flag = [...container.querySelectorAll("button")].find(
    (b) => b.textContent === "Flag",
  ) as HTMLElement;
  assert.ok(flag);
  await act(async () => {
    click(flag);
  });
  assert.ok(container.textContent?.includes("Download log (1)"));
  await act(async () => {
    root.unmount();
  });
  container.remove();
});
