import "./test-dom";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { act, useState } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";
import { Button } from "./components/ds/Button";
import { SegmentedControl } from "./components/ds/SegmentedControl";
import { Form, FormField, TextField } from "./components/ds/TextField";
import { RecordsTable } from "./components/ds/RecordsTable";

test("actions do not submit a form unless explicitly marked submit", async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Element: dom.window.Element, Node: dom.window.Node, IS_REACT_ACT_ENVIRONMENT: true });
  const host = dom.window.document.getElementById("root")!, root = createRoot(host);
  let submissions = 0, actions = 0;
  try {
    await act(async () => root.render(<form onSubmit={event => { event.preventDefault(); submissions++; }}><Button onClick={() => actions++}>Preview</Button><Button type="submit">Save</Button><Button type="submit" loading onClick={() => actions++}>Pending</Button><Button disabled onClick={() => actions++}>Unavailable</Button></form>));
    const [preview, save, pending, disabled] = host.querySelectorAll("button");
    await act(async () => { preview.click(); pending.click(); disabled.click(); });
    assert.equal(actions, 1);
    assert.equal(submissions, 0);
    assert.equal(pending.getAttribute("aria-busy"), "true");
    assert.equal(pending.getAttribute("aria-disabled"), "true");
    assert.equal(pending.textContent, "Pending");
    pending.focus();
    assert.equal(dom.window.document.activeElement, pending);
    assert.equal(disabled.disabled, true);
    await act(async () => save.click());
    assert.equal(submissions, 1);
  } finally { await act(async () => root.unmount()); dom.window.close(); }
});

test("pending asChild actions block the child's own handler", async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Element: dom.window.Element, Node: dom.window.Node, IS_REACT_ACT_ENVIRONMENT: true });
  const host = dom.window.document.getElementById("root")!, root = createRoot(host);
  let actions = 0;
  try {
    await act(async () => root.render(<Button asChild loading><a href="#saved" onClick={() => actions++}>Save</a></Button>));
    await act(async () => host.querySelector("a")!.click());
    assert.equal(actions, 0);
    assert.equal(dom.window.location.hash, "");
  } finally { await act(async () => root.unmount()); dom.window.close(); }
});

test("dialogs keep their bounded scroll area inside the Radix scroll-lock shard", () => {
  const system = readFileSync(new URL("./app/system.css", import.meta.url), "utf8");
  const content = system.match(/\.ds-dialog\s*\{([^}]+)\}/)![1];
  assert.match(content, /max-height:\s*100%/);
  assert.match(content, /overflow-y:\s*auto/);
  assert.match(content, /overscroll-behavior:\s*contain/);
  const palette = readFileSync(new URL("./components/site/DimeCommandPalette.tsx", import.meta.url), "utf8");
  assert.match(palette, /className="overflow-x-hidden"/);
  assert.doesNotMatch(palette, /className="overflow-hidden"/);
});

test("non-modal dialogs render independently of the optional overlay and close", async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost", pretendToBeVisual: true });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, HTMLInputElement: dom.window.HTMLInputElement, Element: dom.window.Element, Node: dom.window.Node, NodeFilter: dom.window.NodeFilter, MutationObserver: dom.window.MutationObserver, CustomEvent: dom.window.CustomEvent, Event: dom.window.Event, getComputedStyle: dom.window.getComputedStyle.bind(dom.window), IS_REACT_ACT_ENVIRONMENT: true });
  const { Dialog, DialogTrigger, DialogContent, DialogTitle, DialogDescription, DialogClose } = await import("./components/ui/dialog");
  const host = dom.window.document.getElementById("root")!, root = createRoot(host);
  try {
    await act(async () => root.render(<Dialog modal={false}><DialogTrigger>Inspect</DialogTrigger><DialogContent><DialogTitle>Source</DialogTitle><DialogDescription>Evidence details</DialogDescription><DialogClose>Close</DialogClose></DialogContent></Dialog>));
    await act(async () => host.querySelector("button")!.click());
    const dialog = dom.window.document.querySelector('[role="dialog"]')!;
    assert.ok(dialog);
    assert.match(dialog.textContent!, /Evidence details/);
    assert.equal(dom.window.document.querySelector(".ds-dialog-backdrop"), null);
    await act(async () => dialog.querySelector<HTMLButtonElement>("button")!.click());
    assert.equal(dom.window.document.querySelector('[role="dialog"]'), null);
  } finally { await act(async () => root.unmount()); dom.window.close(); }
});

test("complete fields associate explicit IDs, help and errors and retain disabled input semantics", async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost" });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, HTMLInputElement: dom.window.HTMLInputElement, Element: dom.window.Element, Node: dom.window.Node, IS_REACT_ACT_ENVIRONMENT: true });
  const host = dom.window.document.getElementById("root")!, root = createRoot(host);
  try {
    await act(async () => root.render(<Form><FormField name="research" label="Research name" description="Keep the draft" error="Use at least 3 characters"><TextField id="explicit-research" required disabled defaultValue="Draft" /></FormField></Form>));
    const input = host.querySelector("input")!;
    assert.equal(host.querySelector("label")!.htmlFor, input.id);
    assert.equal(input.name, "research");
    assert.equal(input.disabled, true);
    assert.equal(input.required, true);
    assert.equal(input.value, "Draft");
    assert.equal(input.getAttribute("aria-invalid"), "true");
    const descriptions = input.getAttribute("aria-describedby")!.split(" ").map(id => dom.window.document.getElementById(id)!.textContent);
    assert.ok(descriptions.includes("Keep the draft"));
    assert.ok(descriptions.includes("Use at least 3 characters"));
    assert.equal(host.querySelector('[role="alert"]')!.textContent, "Use at least 3 characters");
  } finally { await act(async () => root.unmount()); dom.window.close(); }
});

test("evidence tables distinguish zero from missing values and keep numeric alignment, source and empty recovery", () => {
  const dom = new JSDOM(renderToStaticMarkup(<RecordsTable title="Player evidence" source="warehouse · minutes" rows={[{ player: "Wing A", minutes: 0 }, { player: "Wing B", minutes: null }]} />));
  const region = dom.window.document.querySelector('[role="region"]')!;
  assert.equal(region.getAttribute("aria-label"), "Player evidence records");
  assert.equal(region.getAttribute("tabindex"), "0");
  assert.equal(region.querySelector("caption")!.textContent, "Player evidence");
  assert.equal(region.querySelectorAll('th[scope="col"]').length, 2);
  assert.equal(region.querySelector("td.is-numeric")!.textContent, "0");
  assert.equal(region.querySelector('[aria-label="Not available"]')!.textContent, "—");
  assert.match(dom.window.document.body.textContent!, /2 records/);
  assert.match(dom.window.document.body.textContent!, /warehouse · minutes/);
  dom.window.close();
  const empty = renderToStaticMarkup(<RecordsTable title="Player evidence" rows={[]} source="warehouse · minutes" />);
  assert.match(empty, /0 records/);
  assert.match(empty, /No records available/);
  assert.match(empty, /Adjust the query/);
  assert.match(empty, /warehouse · minutes/);
  assert.doesNotMatch(empty, /<table/);
});

test("evidence tables render long floats at four significant digits without touching integers", () => {
  const dom = new JSDOM(renderToStaticMarkup(<RecordsTable title="Float evidence" rows={[{ player: "Guard A", pts: 32.68421052631579, rate: 0.0045671, games: 82 }]} />));
  const text = dom.window.document.body.textContent!;
  assert.match(text, /32\.68/);
  assert.doesNotMatch(text, /32\.684210526/);
  assert.match(text, /0\.004567/);
  assert.match(text, /82/);
  dom.window.close();
});

test("native field validation supplies associated feedback without an explicit error", async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost", pretendToBeVisual: true });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, HTMLInputElement: dom.window.HTMLInputElement, Element: dom.window.Element, Node: dom.window.Node, Event: dom.window.Event, FormData: dom.window.FormData, IS_REACT_ACT_ENVIRONMENT: true });
  const host = dom.window.document.getElementById("root")!, root = createRoot(host);
  const cases = [
    { props: { required: true }, feedback: /missing/, valid: "Scouting report" },
    { props: { type: "email", defaultValue: "not-email" }, feedback: /required type/, valid: "analyst@example.com" },
    { props: { type: "number", min: 3, defaultValue: "1" }, feedback: /too small/, valid: "3" },
  ];
  try {
    for (const [index, entry] of cases.entries()) {
      let submissions = 0;
      await act(async () => root.render(<Form key={index} onSubmit={event => { event.preventDefault(); submissions++; }}><FormField name="research" label="Research field" description="Keep the draft"><TextField {...entry.props} /></FormField><Button type="submit">Save</Button></Form>));
      const input = host.querySelector("input")!;
      await act(async () => host.querySelector("button")!.click());
      const message = host.querySelector('[role="alert"]')!;
      assert.equal(submissions, 0);
      assert.ok(message);
      assert.match(message.textContent!, entry.feedback);
      assert.ok(input.getAttribute("aria-describedby")!.split(" ").includes(message.id));
      assert.match(host.textContent!, /Keep the draft/);
      await act(async () => { input.value = entry.valid; input.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
      assert.equal(host.querySelector('[role="alert"]'), null);
      await act(async () => host.querySelector("button")!.click());
      assert.equal(submissions, 1);
    }
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

test("filter selection follows library-managed arrow focus even on rapid key presses", async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost", pretendToBeVisual: true });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Element: dom.window.Element, Node: dom.window.Node, Event: dom.window.Event, CustomEvent: dom.window.CustomEvent, IS_REACT_ACT_ENVIRONMENT: true });
  const host = dom.window.document.getElementById("root")!, root = createRoot(host);
  function Filters({ disabled = false }: { disabled?: boolean }) {
    const [value, setValue] = useState("With records");
    return <SegmentedControl options={["With records", "No matches"]} value={value} onChange={setValue} disabled={disabled} label="Evidence state" />;
  }
  try {
    await act(async () => root.render(<Filters />));
    const [withRecords, noMatches] = host.querySelectorAll<HTMLButtonElement>('[role="radio"]');
    await act(async () => withRecords.focus());
    await act(async () => {
      withRecords.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
      withRecords.dispatchEvent(new dom.window.KeyboardEvent("keyup", { key: "ArrowRight", bubbles: true }));
      await new Promise(resolve => setTimeout(resolve, 20));
    });
    assert.equal(dom.window.document.activeElement, noMatches);
    assert.equal(noMatches.getAttribute("aria-checked"), "true");
    assert.equal(noMatches.getAttribute("data-state"), "checked");
    await act(async () => {
      noMatches.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
      noMatches.dispatchEvent(new dom.window.KeyboardEvent("keyup", { key: "ArrowLeft", bubbles: true }));
      await new Promise(resolve => setTimeout(resolve, 20));
    });
    assert.equal(withRecords.getAttribute("aria-checked"), "true");
    await act(async () => root.render(<Filters disabled />));
    await act(async () => noMatches.click());
    assert.equal(withRecords.getAttribute("aria-checked"), "true");
    assert.equal(noMatches.disabled, true);
  } finally { await act(async () => root.unmount()); dom.window.close(); }
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
  for (const foreground of ["control-edge", "accent-ink"]) {
    test(`${theme} ${foreground} on surface meets control/focus contrast`, () => {
      const l1 = luminance(color(palette[foreground]).rgb), l2 = luminance(color(palette.surface).rgb);
      const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
      assert.ok(ratio >= 3, `${ratio.toFixed(2)}:1 is below 3:1`);
    });
  }
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

test("entrances keep opacity fades under reduced motion and layer movement behind no-preference", () => {
  const globals = readFileSync(new URL("./app/globals.css", import.meta.url), "utf8");
  assert.ok(globals.includes("@keyframes artifact-fade"), "opacity-only artifact fade keyframes exist");
  assert.ok(globals.includes("@keyframes artifact-enter"), "movement-bearing artifact entrance keyframes exist");
  const noPreference = [...globals.matchAll(/@media \(prefers-reduced-motion: no-preference\) \{([\s\S]*?)\n\}/g)].map(m => m[1]).join("\n");
  assert.ok(noPreference.includes(".artifact-enter"), "the translate-bearing entrance applies only when motion is allowed");
  const reduceBlocks = [...globals.matchAll(/@media \(prefers-reduced-motion: reduce\) \{([\s\S]*?)\n\}/g)].map(m => m[1]).join("\n");
  assert.ok(reduceBlocks.includes(".artifact-enter"), "reduced motion re-enables the opacity fade duration for entrances");
  const base = globals.match(/\.artifact-enter \{\r?\n\s+animation: artifact-fade/);
  assert.ok(base, "the base artifact entrance is the opacity-only fade");
});

test("reduced motion keeps opacity fades while movement transitions are opt-in gated", () => {
  const globals = readFileSync(new URL("./app/globals.css", import.meta.url), "utf8");
  const reduceBlocks = [...globals.matchAll(/@media \(prefers-reduced-motion: reduce\) \{([\s\S]*?)\n\}/g)].map(m => m[1]);
  const blanket = reduceBlocks.find(b => b.includes("animation-duration"));
  assert.ok(blanket, "a reduced-motion animation override exists");
  assert.ok(!blanket!.includes("transition-duration"), "the blanket override must not kill opacity/color transitions");
  const noPreference = [...globals.matchAll(/@media \(prefers-reduced-motion: no-preference\) \{([\s\S]*?)\n\}/g)].map(m => m[1]).join("\n");
  for (const sel of [".records-resize-handle::after", ".records-sort", ".records-primary-button", ".records-checkbox-box", ".records-add-calculation", ".animated-underline::after"]) {
    assert.ok(noPreference.includes(sel), `${sel} transform transition is gated behind no-preference`);
  }
  const sortBase = globals.match(/\.records-sort \{(?!.*transform)[\s\S]*?transition: opacity 120ms ease-out;/);
  assert.ok(sortBase, "the base rule keeps the opacity fade without the transform");
});


test("chart threshold marks label in the legend strip, never inside the plot where bars collide", () => {
  const source = readFileSync(new URL("./components/dime/ArtifactChart.tsx", import.meta.url), "utf8");
  assert.ok(!source.includes("position: \"insideTopLeft\"") && !source.includes("position: \"insideTopRight\""), "reference-line labels must not render inside the plot area");
  assert.ok(source.includes("mark-legend"), "mark labels ride in the legend strip");
});

test("shot chart court strokes use a legible mid-tone, not a hairline token", () => {
  const source = readFileSync(new URL("./components/dime/ArtifactShotChart.tsx", import.meta.url), "utf8");
  assert.ok(!source.includes('const LINE = "var(--line-strong)"'), "court geometry must not render in the hairline token — illegible in light mode");
  assert.ok(source.includes("var(--ink-3)"), "court strokes use the mid-tone ink token");
});

test("card bodies do not repeat the kind label the shell already carries", () => {
  for (const file of ["./components/dime/ArtifactPlayerCard.tsx", "./components/dime/ArtifactTeamCard.tsx"]) {
    const source = readFileSync(new URL(file, import.meta.url), "utf8");
    assert.ok(!source.includes("Player snapshot</p>") && !source.includes("Team snapshot</p>"), `${file} re-labels the kind inside the body — redundant with the shell header`);
  }
});

test("card sections dedupe a citation shared by every section to one line", () => {
  const source = readFileSync(new URL("./components/dime/ArtifactCardSections.tsx", import.meta.url), "utf8");
  assert.ok(source.includes("sharedCitation"), "sections accept the card-level shared citation");
  assert.ok(source.includes("citation !== sharedCitation"), "a section repeats its citation only when it differs from the shared one");
  for (const file of ["./components/dime/ArtifactPlayerCard.tsx", "./components/dime/ArtifactTeamCard.tsx"]) {
    const card = readFileSync(new URL(file, import.meta.url), "utf8");
    assert.ok(!card.includes("Scope not declared"), `${file} must not headline missing scope in the subtitle — the quiet provenance row carries it`);
  }
});

test("the shell never renders undeclared provenance as a headline subtitle", () => {
  const source = readFileSync(new URL("./components/dime/ArtifactShell.tsx", import.meta.url), "utf8");
  assert.ok(source.includes('source === "source not declared"'), "the shell drops the undeclared-provenance string from the subtitle slot");
});

test("scatter labels every point at low density and stays hover-only beyond it", () => {
  const source = readFileSync(new URL("./components/dime/ArtifactScatter.tsx", import.meta.url), "utf8");
  assert.ok(source.includes("points.length <= 8"), "static labels for all points when density is 8 or fewer");
  assert.ok(source.includes("<title>"), "hover titles carry identity beyond that density");
});

test("currency-shorthand units compose inline with the number, not as a detached caption", () => {
  const format = readFileSync(new URL("./lib/metric-format.ts", import.meta.url), "utf8");
  assert.ok(format.includes('unit.startsWith("$")'), "shorthand currency units compose inline ($172M not 172 + $M beneath)");
  const card = readFileSync(new URL("./components/dime/ArtifactTeamCard.tsx", import.meta.url), "utf8");
  assert.ok(card.includes("unitEmbeddedInline(metric.unit)"), "the detached caption drops when the unit already rides inline");
});

test("an empty verification verdict compresses to one quiet line", () => {
  const source = readFileSync(new URL("./components/site/harness/AnswerView.tsx", import.meta.url), "utf8");
  assert.ok(source.includes("emptyCase"), "no-verified-claims renders as one quiet line, not a heavy card");
});

test("section metrics use the headline formatter and inline units never double as captions", () => {
  const sections = readFileSync(new URL("./components/dime/ArtifactCardSections.tsx", import.meta.url), "utf8");
  assert.ok(sections.includes("formatHeadlineMetric(metric.value, metric.unit)") || sections.includes("formatHeadlineMetric(metric.value,"), "section metrics compose through the shared formatter — no String(value) bypass");
  const format = readFileSync(new URL("./lib/metric-format.ts", import.meta.url), "utf8");
  assert.ok(format.includes('unit === "usd_dollars"'), "the canonical currency token counts as inline-embedded — no machine-token caption");
});

test("compressed empty verdict does not duplicate the zero-claims fact", () => {
  const source = readFileSync(new URL("./components/site/harness/AnswerView.tsx", import.meta.url), "utf8");
  assert.ok(source.includes("replace(/^0 verified claims?"), "the detail's duplicate claim-count prefix strips in the compressed line");
});

test("table artifact rows type admits null, matching the renderer and real data", () => {
  const source = readFileSync(new URL("./lib/stream/types.ts", import.meta.url), "utf8");
  assert.ok(source.includes("rows: (string | number | null)[][]"), "the row type widened to reality");
});

test("the shell exposes a skip-to-content link as the first focusable stop", () => {
  const shell = readFileSync(new URL("./components/shell/DimeShell.tsx", import.meta.url), "utf8");
  const anchor = shell.indexOf('href="#dime-main-content"');
  const sidebar = shell.indexOf("<SidebarNav");
  assert.ok(anchor > -1, "skip link present");
  assert.ok(anchor < sidebar, "skip link precedes the sidebar in tab order");
  assert.match(shell, /id="dime-main-content"[^>]*tabIndex=\{-1\}/);
  const css = readFileSync(new URL("./app/dime.css", import.meta.url), "utf8");
  const hidden = css.match(/\.skip-to-content\s*\{([^}]+)\}/)![1];
  assert.match(hidden, /left:\s*-9999px/);
  assert.match(css, /\.skip-to-content:focus-visible\s*\{[^}]*left:\s*\d/);
});
