import test from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ArtifactBody } from "./components/site/DimeHarness";
import type { DimeArtifact } from "./lib/dime-stream";

function render(artifact: DimeArtifact): string {
  return renderToStaticMarkup(<ArtifactBody artifact={artifact} />);
}

test("streamed chart artifacts render a chart", () => {
  const html = render({
    kind: "chart",
    title: "Scoring trend",
    series: [
      { name: "Gilgeous-Alexander", values: [24, 31, 28] },
      { name: "Doncic", values: [27, 25, 30] },
    ],
    footnote: "points per game",
  });
  assert.ok(html.includes("<svg"), html.slice(0, 120));
  assert.ok(html.includes("Gilgeous-Alexander"), html);
});

test("streamed shot chart artifacts render a court", () => {
  const html = render({
    kind: "shot_chart",
    title: "Shot chart",
    zones: [
      { x: 50, y: 12, att: 142, pct: 71 },
      { x: 32, y: 22, att: 88, pct: 52 },
    ],
  });
  assert.ok(html.includes("<svg"), html.slice(0, 120));
});

test("chart and shot artifacts with no data render nothing", () => {
  assert.equal(
    render({ kind: "chart", title: "empty", series: [] }),
    "",
  );
  assert.equal(
    render({ kind: "shot_chart", title: "empty", zones: [] }),
    "",
  );
});

test("table and compare artifacts still render their rows", () => {
  const table = render({
    kind: "table",
    title: "Verified numbers",
    columns: [{ key: "metric", label: "Metric" }],
    rows: [["Wins", "OKC"]],
  });
  assert.ok(table.includes("Wins"), table);

  const compare = render({
    kind: "compare",
    title: "Head-to-head",
    aName: "SGA",
    bName: "Luka",
    rows: [{ label: "PPG", a: 31.2, b: 28.4 }],
  });
  assert.ok(compare.includes("SGA"), compare);
  assert.ok(compare.includes("Luka"), compare);
});
