import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { act } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";
import { Button } from "./components/ds/Button";
import { SegmentedControl } from "./components/ds/SegmentedControl";
import { TextField } from "./components/ds/TextField";

test("actions do not submit a form unless explicitly marked submit", async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Element: dom.window.Element, Node: dom.window.Node, IS_REACT_ACT_ENVIRONMENT: true });
  const host = dom.window.document.getElementById("root")!, root = createRoot(host);
  let submissions = 0, actions = 0;
  try {
    await act(async () => root.render(<form onSubmit={event => { event.preventDefault(); submissions++; }}><Button onClick={() => actions++}>Preview</Button><Button type="submit">Save</Button><Button loading onClick={() => actions++}>Pending</Button><Button disabled onClick={() => actions++}>Unavailable</Button></form>));
    const [preview, save, pending, disabled] = host.querySelectorAll("button");
    await act(async () => { preview.click(); pending.click(); disabled.click(); });
    assert.equal(actions, 1);
    assert.equal(submissions, 0);
    assert.equal(pending.getAttribute("aria-busy"), "true");
    assert.equal(pending.getAttribute("aria-disabled"), "true");
    assert.equal(pending.textContent, "Pending");
    await act(async () => save.click());
    assert.equal(submissions, 1);
  } finally { await act(async () => root.unmount()); dom.window.close(); }
});

test("filters expose named single-choice semantics instead of orphan tabs", () => {
  const html = renderToStaticMarkup(<SegmentedControl options={["all", "thread"]} value="thread" onChange={() => {}} label="Research filters" labels={{ all: "All research", thread: "Conversations" }} />);
  assert.match(html, /role="radiogroup"/);
  assert.match(html, /aria-label="Research filters"/);
  assert.equal((html.match(/role="radio"/g) || []).length, 2);
  assert.match(html, /aria-checked="true"/);
  assert.doesNotMatch(html, /role="tab"/);
  assert.match(html, /Conversations/);
});

test("fields retain native required, error, disabled and help associations", () => {
  const html = renderToStaticMarkup(<TextField id="research" required aria-invalid="true" aria-describedby="research-error" disabled defaultValue="Keep this draft" />);
  for (const expected of ['id="research"', 'required=""', 'aria-invalid="true"', 'aria-describedby="research-error"', 'disabled=""', 'value="Keep this draft"']) assert.ok(html.includes(expected), expected);
});

type Color = { rgb: number[]; alpha: number };
const css = readFileSync(new URL("./app/globals.css", import.meta.url), "utf8");
const variables = (section: string) => Object.fromEntries([...section.matchAll(/--([\w-]+):\s*(oklch\([^;]+\));/g)].map(match => [match[1], match[2]]));
const light = variables(css.match(/:root\s*\{([\s\S]*?)\n\}/)![1]);
const dark = { ...light, ...variables(css.match(/\.dark\s*\{([\s\S]*?)\n\}/)![1]) };
function color(value: string): Color {
  const [l, c, h, alpha = 1] = value.replace(/oklch\(|\)/g, "").split(/[\s/]+/).filter(Boolean).map(Number);
  const a = c * Math.cos(h * Math.PI / 180), b = c * Math.sin(h * Math.PI / 180);
  const ll = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (l - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const rgb = [4.0767416621 * ll - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * ll + 2.6097574011 * m - 0.3413193965 * s, -0.0041960863 * ll - 0.7034186147 * m + 1.707614701 * s].map(v => Math.max(0, Math.min(1, v))).map(v => v <= 0.0031308 ? v * 12.92 : 1.055 * v ** (1 / 2.4) - 0.055);
  return { rgb, alpha };
}
function luminance(rgb: number[]) {
  const [r, g, b] = rgb.map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
for (const [theme, palette] of [["light", light], ["dark", dark]] as const) {
  for (const [foreground, background] of [["ink", "page"], ["ink-2", "surface"], ["ink-3", "surface"], ["ink-3", "inset"], ["green", "green-tint"], ["orange", "orange-tint"], ["red", "red-tint"], ["accent-ink", "accent-tint"], ["page", "accent-ink"], ["page", "green"], ["page", "red"]]) {
    test(`${theme} ${foreground} on ${background} meets normal-text contrast`, () => {
      const fg = color(palette[foreground]), bg = color(palette[background]), surface = color(palette.surface);
      const composite = bg.rgb.map((v, i) => v * bg.alpha + surface.rgb[i] * (1 - bg.alpha));
      const l1 = luminance(fg.rgb), l2 = luminance(composite);
      const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
      assert.ok(ratio >= 4.5, `${ratio.toFixed(2)}:1 is below 4.5:1`);
    });
  }
}
