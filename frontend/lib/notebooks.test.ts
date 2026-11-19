import test from "node:test";
import assert from "node:assert/strict";
import { addCell, chartable, moveCell, newCell, notebookDraft, notebookStarters, removeCell, saveStateLabel, updateCell } from "./notebooks";

test("cell helpers are immutable, bounded and safe on empty or missing cells", () => {
  const first = newCell("sql", "SELECT 1"), second = newCell("python", "print(2)");
  assert.match(first.id, /^[a-f0-9]{32}$/);
  const original = [first, second];
  const added = addCell(original, first.id, "markdown");
  assert.equal(added.length, 3); assert.equal(added[1].kind, "markdown"); assert.equal(original.length, 2);
  assert.deepEqual(moveCell(original, first.id, 1), [second, first]);
  assert.equal(moveCell(original, first.id, -1), original); assert.equal(moveCell(original, "missing", 1), original);
  assert.equal(moveCell([], "missing", 1).length, 0);
  assert.deepEqual(removeCell(original, first.id), [second]); assert.deepEqual(removeCell([], first.id), []);
  assert.equal(addCell([], null)[0].kind, "sql"); assert.equal(addCell(Array(100).fill(first), null).length, 100);
});

test("editing source or kind invalidates old results while an output update preserves source", () => {
  const cell = { ...newCell("sql", "SELECT 1"), outputs: { old: true }, executed_at: "2026-01-01" };
  const changed = updateCell([cell], cell.id, { source: "SELECT 2" })[0];
  assert.equal(changed.outputs, undefined); assert.equal(changed.executed_at, null); assert.equal(cell.source, "SELECT 1");
  assert.equal(updateCell([cell], cell.id, { kind: "python" })[0].outputs, undefined);
  assert.deepEqual(updateCell([cell], cell.id, { outputs: { fresh: true } })[0].outputs, { fresh: true });
  assert.deepEqual(updateCell([], "missing", { source: "x" }), []);
});

test("starter registry generates independent cell ids and only known chart shapes qualify", () => {
  for (const starter of notebookStarters) {
    const first = notebookDraft(starter.id), second = notebookDraft(starter.id);
    assert.equal(first.title, starter.title); assert.equal(first.cells.length, starter.cells.length);
    assert.notEqual(first.cells[0].id, second.cells[0].id);
  }
  assert.equal(notebookDraft().cells.length, 1); assert.equal(notebookDraft("unknown").title, "Untitled notebook");
  assert.equal(chartable([]), false); assert.equal(chartable([{ value: 1 }]), false);
  assert.equal(chartable([{ PLAYER: "Curry", PTS: 30 }]), true);
  assert.equal(chartable([{ zone: "Paint", FG_PCT: 65 }]), true);
});

test("save state labels distinguish pending, saving, saved, failed and conflicted writes", () => {
  assert.equal(saveStateLabel("saved"), "Saved"); assert.equal(saveStateLabel("dirty"), "Unsaved changes");
  assert.equal(saveStateLabel("saving"), "Saving…"); assert.equal(saveStateLabel("conflict"), "Conflict, reload");
  assert.equal(saveStateLabel("error"), "Not saved · retry");
});
