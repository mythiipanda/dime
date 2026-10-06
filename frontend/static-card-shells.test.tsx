import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { JSDOM } from "jsdom";
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";
import AnswerText from "./components/AnswerText";
import Skeleton from "./components/Skeleton";
import DataArtifacts from "./components/DataArtifacts";
import BriefsPage from "./app/briefs/page";
import { DiagnosticsTable } from "./components/DiagnosticsTable";
import { saveBrief } from "./lib/briefs";
import type { BindingDiagnostic } from "./lib/diagnostics";
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
gx.Event = dom.window.Event;
gx.MouseEvent = dom.window.MouseEvent;
gx.localStorage = dom.window.localStorage;
gx.getComputedStyle = dom.window.getComputedStyle.bind(dom.window);
gx.requestAnimationFrame = (cb: FrameRequestCallback) => setTimeout(cb, 0);
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
gx.IS_REACT_ACT_ENVIRONMENT = true;

const ENTRANCE = ".t-skel-in, .chat-answer-reveal";

async function mount(el: React.ReactElement) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(el);
    await new Promise((r) => setTimeout(r, 60));
  });
  return { container, root };
}

async function unmount(root: { unmount: () => void }, container: Element) {
  await act(async () => {
    root.unmount();
  });
  container.remove();
  (globalThis as unknown as { localStorage: Storage }).localStorage.clear();
}

function loadingAi(): AiMessage {
  return { text: "partial answer", nodes: {}, done: false, streaming: true };
}

const DIAG_ROW: BindingDiagnostic = {
  run_id: "r1",
  claim_index: 0,
  requirement_kind: "stat",
  requirement_id: null,
  output_id: "STAT0",
  node_id: null,
  evidence_id: null,
  selector: "s",
  row_selector: null,
  subject_selector: null,
  subject_entity_type: null,
  subject_entity_id: null,
  declared_value: { v: 1 },
  declared_unit: null,
  domain: "nba",
  evidence_capability: "get_leaders",
  reanchor_changed: false,
  rejection: "ok",
};

test("answer and artifact shells mount with no entrance animation", async () => {
  const a = await mount(<AnswerText text="Boston leads at 9.4." />);
  assert.equal(a.container.querySelectorAll(ENTRANCE).length, 0);
  assert.ok(a.container.querySelector(".answer-md"));
  await unmount(a.root, a.container);
  const d = await mount(<DataArtifacts ai={loadingAi()} loading={true} />);
  assert.equal(d.container.querySelectorAll(ENTRANCE).length, 0);
  assert.ok(d.container.querySelector(".card-progress"));
  assert.equal(d.container.querySelectorAll(".skeleton-pulse").length, 0);
  await unmount(d.root, d.container);
});

test("loading skeleton is static lines plus a width bar", async () => {
  const s = await mount(<Skeleton lines={3} label="Loading data..." />);
  assert.equal(s.container.querySelectorAll(".skeleton-pulse").length, 0);
  assert.equal(s.container.querySelectorAll(".skeleton-row").length, 3);
  assert.ok(s.container.querySelector(".card-progress"));
  await unmount(s.root, s.container);
});

test("brief viewer and diagnostics table mount with no entrance animation", async () => {
  const prev = gx.fetch;
  gx.fetch = (async () => {
    throw new TypeError("offline");
  }) as unknown as typeof fetch;
  try {
    saveBrief({ title: "BOS at NYK", question: "How do they match up?", rows: null });
    const b = await mount(<BriefsPage />);
    assert.equal(b.container.querySelectorAll(ENTRANCE).length, 0);
    await unmount(b.root, b.container);
  } finally {
    if (prev === undefined) delete gx.fetch;
    else gx.fetch = prev;
  }
  const t = await mount(<DiagnosticsTable rows={[DIAG_ROW]} />);
  assert.equal(t.container.querySelectorAll(ENTRANCE).length, 0);
  assert.ok(t.container.querySelector("table"));
  await unmount(t.root, t.container);
});

test("global stylesheet carries no card-shell entrance animations", () => {
  const css = readFileSync(join(process.cwd(), "app", "globals.css"), "utf8");
  for (const token of [
    "t-skel-in",
    "chat-answer-reveal",
    "answer-panel-reveal",
    "skeleton-pulse",
    "dime-pulse-soft",
  ]) {
    assert.ok(!css.includes(token), `entrance token leaked: ${token}`);
  }
  assert.ok(css.includes(".card-progress"));
});
