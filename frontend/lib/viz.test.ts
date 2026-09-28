import assert from "node:assert/strict";
import test from "node:test";
import {
  clamp,
  formatPct,
  histogramBins,
  ordinal,
  percentileRank,
} from "./viz";

test("ordinal handles 1st/2nd/3rd and the teens", () => {
  assert.equal(ordinal(1), "1st");
  assert.equal(ordinal(2), "2nd");
  assert.equal(ordinal(3), "3rd");
  assert.equal(ordinal(4), "4th");
  assert.equal(ordinal(11), "11th");
  assert.equal(ordinal(12), "12th");
  assert.equal(ordinal(13), "13th");
  assert.equal(ordinal(21), "21st");
  assert.equal(ordinal(92), "92nd");
  assert.equal(ordinal(103), "103rd");
});

test("formatPct formats a rate", () => {
  assert.equal(formatPct(0.618), "61.8%");
  assert.equal(formatPct(0.5, 0), "50%");
});

test("clamp bounds the value", () => {
  assert.equal(clamp(150, 0, 100), 100);
  assert.equal(clamp(-5, 0, 100), 0);
  assert.equal(clamp(42, 0, 100), 42);
});

test("percentileRank counts values at or below v", () => {
  const sorted = [1, 2, 3, 4, 5];
  assert.equal(percentileRank(sorted, 3), 0.6);
  assert.equal(percentileRank(sorted, 5), 1);
  assert.equal(percentileRank(sorted, 0), 0);
  assert.equal(percentileRank([], 3), 0);
});

test("histogramBins covers every value exactly once", () => {
  const values = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
  const bins = histogramBins(values, 5);
  assert.equal(bins.length, 5);
  assert.equal(
    bins.reduce((a, b) => a + b.count, 0),
    values.length,
  );
  // Max value lands in the last bin (closed on the right).
  assert.equal(bins[4].count >= 1, true);
});

test("histogramBins handles a flat input", () => {
  const bins = histogramBins([3, 3, 3], 4);
  assert.equal(bins.length, 4);
  assert.equal(
    bins.reduce((a, b) => a + b.count, 0),
    3,
  );
});
