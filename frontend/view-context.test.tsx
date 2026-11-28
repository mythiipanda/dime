import test from "node:test";
import assert from "node:assert/strict";
import { serializeViewContext, splitViewContext, type ViewContext } from "./lib/view-context";

const matchup: ViewContext = {
  kind: "matchup",
  summary: "BOS @ NYK, 2025-26 season matchup",
  entities: { teams: ["BOS", "NYK"], season: "2025-26", date: "2026-11-27" },
};

test("serializeViewContext emits a machine-readable delimited block ahead of the question", () => {
  const wire = serializeViewContext(matchup, "Who has the edge tonight?");
  assert.ok(wire.startsWith("<dime-context"));
  assert.ok(wire.includes("</dime-context>"));
  assert.ok(wire.indexOf("</dime-context>") < wire.indexOf("Who has the edge tonight?"));
  assert.ok(wire.includes('"teams":["BOS","NYK"]'));
});

test("splitViewContext round-trips the envelope and clean user text", () => {
  const wire = serializeViewContext(matchup, "Who has the edge tonight?");
  const split = splitViewContext(wire);
  assert.deepEqual(split.context, matchup);
  assert.equal(split.text, "Who has the edge tonight?");
});

test("splitViewContext passes plain user text through untouched", () => {
  const split = splitViewContext("just a normal question");
  assert.equal(split.context, null);
  assert.equal(split.text, "just a normal question");
});

test("splitViewContext does not treat context-shaped prose mid-message as machine context", () => {
  const wire = "what does this mean: <dime-context kind=\"matchup\">\n{}</dime-context>";
  const split = splitViewContext(wire);
  assert.equal(split.context, null);
  assert.equal(split.text, wire);
});

test("refs ride as optional non-load-bearing metadata", () => {
  const withRef: ViewContext = { ...matchup, refs: { object_id: "obj_123" } };
  const split = splitViewContext(serializeViewContext(withRef, "q"));
  assert.equal(split.context?.refs?.object_id, "obj_123");
});
