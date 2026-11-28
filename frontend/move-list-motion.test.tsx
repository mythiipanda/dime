import "./test-dom";
import test from "node:test";
import assert from "node:assert/strict";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";
import type { ScenarioMove } from "./lib/capsheet-fixture";

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

async function flush() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 30));
  });
}

const moveA: ScenarioMove = { kind: "waive", player: "Alpha Player", season: "2026-27" };
const moveB: ScenarioMove = { kind: "signing", player: "Beta Player", season: "2026-27", amount: 5000000 };
const moveC: ScenarioMove = { kind: "renounce", player: "Gamma Player", season: "2026-27" };

test("reordering preserves element identity — keys are stable unit identities, not indices", async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost/" });
  const host = dom.window.document.getElementById("root")!;
  const { default: ScenarioMoveList } = await import("./components/dime/ScenarioMoveList");
  let moves = [moveA, moveB, moveC];
  let pending: ScenarioMove[] | null = null;
  const root = createRoot(host);
  const render = async () => {
    const current = moves;
    await act(async () => root.render(
      <ScenarioMoveList
        moves={current}
        groups={{}}
        labels={{ describe: (m) => `${m.kind} ${m.player}` }}
        onChange={(next) => { pending = next; }}
        reorderable
      />
    ));
    await flush();
  };
  await render();
  const rowsBefore = [...host.querySelectorAll(".items-baseline.justify-between")];
  assert.ok(rowsBefore.length >= 2, "rows render");
  const alphaRow = rowsBefore.find((row) => row.textContent?.includes("Alpha Player"))!;
  const laterButton = [...alphaRow.querySelectorAll("button")].find((b) => b.getAttribute("aria-label") === "Move later")!;
  await act(async () => { laterButton.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true })); });
  assert.ok(pending, "the reorder produced a new move ordering");
  moves = pending!;
  await render();
  const rowsAfter = [...host.querySelectorAll(".items-baseline.justify-between")];
  const alphaRowAfter = rowsAfter.find((row) => row.textContent?.includes("Alpha Player"))!;
  assert.equal(alphaRowAfter, alphaRow, "the alpha row is the SAME element after reordering — no remount");
  assert.ok(rowsAfter.indexOf(alphaRowAfter) > 0, "and it moved later in the list");
  await act(async () => root.unmount());
  dom.window.close();
});

test("the move list opts into user-controlled reduced motion via MotionConfig", async () => {
  const source = await import("node:fs").then((fs) => fs.readFileSync(new URL("./components/dime/ScenarioMoveList.tsx", import.meta.url), "utf8"));
  assert.ok(source.includes('MotionConfig reducedMotion="user"'), "layout animations degrade per the user's reduced-motion preference");
  assert.equal((source.match(/key=\{unitKeys\[unitIndex\]\}/g) ?? []).length, 2, "both unit render paths key on the stable unit identity");
});
