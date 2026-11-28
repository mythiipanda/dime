import assert from "node:assert/strict";
import test from "node:test";
import { formatHeadlineMetric } from "./metric-format";

test("usd_dollars headline metrics render as money", () => {
  assert.equal(formatHeadlineMetric(201332759, "usd_dollars"), "$201.3M");
});

test("undeclared numeric headline metrics do not acquire a dollar sign", () => {
  const rendered = formatHeadlineMetric(201332759, undefined);
  assert.equal(rendered, "201.3M");
  assert.equal(rendered.includes("$"), false);
});

test("usd_millions headline metrics render as money at the millions scale without re-scaling", () => {
  assert.equal(formatHeadlineMetric(45.3, "usd_millions"), "$45.3M");
  assert.equal(formatHeadlineMetric(0.5, "usd_millions"), "$500K");
  assert.equal(formatHeadlineMetric(-12.1, "usd_millions"), "-$12.1M");
});

test("usd_millions counts as an inline-embedded unit", async () => {
  const { unitEmbeddedInline } = await import("./metric-format");
  assert.equal(unitEmbeddedInline("usd_millions"), true);
});
