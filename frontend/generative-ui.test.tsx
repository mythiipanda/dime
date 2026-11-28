import "./test-dom";
import assert from "node:assert/strict";
import test from "node:test";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { JSDOM } from "jsdom";
import ArtifactPlayerCard from "./components/dime/ArtifactPlayerCard";
import ArtifactTeamCard from "./components/dime/ArtifactTeamCard";
import ArtifactTable from "./components/dime/ArtifactTable";
import ArtifactShell from "./components/dime/ArtifactShell";
import { artifactToCopyText } from "./components/site/harness/ArtifactsView";
import { asResolvedArtifacts, DimeStream } from "./lib/dime-stream";
import { generativeFixtures, playerCardFixture } from "./lib/generative-fixture";
import { replayName, replayStream } from "./lib/replay";
import { loadChatRuns } from "./lib/chat-persistence";

test("player-card catalog rejects malformed payloads and arbitrary component names", () => {
  assert.equal(asResolvedArtifacts([playerCardFixture])[0].kind, "player_card");
  for (const overrides of [
    { playerName: "" }, { sourceRef: "" }, { sourceRow: -1 }, { sourceRow: 0.5 }, { nameColumn: "" },
    { metrics: [] }, { metrics: Array(7).fill(playerCardFixture.metrics[0]) },
    { metrics: [{ column: "points", label: "Scoring", value: "24.6" }] },
    { metrics: [{ column: "points", label: "Scoring", value: Infinity }] },
  ]) assert.deepEqual(asResolvedArtifacts([{ ...playerCardFixture, ...overrides }]), []);
  for (const kind of ["script", "iframe", "constructor", "__proto__", "toString"]) assert.deepEqual(asResolvedArtifacts([{ kind, title: "Not allowed" }]), []);
});

test("player-card markup and CSV keep exact ratios, missing values, zero and source selectors", () => {
  const html = renderToStaticMarkup(<ArtifactPlayerCard artifact={playerCardFixture} />);
  assert.match(html, /Alex Example/);
  assert.match(html, /0\.612/);
  assert.match(html, />0</);
  assert.match(html, /aria-label="Not available"/);
  assert.match(html, /Not a verification/);
  assert.match(html, /Unit not declared/);
  const csv = artifactToCopyText(playerCardFixture);
  assert.match(csv, /True shooting,0\.612,ratio,design-player-fixture,0,ts/);
  assert.match(csv, /Impact,,,design-player-fixture,0,impact/);
  assert.match(artifactToCopyText({ ...playerCardFixture, playerName: 'Alex, "Example"' }), /"Alex, ""Example"""/);
});

test("team-card section money is compact in the card and exact in source inspection", async () => {
  const host = document.createElement("div"); document.body.append(host);
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const root = createRoot(host);
  try {
    await act(async () => root.render(<ArtifactTeamCard artifact={{
      kind: "team_card", title: "LAL snapshot", teamName: "Los Angeles Lakers",
      sourceRef: "cap-src", sourceRow: 0, nameColumn: "team",
      metrics: [{ column: "payroll", label: "Payroll", value: 201332759, unit: "usd_dollars" }],
      sections: [{ label: "Apron position", sourceRef: "cap-src", sourceRow: 0,
        metrics: [{ column: "room_under_apron2", label: "Room under apron 2", value: 20353241, unit: "usd_dollars" }] }],
    }} />));
    assert.match(host.textContent!, /\$201\.3M/);
    assert.match(host.textContent!, /\$20\.4M/);
    assert.doesNotMatch(host.textContent!, /201332759/);
    assert.doesNotMatch(host.textContent!, /20353241/);
    const trigger = host.querySelector("button")!;
    await act(async () => trigger.click());
    const popover = document.querySelector('[role="dialog"]')!;
    assert.ok(popover);
    assert.match(popover.textContent!, /201332759 · usd_dollars/);
    assert.match(popover.textContent!, /20353241 · usd_dollars/);
    await act(async () => popover.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true })));
  } finally { await act(async () => root.unmount()); host.remove(); }
});

test("charts preserve observation positions when values or labels are missing", () => {
  const [chart] = asResolvedArtifacts([{ kind: "chart", title: "Gaps", xLabels: ["Oct", "", "Dec"], series: [{ name: "Player", values: [10, "bad", 30] }] }]);
  assert.equal(chart.kind, "chart");
  if (chart.kind !== "chart") return;
  assert.deepEqual(chart.series[0].values, [10, null, 30]);
  assert.deepEqual(chart.xLabels, ["Oct", "", "Dec"]);
  assert.match(artifactToCopyText(chart), /Player,10,,30/);
});

test("numeric chart years and game zero retain labels in the view and CSV", () => {
  const [chart] = asResolvedArtifacts([{ kind: "chart", title: "Years", xLabels: [2024, null, 2026, 0], series: [{ name: "Player", values: [10, null, 30, 0] }] }]);
  assert.equal(chart.kind, "chart");
  if (chart.kind !== "chart") return;
  assert.deepEqual(chart.xLabels, ["2024", "", "2026", "0"]);
  assert.match(artifactToCopyText(chart), /,2024,,2026,0/);
});

test("final submission restores catalog artifacts without duplicating streamed ones", () => {
  const stream = new DimeStream();
  stream.handle("custom_data", { artifacts: generativeFixtures });
  stream.handle("final_answer", { text: "Fixture answer", carry: { submission: { blocks: [{ text: "Fixture answer", anchors: [] }], artifacts: generativeFixtures } } });
  assert.equal(stream.snapshot().artifacts.length, generativeFixtures.length);
  const restored = new DimeStream();
  restored.handle("final_answer", { text: "Fixture answer", carry: { submission: { blocks: [{ text: "Fixture answer", anchors: [] }], artifacts: generativeFixtures } } });
  assert.deepEqual(restored.snapshot().artifacts, stream.snapshot().artifacts);
});

test("saved runs restore generative artifacts from stored submission sources", async () => {
  const previous = globalThis.fetch;
  globalThis.fetch = async input => String(input).includes("/sources")
    ? Response.json({ sources: [], submission: { blocks: [{ text: "Saved fixture", anchors: [] }], artifacts: generativeFixtures } })
    : Response.json({ runs: [{ id: "saved-generative", question: "Question", answer: "Saved fixture", tables: [] }] });
  try {
    const [run] = await loadChatRuns("generative-restore");
    assert.equal(run.snapshot.artifacts.length, generativeFixtures.length);
    assert.equal(run.snapshot.artifacts[0].kind, "player_card");
  } finally { globalThis.fetch = previous; }
});

test("generative replay is development-only and completes through the real stream reducer", async () => {
  const previous = process.env.NODE_ENV;
  assert.equal(replayName("?replay=generative", "development"), "generative");
  assert.equal(replayName("?replay=generative", "production"), null);
  Object.assign(process.env, { NODE_ENV: "development" });
  try {
    const stream = new DimeStream();
    await replayStream("generative", { onEvent: (type, data) => stream.handle(type, data), onDone: () => stream.finish(), onError: message => assert.fail(message) });
    assert.equal(stream.snapshot().done, true);
    assert.match(stream.snapshot().text, /Fictional players/);
    assert.deepEqual(stream.snapshot().artifacts.map(a => a.kind), ["player_card", "chart", "chart", "table", "compare", "scatter", "shot_chart", "team_card", "memo"]);
  } finally { Object.assign(process.env, { NODE_ENV: previous }); }
});

test("sortable evidence tables announce ordering, retain missing-last sorting and local overflow", async () => {
  const host = document.createElement("div"); document.body.append(host);
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const root = createRoot(host);
  try {
    await act(async () => root.render(<ArtifactTable title="Fixture ranking" columns={[{ key: "player", label: "Player" }, { key: "points", label: "Points/game", numeric: true }]} rows={[["Missing", null], ["Zero", 0], ["Leader", 12.3]]} />));
    const region = host.querySelector('[role="region"]')!;
    assert.equal(region.getAttribute("tabindex"), "0");
    assert.equal(region.getAttribute("aria-label"), "Fixture ranking records");
    const heading = host.querySelectorAll("th")[1];
    await act(async () => heading.querySelector("button")!.click());
    assert.equal(heading.getAttribute("aria-sort"), "descending");
    assert.deepEqual([...host.querySelectorAll("tbody tr")].map(row => row.firstChild!.textContent), ["Leader", "Zero", "Missing"]);
    await act(async () => heading.querySelector("button")!.click());
    assert.equal(heading.getAttribute("aria-sort"), "ascending");
    assert.deepEqual([...host.querySelectorAll("tbody tr")].map(row => row.firstChild!.textContent), ["Zero", "Leader", "Missing"]);
    assert.match(host.textContent!, /3 records/);
  } finally { await act(async () => root.unmount()); host.remove(); }
});

test("source-value popovers open with actual selectors and dismiss without changing the card", async () => {
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host);
  try {
    await act(async () => root.render(<ArtifactPlayerCard artifact={playerCardFixture} />));
    const trigger = host.querySelector("button")!;
    await act(async () => trigger.click());
    const popover = document.querySelector('[role="dialog"]')!;
    assert.ok(popover);
    assert.match(popover.textContent!, /design-player-fixture/);
    assert.match(popover.textContent!, /0 \(zero-based\)/);
    assert.match(popover.textContent!, /points/);
    assert.match(popover.textContent!, /0\.612 · ratio/);
    await act(async () => popover.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true })));
    assert.equal(document.querySelector('[role="dialog"]'), null);
    assert.match(host.textContent!, /Alex Example/);
  } finally { await act(async () => root.unmount()); host.remove(); }
});

test("overflowing tables expose measured cues and working scroll buttons", async () => {
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host);
  try {
    await act(async () => root.render(<ArtifactTable title="Wide fixture" columns={[{ key: "player", label: "Player" }]} rows={[["Player"]]} />));
    const region = host.querySelector<HTMLDivElement>('[role="region"]')!;
    Object.defineProperties(region, { scrollWidth: { configurable: true, value: 640 }, clientWidth: { configurable: true, value: 220 } });
    region.scrollBy = (options?: ScrollToOptions | number) => {
      const left = typeof options === "number" ? options : options?.left ?? 0;
      region.scrollLeft = Math.max(0, Math.min(420, region.scrollLeft + left));
      region.dispatchEvent(new window.Event("scroll", { bubbles: true }));
    };
    await act(async () => window.dispatchEvent(new window.Event("resize")));
    const back = host.querySelector<HTMLButtonElement>('[aria-label="Scroll table left"]')!;
    const forward = host.querySelector<HTMLButtonElement>('[aria-label="Scroll table right"]')!;
    assert.equal(back.disabled, true);
    assert.match(document.getElementById(region.getAttribute("aria-describedby")!)!.textContent!, /Scroll for all columns/);
    await act(async () => forward.click());
    assert.equal(region.scrollLeft, 165);
    assert.equal(back.disabled, false);
    await act(async () => { forward.click(); forward.click(); });
    assert.equal(region.scrollLeft, 420);
    assert.equal(forward.disabled, true);
    await act(async () => back.click());
    assert.equal(region.scrollLeft, 255);
    Object.defineProperty(region, "clientWidth", { configurable: true, value: 640 });
    region.scrollLeft = 0;
    await act(async () => window.dispatchEvent(new window.Event("resize")));
    assert.equal(host.querySelector('[aria-label="Scroll table right"]'), null);
  } finally { await act(async () => root.unmount()); host.remove(); }
});

test("clipboard denial reports an honest recovery, not a false copied status", async () => {
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host);
  const previous = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  Object.defineProperty(globalThis, "navigator", { configurable: true, value: { clipboard: { writeText: async () => { throw new Error("Denied"); } } } });
  try {
    await act(async () => root.render(<ArtifactShell title="Fixture" copyText="a,b"><p>Visible values</p></ArtifactShell>));
    await act(async () => host.querySelector("button")!.click());
    assert.match(host.querySelector('[role="status"]')!.textContent!, /Could not copy/);
    assert.equal(host.querySelector('[aria-label="Copied"]'), null);
  } finally { await act(async () => root.unmount()); host.remove(); if (previous) Object.defineProperty(globalThis, "navigator", previous); }
});

test("empty evidence tables retain their title and recovery", () => {
  const dom = new JSDOM(renderToStaticMarkup(<ArtifactTable title="Empty fixture" columns={[{ key: "player", label: "Player" }]} rows={[]} />));
  assert.equal(dom.window.document.querySelector("caption")!.textContent, "Empty fixture");
  assert.match(dom.window.document.body.textContent!, /0 records.*No records available/);
  dom.window.close();
});

test("visually hidden artifact announcements stay anchored to their local surface", () => {
  const dom = new JSDOM(renderToStaticMarkup(<ArtifactShell title="Fixture"><ArtifactTable title="Fixture records" columns={[{ key: "player", label: "Player" }]} rows={[["Player"]]} /></ArtifactShell>));
  const status = dom.window.document.querySelector('[role="status"]')!;
  const caption = dom.window.document.querySelector("caption")!;
  assert.ok(status.parentElement!.classList.contains("relative"));
  assert.ok(caption.closest("table")!.parentElement!.parentElement!.classList.contains("relative"));
  dom.window.close();
});
