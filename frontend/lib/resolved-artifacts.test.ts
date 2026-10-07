import assert from "node:assert/strict";
import test from "node:test";
import { deriveArtifacts, reduceBackendEvent } from "./dime-stream";

test("a chart the backend resolved renders as a chart", () => {
  const chunks = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [
      {
        kind: "chart",
        title: "Scoring trend",
        series: [
          { name: "Gilgeous-Alexander", values: [30, 22, 41] },
          { name: "Doncic", values: [27, 25, 30] },
        ],
        footnote: "points per game",
      },
    ],
  });

  assert.equal(chunks.length, 1);
  const only = chunks[0];
  assert.equal(only.type, "artifact");
  if (only.type !== "artifact") return;
  assert.equal(only.artifact.kind, "chart");
  if (only.artifact.kind !== "chart") return;
  assert.equal(only.artifact.title, "Scoring trend");
  assert.deepEqual(only.artifact.series[0].values, [30, 22, 41]);
  assert.equal(only.artifact.footnote, "points per game");
});

test("a resolved chart and a derived table both reach the stream", () => {
  const chunks = reduceBackendEvent("custom_data", {
    tables: [
      {
        output_id: "PTS",
        display_name: "Points",
        subject_display_name: "Gilgeous-Alexander",
        value: "30",
        unit: "points per game",
      },
    ],
    artifacts: [
      {
        kind: "chart",
        title: "Trend",
        series: [{ name: "Gilgeous-Alexander", values: [30, 22] }],
      },
    ],
  });

  assert.deepEqual(
    chunks.map((chunk) =>
      chunk.type === "artifact" ? chunk.artifact.kind : chunk.type),
    ["table", "chart"],
  );
});

test("a malformed resolved artifact is dropped instead of rendered blank", () => {
  const chunks = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [{ kind: "chart", title: "no series" }],
  });

  assert.deepEqual(chunks, []);
});

test("an artifact kind the UI cannot draw is dropped", () => {
  const chunks = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [{ kind: "pie", title: "x", series: [{ name: "a", values: [1] }] }],
  });

  assert.deepEqual(chunks, []);
});

test("a chart series with no numbers is dropped", () => {
  const chunks = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [
      { kind: "chart", title: "empty", series: [{ name: "a", values: [] }] },
    ],
  });

  assert.deepEqual(chunks, []);
});

test("deriveArtifacts still derives the table and compare from evidence rows", () => {
  const derived = deriveArtifacts([
    {
      output_id: "PTS",
      display_name: "Points",
      subject_display_name: "Gilgeous-Alexander",
      value: "30",
      unit: "points per game",
    },
  ]);

  assert.equal(derived.length, 1);
  assert.equal(derived[0].kind, "table");
});