import { it } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { DimeShell, parseShellTab, shellNavigation } from "./components/shell/DimeShell";
import { availableModel, modelLabel } from "./lib/model-catalog";
import { renderToStaticMarkup } from "react-dom/server";
import { PromptBar } from "./components/ds/PromptBar";
import { AssistantTurn } from "./components/shell/ChatView";
import { aiFromRun, applyEvent } from "./lib/stream-event";
import { citationDetails } from "./lib/citation-details";
import { evidenceSources } from "./lib/evidence";
import CitedAnswerText from "./components/CitedAnswerText";
import { EvidenceAction } from "./components/ds/CitationChip";

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
  assert.deepEqual(shellNavigation.map((n) => n.label), ["Home", "Ask", "Boards", "Workflows", "Library", "Data"]);
  for (const tab of ["chat", "today", "data", "workflows"] as const) assert.equal(parseShellTab(tab), tab);
  assert.equal(parseShellTab("unknown"), "chat");
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
    assert.match(host.textContent!, /Agent-built, cited player grids/);
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
