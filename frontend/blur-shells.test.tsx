import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { JSDOM } from "jsdom";
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";
import AnswerText from "./components/AnswerText";
import CitedAnswerText from "./components/CitedAnswerText";
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

const BLUR_ALLOWLIST = ["stream-tail", "command-backdrop", "backdrop-blur-xs"];

function shellFilters(container: Element): Element[] {
  return [...container.querySelectorAll("*")].filter((el) => {
    const style = (el as HTMLElement).style;
    return (style.filter && style.filter !== "") || (style.backdropFilter && style.backdropFilter !== "");
  });
}

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

function settledAi(): AiMessage {
  return {
    text: "Boston measured 9.4 units.",
    nodes: {
      analytics: {
        status: "complete",
        thoughts: [],
        toolCalls: [],
        toolResults: [],
        tables: [
          {
            output_id: "STAT0",
            value: "9.4",
            display_name: "Rating",
            provenance: { capability: "get_leaders", season: "2024-25" },
          },
        ] as never[],
      },
    },
    done: true,
  };
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

test("settled answer shells carry no pinned filter and no streaming tail", async () => {
  const ai = settledAi();
  const a = await mount(<CitedAnswerText text={ai.text} ai={ai} />);
  assert.equal(shellFilters(a.container).length, 0);
  assert.equal(a.container.querySelectorAll(".stream-tail").length, 0);
  assert.ok(a.container.querySelector("button.cite-marker"));
  await unmount(a.root, a.container);
  const p = await mount(<AnswerText text="Boston leads at 9.4." />);
  assert.equal(shellFilters(p.container).length, 0);
  assert.equal(p.container.querySelectorAll(".stream-tail").length, 0);
  await unmount(p.root, p.container);
});

test("evidence drawer settled card and skeleton carry no pinned filter", async () => {
  const d = await mount(<DataArtifacts ai={settledAi()} loading={false} />);
  assert.equal(shellFilters(d.container).length, 0);
  assert.equal(d.container.querySelectorAll(".stream-tail").length, 0);
  await unmount(d.root, d.container);
  const s = await mount(<Skeleton lines={3} label="Loading data..." />);
  assert.equal(shellFilters(s.container).length, 0);
  await unmount(s.root, s.container);
});

test("brief viewer and diagnostics table carry no pinned filter", async () => {
  const prev = gx.fetch;
  gx.fetch = (async () => {
    throw new TypeError("offline");
  }) as unknown as typeof fetch;
  try {
    saveBrief({ title: "BOS at NYK", question: "How do they match up?", rows: null });
    const b = await mount(<BriefsPage />);
    assert.equal(shellFilters(b.container).length, 0);
    assert.equal(b.container.querySelectorAll(".stream-tail").length, 0);
    await unmount(b.root, b.container);
  } finally {
    if (prev === undefined) delete gx.fetch;
    else gx.fetch = prev;
  }
  const t = await mount(<DiagnosticsTable rows={[DIAG_ROW]} />);
  assert.equal(shellFilters(t.container).length, 0);
  await unmount(t.root, t.container);
});

test("blur sources are limited to the transient allowlist", () => {
  const hits: string[] = [];
  const css = readFileSync(join(process.cwd(), "app", "globals.css"), "utf8");
  let context = "";
  for (const [i, line] of css.split("\n").entries()) {
    const trimmed = line.trim();
    if (trimmed.endsWith("{")) context = trimmed;
    if (/blur|backdrop-filter/i.test(line) && ![context, line].some((s) => BLUR_ALLOWLIST.some((a) => s.includes(a)))) {
      hits.push(`globals.css:${i + 1}:${trimmed}`);
    }
  }
  const walk = (dir: string) => {
    for (const name of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, name.name);
      if (name.isDirectory()) {
        if (name.name !== "node_modules") walk(full);
      } else if (/\.tsx?$/.test(name.name)) {
        const src = readFileSync(full, "utf8");
        for (const [i, line] of src.split("\n").entries()) {
          if (/backdropFilter|backdrop-filter|filter:\s*blur|blur\(/i.test(line) && !/blurTail|BLUR_ALLOWLIST/.test(line) && !BLUR_ALLOWLIST.some((a) => line.includes(a))) {
            hits.push(`${full}:${i + 1}:${line.trim()}`);
          }
        }
      }
    }
  };
  walk(join(process.cwd(), "components"));
  walk(join(process.cwd(), "app"));
  assert.deepEqual(hits, []);
});
