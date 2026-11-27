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
