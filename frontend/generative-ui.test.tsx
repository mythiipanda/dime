import "./test-dom";
import assert from "node:assert/strict";
import test from "node:test";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { JSDOM } from "jsdom";
import ArtifactPlayerCard from "./components/dime/ArtifactPlayerCard";
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

test("table cells wrap at word boundaries rather than breaking names mid-word", () => {
  const dom = new JSDOM(renderToStaticMarkup(<ArtifactTable title="Wrap fixture" columns={[{ key: "player", label: "Player" }]} rows={[["Jonas Valančiūnas"]]} />));
  const cell = dom.window.document.querySelector("tbody td")! as HTMLElement;
  assert.equal(cell.style.overflowWrap, "break-word");
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

test("trade_verdict resolver accepts evaluator-shaped payloads and rejects malformed ones", () => {
  const valid = {
    kind: "trade_verdict", title: "Washington-for-Poeltl works", legal: true, sourceRef: "trade-src",
    teams: [
      { team: "DAL", playersOut: ["P.J. Washington"], playersIn: ["Jakob Poeltl"], outgoing: 19813044, incoming: 19500000, payrollBefore: 183593937, allowedIncoming: 28909044, matchRule: "standard TPE matching", tpeCreation: { amount: 313044, condition: "non-simultaneous only" } },
      { team: "TOR", playersOut: ["Jakob Poeltl"], playersIn: ["P.J. Washington"], outgoing: 19500000, incoming: 19813044, hardCap: "first apron" },
    ],
    checks: [{ rule: "salary matching", note: "both sides within band" }],
    evaluationTool: "get_trade_check",
  };
  const [resolved] = asResolvedArtifacts([valid]);
  assert.equal(resolved.kind, "trade_verdict");
  if (resolved.kind !== "trade_verdict") return;
  assert.equal(resolved.legal, true);
  assert.equal(resolved.teams.length, 2);
  assert.equal(resolved.teams[0].tpeCreation?.amount, 313044);
  for (const malformed of [
    { ...valid, legal: "yes" },
    { ...valid, legal: undefined },
    { ...valid, sourceRef: "" },
    { ...valid, teams: [] },
    { ...valid, teams: [{ team: "DAL" }] },
    { ...valid, teams: [{ ...valid.teams[0], outgoing: "big" }, valid.teams[1]] },
    { ...valid, teams: [{ ...valid.teams[0], playersOut: "P.J. Washington" }, valid.teams[1]] },
  ]) assert.deepEqual(asResolvedArtifacts([malformed]), []);
});

test("trade_verdict markup renders the verdict, salary math, issues and evaluator framing", async () => {
  const { default: ArtifactTradeVerdict } = await import("./components/dime/ArtifactTradeVerdict");
  const worstcase = (await import("./lib/worstcase-fixture")).worstcaseFixtures.find(a => a.kind === "trade_verdict");
  assert.ok(worstcase && worstcase.kind === "trade_verdict");
  const html = renderToStaticMarkup(<ArtifactTradeVerdict artifact={worstcase} />);
  assert.match(html, /Illegal/);
  assert.match(html, /Dikembe Mutombo Mpolondo Mukamba Jean-Jacques Wamutombo/);
  assert.match(html, /\$18\.1M/);
  assert.match(html, /\$57\.1M/);
  assert.match(html, /takes back too much/);
  assert.match(html, /trade exception/);
  assert.match(html, /hard-cap/);
  assert.match(html, /evaluator/);
  const legal = renderToStaticMarkup(<ArtifactTradeVerdict artifact={{ ...worstcase, legal: true, issues: undefined }} />);
  assert.match(legal, /Legal/);
});

test("trade_verdict copy text carries the verdict and per-team salary rows", () => {
  const artifact = {
    kind: "trade_verdict" as const, title: "t", legal: false, sourceRef: "s",
    issues: ["takes back too much"],
    teams: [{ team: "CHA", playersOut: ["Grayson Allen"], playersIn: ["Devin Booker"], outgoing: 18125000, incoming: 57078728, matchRule: "outgoing plus $9.096M" }],
    checks: [{ rule: "salary matching", note: "exceeds band" }],
  };
  const csv = artifactToCopyText(artifact);
  assert.match(csv, /Verdict,Illegal/);
  assert.match(csv, /CHA,Grayson Allen,18125000,Devin Booker,57078728/);
  assert.match(csv, /Issue,takes back too much/);
  assert.match(csv, /Check,salary matching,exceeds band/);
});

test("worst-case trade verdict survives the replay stream reducer", async () => {
  const previous = process.env.NODE_ENV;
  Object.assign(process.env, { NODE_ENV: "development" });
  try {
    const stream = new DimeStream();
    await replayStream("worstcase", { onEvent: (type, data) => stream.handle(type, data), onDone: () => stream.finish(), onError: message => assert.fail(message) });
    const verdict = stream.snapshot().artifacts.find(a => a.kind === "trade_verdict");
    assert.ok(verdict && verdict.kind === "trade_verdict");
    assert.equal(verdict.legal, false);
    assert.equal(verdict.teams.length, 2);
  } finally { Object.assign(process.env, { NODE_ENV: previous }); }
});

test("cap_summary resolver accepts evaluator-shaped payloads and rejects malformed ones", () => {
  const valid = {
    kind: "cap_summary", title: "Vucevic signing fits", sourceRef: "cap-src", team: "MEM", season: "2031-32",
    payrollBefore: 140089456, payrollAfter: 152089456, delta: 12000000,
    capRoom: 85763787, capRoomBefore: 97763787, taxRoom: 136902789, roomApron1: 149284175, roomApron2: 167554181,
    rosterBefore: 16, rosterAfter: 17,
    issues: ["roster would be 17 players - must trim to 15"],
    steps: [
      { kind: "payroll", detail: "MEM committed payroll", delta: 0, payroll: 140089456 },
      { kind: "signing", detail: "sign Nikola Vucevic", delta: 12000000, payroll: 152089456 },
    ],
    restrictions: [{ threshold: "second apron", rule: "aggregating salaries hard-caps the team" }],
    evaluationTool: "get_cap_scenario",
  };
  const [resolved] = asResolvedArtifacts([valid]);
  assert.equal(resolved.kind, "cap_summary");
  if (resolved.kind !== "cap_summary") return;
  assert.equal(resolved.team, "MEM");
  assert.equal(resolved.payrollBefore, 140089456);
  assert.equal(resolved.capRoom, 85763787);
  assert.equal(resolved.steps?.length, 2);
  assert.equal(resolved.restrictions?.length, 1);
  for (const malformed of [
    { ...valid, payrollBefore: "big" },
    { ...valid, payrollAfter: undefined },
    { ...valid, sourceRef: "" },
    { ...valid, team: "" },
    { ...valid, capRoom: "lots" },
    { ...valid, steps: [{ detail: 3 }] },
    { ...valid, restrictions: [{ threshold: "x" }] },
  ]) assert.deepEqual(asResolvedArtifacts([malformed]), []);
});

test("cap_summary markup renders payroll movement, room rows, issues and restrictions", async () => {
  const { default: ArtifactCapSummary } = await import("./components/dime/ArtifactCapSummary");
  const worstcase = (await import("./lib/worstcase-fixture")).worstcaseFixtures.find(a => a.kind === "cap_summary");
  assert.ok(worstcase && worstcase.kind === "cap_summary");
  const html = renderToStaticMarkup(<ArtifactCapSummary artifact={worstcase} />);
  assert.match(html, /PHX/);
  assert.match(html, /Payroll/);
  assert.match(html, /Cap room/);
  assert.match(html, /Room under first apron/);
  assert.match(html, /hard-cap/);
  assert.match(html, /must trim to 15/);
  assert.match(html, /over second apron/);
  assert.match(html, /sign Nikola Jokić-Valančiūnas/);
  assert.match(html, /second apron/);
  assert.match(html, /Resolved server-side/);
});

test("cap_summary copy text carries payroll, room rows, steps and issues", () => {
  const artifact = {
    kind: "cap_summary" as const, title: "t", sourceRef: "s", team: "MEM",
    payrollBefore: 140089456, payrollAfter: 152089456, delta: 12000000,
    capRoom: 85763787, roomApron1: 149284175,
    issues: ["roster would be 17 players - must trim to 15"],
    steps: [{ kind: "signing", detail: "sign Nikola Vucevic", delta: 12000000, payroll: 152089456 }],
    restrictions: [{ threshold: "second apron", rule: "no aggregation" }],
  };
  const csv = artifactToCopyText(artifact);
  assert.match(csv, /Team,MEM/);
  assert.match(csv, /Payroll Before,140089456,Payroll After,152089456,Delta,12000000/);
  assert.match(csv, /Cap Room,85763787/);
  assert.match(csv, /Step,sign Nikola Vucevic,12000000,152089456/);
  assert.match(csv, /Issue,roster would be 17/);
  assert.match(csv, /Restriction,second apron,no aggregation/);
});

test("worst-case cap summary survives the replay stream reducer", async () => {
  const previous = process.env.NODE_ENV;
  Object.assign(process.env, { NODE_ENV: "development" });
  try {
    const stream = new DimeStream();
    await replayStream("worstcase", { onEvent: (type, data) => stream.handle(type, data), onDone: () => stream.finish(), onError: message => assert.fail(message) });
    const card = stream.snapshot().artifacts.find(a => a.kind === "cap_summary");
    assert.ok(card && card.kind === "cap_summary");
    assert.equal(card.team, "PHX");
    assert.equal(card.overApron2, true);
  } finally { Object.assign(process.env, { NODE_ENV: previous }); }
});

test("trade_verdict picks parse, render and copy", async () => {
  const { default: ArtifactTradeVerdict } = await import("./components/dime/ArtifactTradeVerdict");
  const artifact = {
    kind: "trade_verdict" as const, title: "t", legal: true, sourceRef: "s",
    teams: [
      { team: "DAL", playersOut: ["Daniel Gafford"], playersIn: ["Jalen Johnson"], picksOut: [{ year: 2028, round: 1, protection: "top-3" }, { year: 2029, round: 2, swap: true }], outgoing: 17263584, incoming: 30000000 },
      { team: "ATL", playersOut: ["Jalen Johnson"], playersIn: ["Daniel Gafford"], picksIn: [{ year: 2028, round: 1, protection: "top-3" }], outgoing: 30000000, incoming: 17263584 },
    ],
  };
  const [resolved] = asResolvedArtifacts([artifact]);
  assert.equal(resolved.kind, "trade_verdict");
  if (resolved.kind !== "trade_verdict") return;
  assert.equal(resolved.teams[0].picksOut?.length, 2);
  const html = renderToStaticMarkup(<ArtifactTradeVerdict artifact={resolved} />);
  assert.match(html, /2028 1st \(top-3\)/);
  assert.match(html, /2029 2nd swap/);
  const csv = artifactToCopyText(resolved);
  assert.match(csv, /2028 1st \(top-3\)/);
  for (const malformed of [
    { ...artifact, teams: [{ ...artifact.teams[0], picksOut: [{ year: "2028" }] }, artifact.teams[1]] },
    { ...artifact, teams: [{ ...artifact.teams[0], picksOut: "none" }, artifact.teams[1]] },
  ]) assert.deepEqual(asResolvedArtifacts([malformed]), []);
});
