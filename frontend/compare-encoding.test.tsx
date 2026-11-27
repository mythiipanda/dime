import "./test-dom";
import test from "node:test";
import assert from "node:assert/strict";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

test("compare bars share one baseline and encode the honest ratio", async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost/" });
  const host = dom.window.document.getElementById("root")!;
  const { default: ArtifactCompare } = await import("./components/dime/ArtifactCompare");
  const root = createRoot(host);
  await act(async () => root.render(
    <ArtifactCompare
      aName="Alpha"
      bName="Beta"
      rows={[{ label: "Points/game", a: 24.6, b: 23.5, fmt: (v) => v.toFixed(1) }]}
    />
  ));
  const track = host.querySelector(".relative.mt-1\\.5");
  assert.ok(track, "a single shared track renders per row");
  const bars = [...track!.querySelectorAll(":scope > div")];
  assert.equal(bars.length, 2, "exactly two overlaid bars, not split lanes");
  const widths = bars.map((bar) => parseFloat((bar as HTMLElement).style.width));
  const ratio = Math.min(...widths) / Math.max(...widths);
  assert.ok(Math.abs(ratio - 23.5 / 24.6) < 0.01, `the trailing bar is ${(23.5 / 24.6 * 100).toFixed(1)}% of the leader — close races LOOK close (got ${(ratio * 100).toFixed(1)}%)`);
  assert.ok(Math.max(...widths) === 100, "the leader spans the full track");
  assert.ok(host.textContent!.includes("one baseline"), "the legend states the encoding honestly");
  assert.ok(!host.textContent!.includes("solid marks the leader"), "the misleading leader-fill legend is gone");
  await act(async () => root.unmount());
  dom.window.close();
});
