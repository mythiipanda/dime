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

test("sign-bearing rows diverge from a visible zero line, negative bars grow left", async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost/" });
  const host = dom.window.document.getElementById("root")!;
  const { default: ArtifactCompare } = await import("./components/dime/ArtifactCompare");
  const root = createRoot(host);
  await act(async () => root.render(
    <ArtifactCompare
      aName="Nikola Jokić"
      bName="Blake Example"
      rows={[{ label: "Plus-minus", a: -482, b: 523, fmt: (v) => String(v) }]}
    />
  ));
  const span = 523 - -482;
  const zero = (-(-482) / span) * 100;
  const track = host.querySelector(".relative.mt-1\\.5");
  assert.ok(track, "track renders");
  const zeroLineEl = track!.querySelector(".w-px") as HTMLElement | null;
  assert.ok(zeroLineEl, "zero line renders");
  assert.ok(Math.abs(parseFloat(zeroLineEl!.style.left) - zero) < 0.5, `zero line at ${zero.toFixed(1)}% (got ${zeroLineEl!.style.left})`);
  const bars = [...track!.querySelectorAll(":scope > div.rounded-full")] as HTMLElement[];
  assert.equal(bars.length, 2, "two diverging bars");
  const negBarEl = bars.find((el) => el.classList.contains("bg-ink") && !el.classList.contains("bg-ink-3"))!;
  const magnitude = (482 / span) * 100;
  assert.ok(Math.abs(parseFloat(negBarEl.style.width) - magnitude) < 0.5, `negative bar width ${magnitude.toFixed(1)}% (got ${negBarEl.style.width})`);
  assert.ok(Math.abs(parseFloat(negBarEl.style.left) - (zero - magnitude)) < 0.5, "negative bar ends at the zero line");
  const posBarEl = bars.find((el) => el.className.includes("bg-ink-3") && el !== zeroLineEl)!;
  assert.ok(posBarEl, "positive bar renders");
  assert.ok(Math.abs(parseFloat(posBarEl.style.left) - zero) < 0.5, "positive bar starts at the zero line");
  await act(async () => root.unmount());
  dom.window.close();
});
