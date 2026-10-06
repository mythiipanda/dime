import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { Profiler } from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";
import CitedAnswerText from "./components/CitedAnswerText";
import AnswerText from "./components/AnswerText";
import type { AiMessage } from "./lib/chat";

const dom = new JSDOM("<!doctype html><html><body></body></html>");
(globalThis as Record<string, unknown>).window = dom.window;
(globalThis as Record<string, unknown>).document = dom.window.document;
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
(dom.window.Element as unknown as { prototype: { scrollIntoView: () => void } }).prototype.scrollIntoView = () => {};
(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const VALUES = ["27.5", "112", "38", "9.4", "51", "7.8", "64", "102"];
const NAMES = ["Points", "Possessions", "Starts", "Assists", "Games", "Rebounds", "Minutes", "Rating"];

function anchoredAi(): AiMessage {
  return {
    text: VALUES.map((v, i) => `Claim ${i} measured ${v} units.`).join(" "),
    nodes: {
      analytics: {
        status: "complete",
        thoughts: [],
        toolCalls: [],
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
}

async function mount(el: React.ReactElement, commits: { n: number }) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const t0 = performance.now();
  await act(async () => {
    root.render(<Profiler id="p" onRender={() => commits.n++}>{el}</Profiler>);
  });
  const ms = performance.now() - t0;
  return { container, root, ms };
}

test("cited answer renders 8 anchored sources in few commits", async () => {
  const ai = anchoredAi();
  const commits = { n: 0 };
  const { root, container, ms } = await mount(
    <CitedAnswerText text={ai.text} ai={ai} />, commits);
  const markers = container.querySelectorAll("a[href^='#cite-'], button.cite-marker");
  console.log(`cited-first-render: commits=${commits.n} ms=${ms.toFixed(1)} markers=${markers.length}`);
  assert.equal(markers.length, 8);
  assert.ok(commits.n <= 3);
  await act(async () => {
    root.unmount();
  });
  container.remove();
});

test("plain answer render cost as anchor-overhead baseline", async () => {
  const ai = anchoredAi();
  const commits = { n: 0 };
  const { root, container, ms } = await mount(
    <AnswerText text={ai.text} />, commits);
  console.log(`plain-first-render: commits=${commits.n} ms=${ms.toFixed(1)}`);
  assert.ok(commits.n <= 2);
  await act(async () => {
    root.unmount();
  });
  container.remove();
});

test("opening one anchor commits once with ledger table", async () => {
  const ai = anchoredAi();
  const commits = { n: 0 };
  const { root, container } = await mount(
    <CitedAnswerText text={ai.text} ai={ai} />, commits);
  const base = commits.n;
  const first = container.querySelector("button.cite-marker") as HTMLElement | null;
  assert.ok(first);
  const t0 = performance.now();
  await act(async () => {
    first!.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  });
  const ms = performance.now() - t0;
  const tables = container.querySelectorAll("table");
  console.log(`anchor-toggle: commits=${commits.n - base} ms=${ms.toFixed(1)} tables=${tables.length}`);
  assert.equal(tables.length, 1);
  assert.ok(commits.n - base <= 2);
  await act(async () => {
    root.unmount();
  });
  container.remove();
});

test("markers plus pills render in few commits without blowing the anchor budget", async () => {
  const ai = anchoredAi();
  ai.text += " Also 99 votes and a 4.5 rating showed up unbacked.";
  ai.carry = {
    gaps: [{ kind: "missing_evidence" }],
    output_statuses: [
      { output_id: "VOTES", status: "incomplete", value: "99" },
      { output_id: "RATING", status: "incomplete", value: "4.5" },
    ],
  } as never;
  const commits = { n: 0 };
  const { root, container, ms } = await mount(
    <CitedAnswerText text={ai.text} ai={ai} />, commits);
  const unverified = container.querySelectorAll(".unverified-marker");
  console.log(`markers-pills-render: commits=${commits.n} ms=${ms.toFixed(1)} unverified=${unverified.length}`);
  assert.equal(unverified.length, 2);
  assert.ok(commits.n <= 3);
  await act(async () => {
    root.unmount();
  });
  container.remove();
});
