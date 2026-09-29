
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  EXPANDABLE_PANELS,
  markMounted,
  toggleExpanded,
} from "./explorePanels";

test("all six sections are expandable panels", () => {
  assert.deepEqual([...EXPANDABLE_PANELS].sort(), [
    "draft",
    "leaders",
    "lineups",
    "playoffs",
    "shots",
    "trade",
  ]);
});

test("markMounted adds a panel once and never removes", () => {
  assert.deepEqual(markMounted([], "shots"), ["shots"]);
  assert.deepEqual(markMounted(["shots"], "shots"), ["shots"]);
  assert.deepEqual(markMounted(["shots"], "trade"), ["shots", "trade"]);
});

test("toggleExpanded opens, switches, and closes on repeat click", () => {
  assert.equal(toggleExpanded(null, "shots"), "shots");
  assert.equal(toggleExpanded("shots", "shots"), null);
  assert.equal(toggleExpanded("shots", "trade"), "trade");
});
