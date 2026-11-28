import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { JSDOM } from "jsdom";
import { DimeShell } from "./components/shell/DimeShell";
import { AssistantTurn, PiAnswer } from "./components/shell/ChatView";
import { PromptBar } from "./components/ds/PromptBar";
import { EvidenceAction } from "./components/ds/CitationChip";
import { parseShellTab, shellNavigation, shellUrl, validThread } from "./lib/shell-navigation";
import { citationDetails } from "./lib/citation-details";
import { DimeStream, streamDimeChat } from "./lib/dime-stream";
import { scoutingEvents } from "./lib/replay-fixture";
import { getClientId, getThreads } from "./lib/api";
import { LibraryView } from "./components/shell/WorkspaceViews";

test("navigation exposes only this port's destinations, with Tools grouped", () => {
  assert.deepEqual(shellNavigation.map(item => item.label), ["Home", "Ask", "Workflows", "Boards", "Notebooks", "Library", "Data", "Trades", "Compare", "Draft", "Cap", "Planner", "History", "Matchups", "Scout", "Awards"]);
  assert.ok(shellNavigation.slice(7).every(item => "group" in item && item.group === "Tools"));
  for (const item of shellNavigation) assert.equal(parseShellTab(item.id), item.id);
  for (const invalid of [null, "explore", "lineups", "props", "invalid"]) assert.equal(parseShellTab(invalid), "chat");
  assert.equal(validThread("thread_01-abc"), true);
  for (const invalid of [null, "", "../foo", "a".repeat(81)]) assert.equal(validThread(invalid), false);
  const url = shellUrl("http://localhost/?replay=scouting&other=keep", "briefs", "thread-1");
  assert.equal(url.searchParams.get("tab"), "briefs"); assert.equal(url.searchParams.get("thread"), "thread-1");
  assert.equal(url.searchParams.get("replay"), null); assert.equal(url.searchParams.get("other"), "keep");
});

test("Library keeps conversations available when projects returns 404", async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Element: dom.window.Element, Node: dom.window.Node, IS_REACT_ACT_ENVIRONMENT: true });
  const previous = globalThis.fetch;
  globalThis.fetch = async input => String(input).includes("/projects") ? new Response("Not found", { status: 404 }) : Response.json({ threads: [{ id: "conversation", title: "Available conversation", updated: "2026-11-19", turns: 1 }] });
  const host = dom.window.document.getElementById("root")!, root = createRoot(host);
  let opened = "";
  try {
    await act(async () => root.render(<LibraryView onThread={id => { opened = id; }} />));
    assert.match(host.textContent!, /Available conversation/); assert.match(host.textContent!, /Projects could not be loaded/); assert.doesNotMatch(host.textContent!, /Could not load your library/);
    await act(async () => [...host.querySelectorAll("button")].find(button => button.textContent?.includes("Open conversation"))!.click());
    assert.equal(opened, "conversation");
    await act(async () => [...host.querySelectorAll("button")].find(button => button.textContent === "Conversations")!.click());
    assert.match(host.textContent!, /Available conversation/); assert.match(host.textContent!, /Projects could not be loaded/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; dom.window.close(); }
});

for (const mode of ["http", "network", "cached"]) test(`Library exposes ${mode} failures and retry under every filter`, async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Element: dom.window.Element, Node: dom.window.Node, IS_REACT_ACT_ENVIRONMENT: true });
  const previous = globalThis.fetch, previousStorage = globalThis.localStorage;
  globalThis.localStorage = dom.window.localStorage;
  const threads = [{ id: "cached", title: "Cached conversation", updated: "2026-11-19", turns: 1 }];
  const host = dom.window.document.getElementById("root")!, root = createRoot(host);
  try {
    if (mode === "cached") { globalThis.fetch = async () => Response.json({ threads }); await getThreads(); }
    globalThis.fetch = async () => { if (mode === "network") throw new Error("offline"); return new Response("unavailable", { status: 503 }); };
    await act(async () => root.render(<LibraryView onThread={() => {}} />));
    for (const label of ["All research", "Conversations", "Projects"]) {
      await act(async () => [...host.querySelectorAll("button")].find(button => button.textContent === label)!.click());
      if (mode === "cached") {
        assert.match(host.textContent!, /Showing cached conversations/);
        assert.ok([...host.querySelectorAll("button")].some(button => button.textContent === "Retry conversations"));
      } else {
        assert.match(host.querySelector('[role="alert"]')!.textContent!, /Could not load your library/);
        assert.ok([...host.querySelectorAll("button")].some(button => button.textContent === "Try again"));
        assert.doesNotMatch(host.textContent!, /Your research starts here/);
      }
    }
    globalThis.fetch = async input => Response.json(String(input).includes("/projects") ? { projects: [] } : { threads });
    await act(async () => [...host.querySelectorAll("button")].find(button => button.textContent === (mode === "cached" ? "Retry conversations" : "Try again"))!.click());
    await act(async () => [...host.querySelectorAll("button")].find(button => button.textContent === "Conversations")!.click());
    assert.match(host.textContent!, /Cached conversation/); assert.doesNotMatch(host.textContent!, /could not be loaded|Could not load your library/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; globalThis.localStorage = previousStorage; dom.window.close(); }
});

test("PromptBar has a real ellipsis, clean model labels and disabled unavailable models", async () => {
  const html = renderToStaticMarkup(<PromptBar value="" onChange={() => {}} onSend={() => {}} onStop={() => {}} busy={false} models={[{ id: "gemini:flash", label: "Gemini Flash", available: false }]} model={null} onModelChange={() => {}} onRetry={() => {}} />);
  assert.match(html, /basketball decision…/); assert.doesNotMatch(html, /\\u2026/);
  assert.match(html, /aria-label="Choose model"/);
  assert.doesNotMatch(html, /<select/);
  assert.match(html, /disabled=""[^>]*aria-label="Send message"/);

  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Element: dom.window.Element, Node: dom.window.Node, IS_REACT_ACT_ENVIRONMENT: true });
  const host = dom.window.document.getElementById("root")!, root = createRoot(host);
  try {
    await act(async () => root.render(<PromptBar value="" onChange={() => {}} onSend={() => {}} onStop={() => {}} busy={false} models={[{ id: "nvidia:bolt", label: "Nemotron Bolt", available: true }, { id: "gemini:flash", label: "Gemini Flash", available: false }]} model="nvidia:bolt" onModelChange={() => {}} onRetry={() => {}} />));
    await act(async () => [...host.querySelectorAll("button")].find(button => button.getAttribute("aria-label") === "Choose model")!.click());
    const rows = [...host.querySelectorAll("[role=option]")];
    assert.equal(rows.length, 2);
    assert.match(rows[1].textContent!, /Gemini Flash/);
    assert.match(rows[1].textContent!, /gemini · unavailable/);
    assert.equal(rows[1].getAttribute("aria-disabled"), "true");
    assert.equal(rows[0].getAttribute("aria-disabled"), null);
  } finally { await act(async () => root.unmount()); dom.window.close(); }
});

test("Pi citations retain exact rows, columns, units and prefixed expandable source targets", () => {
  const stream = new DimeStream();
  scoutingEvents.forEach(([type, data]) => stream.handle(type, data)); stream.finish();
  const snapshot = stream.snapshot(), carry = snapshot.carry!;
  const source = carry.sources![0], anchor = carry.submission!.blocks[0].anchors[0];
  const detail = citationDetails(source, anchor, "turn-1-");
  assert.deepEqual(detail.rows, [{ "PPG (points/game)": 32.7, "TS_PCT (ratio)": 0.637 }]);
  assert.equal(detail.target, "turn-1-source-replay-player-row-0");
  assert.equal(detail.season, "2024-25");
  assert.equal(citationDetails(source, { ...anchor, row: 99 }).target, null);
  assert.equal(citationDetails(source, { ...anchor, columns: ["MISSING"] }).target, null);
  const html = renderToStaticMarkup(<AssistantTurn message={{ role: "assistant", text: snapshot.text, artifacts: snapshot.artifacts, carry, failure: null, suggestions: [] }} prefix="turn-1-" onFollowUp={() => {}} />);
  assert.match(html, /citation-chip/); assert.match(html, /id="turn-1-source-replay-player-row-0"/); assert.match(html, /points\/game/);
  assert.equal(renderToStaticMarkup(<PiAnswer text="" carry={null} prefix="" />), "");
  const missing = renderToStaticMarkup(<PiAnswer text="Fallback" carry={{ ...carry, sources: [] }} prefix="" />);
  assert.match(missing, /Source replay-player unavailable/);
  const failure = renderToStaticMarkup(<AssistantTurn message={{ role: "assistant", text: "", artifacts: [], carry: null, failure: { kind: "connection", message: "Connection interrupted" }, suggestions: [] }} prefix="" onFollowUp={() => {}} />);
  assert.match(failure, /role="alert"/); assert.match(failure, /Couldn&#x27;t reach Dime/);
});

test("shell reads URL/history, real threads, library, theme and sends the selected thread to dev's SSE transport", async () => {
  const dom = new JSDOM("<!doctype html><html><body><div id='root'></div></body></html>", { url: "http://localhost/?tab=chat&thread=existing_thread" });
  const globals = globalThis as unknown as Record<string, unknown>;
  Object.assign(globals, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, HTMLElement: dom.window.HTMLElement, HTMLDetailsElement: dom.window.HTMLDetailsElement, IS_REACT_ACT_ENVIRONMENT: true });
  Object.defineProperty(globalThis, "navigator", { configurable: true, value: dom.window.navigator });
  dom.window.matchMedia = (() => ({ matches: true, addEventListener() {}, removeEventListener() {} })) as unknown as typeof dom.window.matchMedia;
  dom.window.HTMLElement.prototype.scrollTo = () => {};
  dom.window.HTMLElement.prototype.scrollIntoView = () => {};
  const previous = globalThis.fetch;
  let sent: Record<string, unknown> | null = null;
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    if (url.includes("/api/models")) return Response.json({ models: [{ id: "gemini:flash", engine: "gemini", available: true, default: true }], available: { gemini: true } });
    if (url.includes("/api/threads/")) return Response.json({ runs: [] });
    if (url.includes("/api/threads")) return Response.json({ threads: [{ id: "saved-thread", title: "Real saved research", updated: "2026-01-01", turns: 2 }] });
    if (url.includes("/api/projects")) return Response.json({ projects: [{ id: "p1", goal: "Server project", status: "active", updated_at: "2026-01-01" }] });
    if (url.includes("/chat/stream")) { sent = JSON.parse(String(init?.body)); return new Response('event: final_answer\ndata: {"text":"Saved response"}\n\nevent: graph_end\ndata: {}\n\n', { headers: { "content-type": "text/event-stream" } }); }
    throw new Error(`Unexpected fetch ${url}`);
  };
  const root = createRoot(dom.window.document.getElementById("root")!);
  const host = dom.window.document.getElementById("root")!;
  const click = async (label: string) => act(async () => { const button = [...host.querySelectorAll("button")].find(item => item.textContent?.trim() === label || item.getAttribute("aria-label") === label); assert.ok(button, label); button.click(); });
  try {
    await act(async () => root.render(<DimeShell />));
    assert.match(host.textContent!, /What are we looking into/); assert.match(host.textContent!, /Real saved research/);
    await click("Collapse sidebar"); assert.ok(host.querySelector(".is-collapsed")); await click("Expand sidebar");
    await click("Toggle theme"); assert.equal(dom.window.localStorage.getItem("bui-theme"), "dark");
    await click("Library"); assert.match(host.textContent!, /Server project/);
    await click("Open conversation"); assert.equal(new URL(dom.window.location.href).searchParams.get("thread"), "saved-thread");
    await act(async () => { dom.window.history.pushState({}, "", "/?tab=chat&thread=history-thread"); dom.window.dispatchEvent(new dom.window.PopStateEvent("popstate")); });
    assert.equal(new URL(dom.window.location.href).searchParams.get("thread"), "history-thread");
    await click("New chat"); assert.notEqual(new URL(dom.window.location.href).searchParams.get("thread"), "history-thread");
    await new Promise<void>((resolve, reject) => streamDimeChat("Question", { onUpdate() {}, onDone() { resolve(); }, onError(_snapshot, message) { reject(new Error(message)); } }, { thread: "real_thread", model: "gemini:flash" }));
    assert.equal((sent as unknown as { thread: string }).thread, "real_thread");
    assert.equal((sent as unknown as { client: string }).client, getClientId());
    assert.doesNotMatch(host.textContent!, /Lineups|Props|Explore/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; dom.window.close(); }
});

test("evidence action expands the specific source before navigating", async () => {
  const dom = new JSDOM("<!doctype html><html><body><div id='root'></div><details><summary>Source</summary><table><tbody><tr id='target' tabindex='-1'><td>32.7</td></tr></tbody></table></details></body></html>");
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLDetailsElement: dom.window.HTMLDetailsElement, IS_REACT_ACT_ENVIRONMENT: true });
  dom.window.HTMLElement.prototype.scrollIntoView = () => {};
  const root = createRoot(dom.window.document.getElementById("root")!);
  let navigated = false;
  try {
    await act(async () => root.render(<EvidenceAction target="target" onNavigate={() => { navigated = true; }} />));
    await act(async () => dom.window.document.querySelector("button")!.click());
    assert.equal(dom.window.document.querySelector("details")!.open, true);
    assert.equal(dom.window.document.activeElement?.id, "target"); assert.equal(navigated, true);
    assert.equal(renderToStaticMarkup(<EvidenceAction target={null} onNavigate={() => {}} />), "");
  } finally { await act(async () => root.unmount()); dom.window.close(); }
});

test("replay fixture import remains behind the development-only branch", () => {
  const events = readFileSync(new URL("./lib/stream/events.ts", import.meta.url), "utf8");
  assert.match(events, /process\.env\.NODE_ENV === "development" && opts\?\.replay/);
  assert.match(events, /import\("\.\.\/replay"\)/);
});
