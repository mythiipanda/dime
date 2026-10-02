import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { Profiler, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";
import { createStreamBatcher } from "./lib/chat";
import type { StreamBatcher } from "./lib/chat";

const dom = new JSDOM("<!doctype html><html><body><div id=root></div></body></html>");
(globalThis as Record<string, unknown>).window = dom.window;
(globalThis as Record<string, unknown>).document = dom.window.document;
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const BURST_KINDS = ["node_update", "tool_call", "tool_result"];
const BURST: string[] = Array.from({ length: 24 }, (_, i) => BURST_KINDS[i % 3]).concat([
  "final_answer",
]);

type Api = { receive: (t: string) => void; items: () => string[] };

function Harness({
  commits,
  apiRef,
  batched,
}: {
  commits: { n: number };
  apiRef: { current: Api | null };
  batched: boolean;
}) {
  const [items, setItems] = useState<string[]>([]);
  const mirror = useRef<string[]>([]);
  mirror.current = items;
  const batcher = useRef<StreamBatcher | null>(null);
  if (batched && !batcher.current) {
    batcher.current = createStreamBatcher((events) => {
      const types = events.map((e) => e.type);
      setItems((m) => [...m, ...types]);
    });
  }
  apiRef.current = {
    receive: (t) => {
      if (batched) batcher.current!.push(t, {});
      else setItems((m) => [...m, t]);
    },
    items: () => mirror.current,
  };
  return (
    <Profiler id={batched ? "batched" : "direct"} onRender={() => commits.n++}>
      <ul>
        {items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </Profiler>
  );
}

const tick = () => new Promise<void>((r) => setTimeout(r, 0));

async function mount(el: React.ReactElement) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(el);
  });
  return { container, root };
}

test("direct setState per event commits once per task across a burst", async () => {
  const commits = { n: 0 };
  const apiRef: { current: Api | null } = { current: null };
  const { root, container } = await mount(<Harness commits={commits} apiRef={apiRef} batched={false} />);
  const base = commits.n;
  for (const type of BURST) {
    await act(async () => {
      apiRef.current!.receive(type);
      await tick();
    });
  }
  assert.equal(commits.n - base, BURST.length);
  assert.deepEqual(apiRef.current!.items(), BURST);
  await act(async () => {
    root.unmount();
  });
  container.remove();
});

test("batched burst commits once with identical final state", async () => {
  const commits = { n: 0 };
  const apiRef: { current: Api | null } = { current: null };
  const { root, container } = await mount(<Harness commits={commits} apiRef={apiRef} batched={true} />);
  const base = commits.n;
  await act(async () => {
    for (const type of BURST) {
      apiRef.current!.receive(type);
      await Promise.resolve();
    }
    await tick();
    await tick();
  });
  assert.deepEqual(apiRef.current!.items(), BURST);
  assert.equal(commits.n - base, 1);
  await act(async () => {
    root.unmount();
  });
  container.remove();
});
