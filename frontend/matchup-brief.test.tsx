import { describe, it, afterEach } from "node:test";
import * as assert from "node:assert";
import { JSDOM } from "jsdom";
import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import BriefsPage from "./app/briefs/page";
import { parsePreview } from "./components/MatchupPreviewView";
import {
  MATCHUP_TEAM_ABBRS,
  listBriefs,
  matchupBriefInput,
  saveBrief,
} from "./lib/briefs";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost/",
});
const win = dom.window as unknown as Window & typeof globalThis;
const gx = globalThis as unknown as Record<string, unknown>;
gx.window = win;
gx.document = win.document;
Object.defineProperty(globalThis, "navigator", {
  value: win.navigator,
  configurable: true,
  writable: true,
});
gx.HTMLElement = win.HTMLElement;
gx.Element = win.Element;
gx.Node = win.Node;
gx.Event = win.Event;
gx.MouseEvent = win.MouseEvent;
gx.getComputedStyle = win.getComputedStyle.bind(win.document);
gx.requestAnimationFrame = (cb: FrameRequestCallback) => setTimeout(cb, 0);
gx.IS_REACT_ACT_ENVIRONMENT = true;

let roots: Root[] = [];
let mounts: HTMLElement[] = [];

async function mountEl(el: React.ReactElement) {
  const host = win.document.createElement("div");
  win.document.body.appendChild(host);
  mounts.push(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(el);
  });
  await act(async () => {
    await new Promise((r) => setTimeout(r, 80));
  });
  return host;
}

function buttons(host: HTMLElement, name: string): HTMLButtonElement[] {
  return [...host.querySelectorAll("button")].filter((b) =>
    (b.textContent || "").includes(name),
  ) as HTMLButtonElement[];
}

afterEach(async () => {
  await act(async () => {
    for (const r of roots) r.unmount();
  });
  for (const m of mounts) m.remove();
  roots = [];
  mounts = [];
  win.localStorage.clear();
  win.sessionStorage.clear();
});

const CITED_ROWS = {
  game: { away: "BOS", home: "NYK", date: "Oct 9", arena: "MSG" },
  form: {
    away: { record: "2-1", last10: "7-3", streak: "W2" },
    home: { record: "3-0", last10: "8-2", streak: "W3" },
  },
  matchups: [
    {
      a: { name: "Jayson Tatum", ppg: 27.5, apg: 4.9, rpg: 8.1 },
      b: { name: "OG Anunoby", ppg: 16.4, apg: 2.1, rpg: 5.3 },
      angle: "Wing scoring",
    },
  ],
  xfactors: {
    away: { player: "Derrick White", line: "3.1 threes per game" },
    home: { player: "Josh Hart", line: "11.2 rebounds per game" },
  },
  why_watch: "Two top-three defenses.",
};

describe("matchup brief template", () => {
  it("builds a template doc from a valid team pair", () => {
    const input = matchupBriefInput("bos", "nyk");
    assert.ok(input);
    assert.equal(input.title, "BOS at NYK");
    assert.ok(input.question.includes("BOS"));
    assert.ok(input.question.includes("NYK"));
    const parsed = parsePreview(input.rows);
    assert.ok(parsed);
    assert.equal(parsed.away, "BOS");
    assert.equal(parsed.home, "NYK");
  });

  it("rejects same-team, unknown, and empty abbreviations", () => {
    assert.equal(matchupBriefInput("BOS", "bos"), null);
    assert.equal(matchupBriefInput("BOS", "ZZZ"), null);
    assert.equal(matchupBriefInput("", "NYK"), null);
    assert.equal(matchupBriefInput("BOS", ""), null);
  });

  it("offers all thirty teams", () => {
    assert.equal(MATCHUP_TEAM_ABBRS.length, 30);
    assert.ok(MATCHUP_TEAM_ABBRS.includes("BOS"));
    assert.ok(MATCHUP_TEAM_ABBRS.includes("OKC"));
  });

  it("fixture brief renders cited ratings, matchup, and decisive stats", async () => {
    const input = matchupBriefInput("BOS", "NYK");
    assert.ok(input);
    const doc = saveBrief({
      title: input.title,
      question: input.question,
      rows: CITED_ROWS,
      meta: input.meta,
    });
    const host = await mountEl(React.createElement(BriefsPage));
    await act(async () => {
      buttons(host, "BOS at NYK")[0].click();
      await new Promise((r) => setTimeout(r, 30));
    });
    assert.ok(host.textContent?.includes("2-1"));
    assert.ok(host.textContent?.includes("Jayson Tatum"));
    assert.ok(host.textContent?.includes("27.5"));
    assert.ok(host.textContent?.includes("3.1 threes per game"));
    assert.ok(host.textContent?.includes("Two top-three defenses."));
    assert.ok(listBriefs().some((b) => b.id === doc.id));
  });

  it("entry surface creates and opens a brief for the picked pair", async () => {
    const restoreFetch = gx.fetch;
    gx.fetch = (() => Promise.reject(new TypeError("offline"))) as unknown as typeof fetch;
    try {
      const host = await mountEl(React.createElement(BriefsPage));
      const away = host.querySelector('select[aria-label="Away team"]') as HTMLSelectElement;
      const home = host.querySelector('select[aria-label="Home team"]') as HTMLSelectElement;
      assert.ok(away && home);
      away.value = "BOS";
      home.value = "NYK";
      await act(async () => {
        buttons(host, "New matchup brief")[0].click();
        await new Promise((r) => setTimeout(r, 30));
      });
      assert.ok(host.textContent?.includes("BOS at NYK"));
      assert.equal(listBriefs().length, 1);
    } finally {
      if (restoreFetch === undefined) delete gx.fetch;
      else gx.fetch = restoreFetch;
    }
  });

  it("entry surface ignores an invalid pair", async () => {
    const host = await mountEl(React.createElement(BriefsPage));
    await act(async () => {
      buttons(host, "New matchup brief")[0].click();
      await new Promise((r) => setTimeout(r, 30));
    });
    assert.equal(listBriefs().length, 0);
  });
});
