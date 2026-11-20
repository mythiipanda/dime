import { it } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { DimeShell, parseShellTab, shellNavigation } from "./components/shell/DimeShell";
import { availableModel, modelLabel } from "./lib/model-catalog";
import { renderToStaticMarkup } from "react-dom/server";
import { PromptBar } from "./components/ds/PromptBar";
import { AssistantTurn, ChatView } from "./components/shell/ChatView";
import { aiFromRun, applyEvent } from "./lib/stream-event";
import { citationDetails } from "./lib/citation-details";
import { evidenceSources } from "./lib/evidence";
import CitedAnswerText from "./components/CitedAnswerText";
import { EvidenceAction } from "./components/ds/CitationChip";
import { addColumn, addRow, newBoard, saveBoard } from "./lib/boards";

it("opens saved board URLs and prefills Ask without sending, with working Boards navigation", async () => {
  const dom = new JSDOM("<!doctype html><html><body><div id='root'></div></body></html>", { url: "http://localhost/?tab=boards&thread=t-existing" });
  const gx = globalThis as unknown as Record<string, unknown>;
  Object.assign(gx, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Element: dom.window.Element, Node: dom.window.Node, DocumentFragment: dom.window.DocumentFragment, localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
  Object.assign(dom.window.HTMLElement.prototype, { scrollIntoView() {}, attachEvent() {}, detachEvent() {} });
  const saved = saveBoard(addColumn(addRow(newBoard(), { player_id: 201939, name: "Stephen Curry", team: "GSW" }), "ppg"));
  dom.window.history.replaceState({}, "", `/?tab=boards&board=${saved.id}`);
  const previous = globalThis.fetch;
  const sent: string[] = [];
  globalThis.fetch = async (url) => {
    const path = String(url);
    if (path.includes("/chat/stream")) sent.push(path);
    if (path.endsWith("/metrics")) return Response.json({ ok: true, metrics: [{ id: "ppg", label: "Points", category: "Scoring", unit: "per_game", higher_is_better: true, definition: "Points per game" }] });
    if (path.endsWith("/fill")) return Response.json({ ok: true, cells: {}, players: {} });
    if (path.includes("/models")) return Response.json({ models: [{ id: "test", default: true, available: true }] });
    return Response.json({ threads: [], runs: [] });
  };
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  try {
    await act(async () => root.render(<DimeShell />));
    assert.match(host.textContent!, /Stephen Curry/);
    await act(async () => [...host.querySelectorAll("button")].find((b) => b.textContent?.includes("Ask Dime about this board"))!.click());
    const url = new URL(dom.window.location.href);
    assert.equal(url.searchParams.get("tab"), "chat"); assert.equal(url.searchParams.get("board"), null);
    const draft = host.querySelector<HTMLTextAreaElement>('[aria-label="Message Dime"]')!.value;
    assert.match(draft, /Stephen Curry/); assert.match(draft, /Points/); assert.match(draft, /2025-26/);
    assert.equal(sent.length, 0);
    await act(async () => [...host.querySelectorAll("button")].find((b) => b.textContent?.trim() === "Boards")!.click());
    assert.match(host.textContent!, /Start with a template/);
    assert.equal(new URL(dom.window.location.href).searchParams.get("board"), null);
    await act(async () => { dom.window.history.pushState({}, "", `/?tab=boards&board=${saved.id}`); dom.window.dispatchEvent(new dom.window.PopStateEvent("popstate")); });
    assert.match(host.textContent!, /Stephen Curry/);
    assert.equal(sent.length, 0);
    Object.defineProperty(dom.window, "localStorage", { configurable: true, get() { throw new Error("Storage blocked"); } });
    const memoryBoard = saveBoard({ ...saved, id: "memory-board", title: "Memory shortlist" });
    await act(async () => [...host.querySelectorAll("button")].find((b) => b.textContent?.trim() === "Library")!.click());
    assert.match(host.textContent!, /Session only/);
    await act(async () => [...host.querySelectorAll("button")].find((b) => b.textContent?.trim() === "Memory shortlist")!.click());
    assert.equal(host.querySelector<HTMLInputElement>('[aria-label="Board title"]')?.value, "Memory shortlist");
    assert.match(host.textContent!, /Stephen Curry/);
    assert.equal(new URL(dom.window.location.href).searchParams.get("tab"), "boards");
    assert.equal(new URL(dom.window.location.href).searchParams.get("board"), memoryBoard.id);
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; dom.window.close(); }
});

it("shows publication caution independently of verification statuses and gaps", () => {
  const ai = applyEvent({ text: "A published answer", done: true, nodes: {} }, "custom_data", { node: "presentation", unverified_numbers: ["42.7", "18"] });
  const render = (caution: string[] | undefined) => renderToStaticMarkup(<AssistantTurn ai={{ ...ai, caution }} question="Ratings" onAsk={() => {}} />);
  assert.match(render(ai.caution), /Check numbers against tables: 42\.7, 18/);
  assert.doesNotMatch(render([]), /Check numbers against tables/);
  assert.doesNotMatch(render(undefined), /Check numbers against tables/);
});

it("ties compact citation chips to source rows and recorded query metadata", () => {
  const ai = aiFromRun({ question: "Ratings", answer: "Net rating is 9.4", created_at: "2026-01-01", suggestions: [], tables: [{ tool: "team_ratings", rows: [{ Team: "Oklahoma City", NET: 9.4 }], meta: { season: "2025-26", source: "Warehouse", sql: "SELECT NET FROM team_ratings" } }, { tool: "team_ratings", output_id: "NET", subject_display_name: "Oklahoma City", value: 9.4, provenance: { capability: "team_ratings", season: "2025-26" } }] });
  const sources = evidenceSources(ai);
  const detail = citationDetails(ai, sources[1]);
  assert.equal(detail.query, "SELECT NET FROM team_ratings");
  assert.equal(detail.season, "2025-26");
  assert.equal(detail.count, 1);
  assert.equal(detail.rows[0].NET, 9.4);
  assert.equal(detail.target, "evidence-0");
  const html = renderToStaticMarkup(<CitedAnswerText text={ai.text} ai={ai} compact />);
  assert.match(html, /citation-chip/);
  assert.doesNotMatch(html, /id="cite-/);
  const empty = aiFromRun({ question: "", answer: "", created_at: "", suggestions: [], tables: [] });
  assert.equal(renderToStaticMarkup(<CitedAnswerText text="" ai={empty} compact />), "<div></div>");
  assert.equal(citationDetails(empty, sources[0]).query, "");
});

it("resolves each citation to its own table rather than the first matching capability", () => {
  const ai = applyEvent({ text: "", done: true, nodes: {} }, "custom_data", { node: "analytics", tables: [
    { tool: "team_ratings", table_id: "okc", rows: [{ Team: "Oklahoma City", NET: 9.4 }], meta: { season: "2025-26", sql: "SELECT NET WHERE TEAM = 'OKC'" } },
    { tool: "team_ratings", table_id: "den", rows: [{ Team: "Denver", NET: 4.6 }], meta: { season: "2024-25", sql: "SELECT NET WHERE TEAM = 'DEN'" } },
    { output_id: "NET", value: 4.6, provenance: { capability: "team_ratings", table_id: "den", season: "2024-25" } },
    { output_id: "NET", value: 4.6, provenance: { capability: "team_ratings" } },
  ] });
  const sources = evidenceSources(ai);
  const first = citationDetails(ai, sources[0]);
  const second = citationDetails(ai, sources[1]);
  const bound = citationDetails(ai, sources[2]);
  const ambiguous = citationDetails(ai, sources[3]);
  assert.equal(first.rows[0].NET, 9.4);
  assert.equal(second.rows[0].NET, 4.6);
  assert.equal(second.season, "2024-25");
  assert.match(second.query, /DEN/);
  assert.equal(second.target, "evidence-1");
  assert.equal(bound.target, second.target);
  assert.equal(bound.query, second.query);
  assert.deepEqual(ambiguous.rows, []);
  assert.equal(ambiguous.query, "");
});

it("preserves statistical drivers when reopening a saved comps result", () => {
  const ai = aiFromRun({ question: "Find player comps", answer: "Comparable players", created_at: "2026-01-01", suggestions: [], tables: [{ tool: "get_comps", rows: [{ PLAYER: "Test player", TEAM: "OKC", similarity: 0.94, drivers: [{ stat: "AST_PCT", target: 31.5, comp: 29.8 }] }] }] });
  const html = renderToStaticMarkup(<AssistantTurn ai={ai} question="Find player comps" onAsk={() => {}} />);
  assert.match(html, /AST_PCT/);
  assert.match(html, /31\.5/);
  assert.match(html, /29\.8/);
  assert.match(html, /Test player/);
  assert.doesNotMatch(html, /2 records/);
});

it("reopens saved game predictions with top-level matchup and estimate", () => {
  const prediction = { tool: "get_game_prediction", matchup: { home: "OKC", away: "DEN" }, estimate: { win_prob: { OKC: 0.62, DEN: 0.38 }, projected_score: { OKC: 115, DEN: 109 }, projected_total: 224 } };
  const ai = aiFromRun({ question: "Predict OKC vs DEN", answer: "Prediction", created_at: "2026-01-01", suggestions: [], tables: [prediction] });
  const html = renderToStaticMarkup(<AssistantTurn ai={ai} question="Predict OKC vs DEN" onAsk={() => {}} />);
  assert.match(html, /62\.0%/);
  assert.match(html, /115/);
  assert.match(html, /109/);
  assert.match(html, /224/);
  const empty = renderToStaticMarkup(<AssistantTurn ai={{ ...ai, nodes: {} }} question="Predict" onAsk={() => {}} />);
  assert.doesNotMatch(empty, /evidence-artifacts/);
});

it("hides evidence navigation for live claim-only answers without inventing row targets", () => {
  const ai = applyEvent({ text: "Net rating is 9.4", done: true, nodes: {} }, "custom_data", { node: "analytics", tables: [{ output_id: "NET_RATING", value: "9.4", provenance: { capability: "team_ratings", season: "2025-26" } }] });
  const detail = citationDetails(ai, evidenceSources(ai)[0]);
  assert.equal(detail.target, null);
  assert.deepEqual(detail.rows, []);
  assert.equal(renderToStaticMarkup(<EvidenceAction target={detail.target} onNavigate={() => {}} />), "");
  const html = renderToStaticMarkup(<AssistantTurn ai={ai} question="Ratings" onAsk={() => {}} />);
  assert.match(html, /citation-chip/);
  assert.doesNotMatch(html, /evidence-artifacts/);
  assert.match(renderToStaticMarkup(<EvidenceAction target="evidence-0" onNavigate={() => {}} />), /View evidence/);
  const empty = { text: "", done: true, nodes: {} };
  assert.equal(citationDetails(empty, evidenceSources(ai)[0]).target, null);
});

it("never selects unconfigured providers and presents human model names", () => {
  const models = [{ id: "mistral:ministral-8b-2512", engine: "mistral", default: true, available: false }, { id: "gemini:gemini-2.5-flash", engine: "gemini", available: true }];
  assert.equal(availableModel(models, models[0].id), models[1].id);
  assert.equal(availableModel(models.slice(0, 1), null), null);
  assert.equal(availableModel([], null), null);
  assert.equal(modelLabel(models[0].id), "Ministral 8B");
  const html = renderToStaticMarkup(<PromptBar value="Question" onChange={() => {}} onSend={() => {}} onStop={() => {}} busy={false} models={models.map((m) => ({ ...m, label: modelLabel(m.id) }))} model={null} onModelChange={() => {}} onRetry={() => {}} />);
  assert.match(html, /disabled=""[^>]*>Ministral 8B · Unavailable/);
  assert.match(html, /disabled="" aria-label="Send message"/);
});

it("keeps old URL values and defines the requested navigation", () => {
  assert.deepEqual(shellNavigation.map((n) => n.label), ["Home", "Ask", "Boards", "Notebooks", "Workflows", "Library", "Data"]);
  for (const tab of ["chat", "today", "data", "workflows", "notebooks"] as const) assert.equal(parseShellTab(tab), tab);
  assert.equal(parseShellTab("unknown"), "chat");
});

for (const hash of ["#m-1", "", "#m-99"]) it(`restores indexed message anchors and scrolls saved history with hash '${hash}'`, async () => {
  const dom = new JSDOM("<!doctype html><html><body><div id='root'></div></body></html>", { url: `http://localhost/?tab=chat&thread=t-linked${hash}` });
  const gx = globalThis as unknown as Record<string, unknown>;
  Object.assign(gx, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Element: dom.window.Element, Node: dom.window.Node, localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
  const scrolled: { id: string; block?: string }[] = [];
  Object.assign(dom.window.HTMLElement.prototype, { scrollIntoView(this: HTMLElement, options?: ScrollIntoViewOptions) { scrolled.push({ id: this.id, block: options?.block }); }, attachEvent() {}, detachEvent() {} });
  const originalFetch = globalThis.fetch;
  let releaseHistory!: () => void;
  const historyGate = new Promise<void>((resolve) => { releaseHistory = resolve; });
  let stream!: ReadableStreamDefaultController<Uint8Array>;
  globalThis.fetch = async (url) => {
    if (String(url).includes("/models")) return Response.json({ models: [{ id: "test", available: true }] });
    if (String(url).includes("/chat/stream")) return new Response(new ReadableStream<Uint8Array>({ start(controller) { stream = controller; } }), { headers: { "Content-Type": "text/event-stream" } });
    await historyGate;
    return Response.json({ runs: [{ question: "Saved question", answer: "Saved answer", created_at: "2026-01-01", tables: [], suggestions: [] }] });
  };
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  try {
    await act(async () => root.render(<ChatView thread="t-linked" preset="Follow-up" autoSend={null} replay={null} onConsumed={() => {}} onRunDone={() => {}} />));
    assert.equal(host.querySelector("#m-1"), null);
    await act(async () => releaseHistory());
    assert.match(host.querySelector("#m-0")!.textContent!, /Saved question/);
    assert.match(host.querySelector("#m-1")!.textContent!, /Saved answer/);
    assert.deepEqual(scrolled.at(-1), hash === "#m-1" ? { id: "m-1", block: "start" } : { id: "", block: "nearest" });
    scrolled.length = 0;
    await act(async () => {
      dom.window.history.replaceState(null, "", "#m-0");
      dom.window.dispatchEvent(new dom.window.HashChangeEvent("hashchange"));
    });
    assert.deepEqual(scrolled, [{ id: "m-0", block: "start" }]);
    scrolled.length = 0;
    await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Send message"]')!.click());
    assert.equal(dom.window.location.hash, "");
    assert.equal(dom.window.location.search, "?tab=chat&thread=t-linked");
    for (const text of ["Streaming", " answer"]) {
      await act(async () => {
        stream.enqueue(new TextEncoder().encode(`event: token\ndata: ${JSON.stringify({ text })}\n\n`));
        await new Promise((resolve) => setTimeout(resolve, 40));
      });
    }
    await act(async () => {
      stream.enqueue(new TextEncoder().encode('event: done\ndata: {}\n\n'));
      stream.close();
    });
    assert.match(host.querySelector("#m-3")!.textContent!, /Streaming answer/);
    assert.ok(scrolled.length >= 2);
    assert.ok(scrolled.every((entry) => entry.id === "" && entry.block === "nearest"));
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = originalFetch;
    dom.window.close();
  }
});

for (const catalog of ["available", "unconfigured", "empty", "error"] as const) it(`dispatches workflows to a new chat with an ${catalog} model catalog`, async () => {
  const dom = new JSDOM("<!doctype html><html><body><div id='root'></div></body></html>", { url: "http://localhost/?tab=boards&thread=t-existing" });
  const gx = globalThis as unknown as Record<string, unknown>;
  Object.assign(gx, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Element: dom.window.Element, Node: dom.window.Node, DocumentFragment: dom.window.DocumentFragment, localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
  Object.assign(dom.window.HTMLElement.prototype, { scrollIntoView() {}, attachEvent() {}, detachEvent() {} });
  const originalFetch = globalThis.fetch;
  const requests: { thread: string; q: string }[] = [];
  let releaseModels!: () => void;
  const modelGate = new Promise<void>((resolve) => { releaseModels = resolve; });
  globalThis.fetch = async (url, init) => {
    if (String(url).includes("/chat/stream")) { requests.push(JSON.parse(String(init?.body))); return new Response("unavailable", { status: 503 }); }
    if (String(url).includes("/models")) {
      await modelGate;
      if (catalog === "error") return new Response("unavailable", { status: 503 });
      return Response.json({ models: catalog === "empty" ? [] : [{ id: "test", default: true, available: catalog === "available" }] });
    }
    return Response.json({ threads: [{ id: "t-existing", title: "Denver rotation", updated: "2026-01-01", turns: 1 }], runs: [] });
  };
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  const button = (label: string) => [...host.querySelectorAll("button")].find((b) => b.textContent?.trim() === label)!;
  try {
    await act(async () => root.render(<DimeShell />));
    assert.match(host.textContent!, /Start with a template/);
    assert.match(host.textContent!, /Denver rotation/);
    await act(async () => button("Workflows").click());
    assert.equal(new URL(dom.window.location.href).searchParams.get("tab"), "workflows");
    await act(async () => [...host.querySelectorAll(".workflow-card")].find((b) => b.textContent?.includes("Opponent scouting report"))!.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true })));
    const selects = host.querySelectorAll("select");
    for (const [i, value] of ["OKC", "DEN"].entries()) await act(async () => { selects[i].value = value; selects[i].dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
    await act(async () => button("Run workflow").click());
    assert.equal(requests.length, 0);
    await act(async () => releaseModels());
    await act(async () => { await new Promise((r) => setTimeout(r, 60)); });
    if (catalog === "available") {
      assert.equal(requests.length, 1);
      assert.match(requests[0].q, /OKC/);
      assert.match(requests[0].q, /DEN/);
      assert.equal(new URL(dom.window.location.href).searchParams.get("thread"), requests[0].thread);
      assert.match(host.textContent!, /Chat failed with status 503/);
      assert.doesNotMatch(host.textContent!, /No model configured/);
    } else {
      assert.equal(requests.length, 0);
      const composer = host.querySelector<HTMLTextAreaElement>('textarea[aria-label="Message Dime"]')!;
      assert.match(composer.value, /OKC/);
      assert.match(composer.value, /DEN/);
      assert.match(composer.value, /warehouse/);
      assert.match(host.querySelector('[role="status"]')!.textContent!, /No model configured — add a provider key to run this workflow/);
      assert.equal(host.querySelector<HTMLButtonElement>('[aria-label="Send message"]')!.disabled, true);
      assert.equal(host.querySelector(".user-turn"), null);
    }
    assert.notEqual(new URL(dom.window.location.href).searchParams.get("thread"), "t-existing");
    assert.equal(new URL(dom.window.location.href).searchParams.get("tab"), "chat");
    await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Collapse sidebar"]')!.click());
    assert.ok(host.querySelector(".is-collapsed"));
    await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Expand sidebar"]')!.click());
    assert.equal(host.querySelector(".is-collapsed"), null);
    await act(async () => { await new Promise((r) => setTimeout(r, 30)); });
    assert.equal(requests.length, catalog === "available" ? 1 : 0);
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = originalFetch;
    dom.window.close();
  }
});
=======
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
  assert.deepEqual(shellNavigation.map(item => item.label), ["Home", "Ask", "Workflows", "Boards", "Notebooks", "Library", "Data", "Trades", "Compare", "Draft", "Matchups", "Awards"]);
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

test("PromptBar has a real ellipsis, clean model labels and disabled unavailable models", () => {
  const html = renderToStaticMarkup(<PromptBar value="" onChange={() => {}} onSend={() => {}} onStop={() => {}} busy={false} models={[{ id: "gemini:flash", label: "Gemini Flash", available: false }]} model={null} onModelChange={() => {}} onRetry={() => {}} />);
  assert.match(html, /basketball decision…/); assert.doesNotMatch(html, /\\u2026/);
  assert.match(html, /option[^>]*disabled=""[^>]*>Gemini Flash · Unavailable/);
  assert.match(html, /disabled=""[^>]*aria-label="Send message"/);
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
  assert.match(failure, /role="alert"/); assert.match(failure, /Connection interrupted/);
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
>>>>>>> origin/dev
