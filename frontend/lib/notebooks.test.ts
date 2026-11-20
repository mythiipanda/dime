import test from "node:test";
import assert from "node:assert/strict";
import { addCell, askCellPrompt, cellArtifact, duplicateNotebook, moveCell, newNotebook, notebookArtifact, notebookContext, notebookMarkdown, removeCell, saveNotebook, sqlCellChart, updateCell, validNotebook, listNotebooks, getNotebook, deleteNotebook, type Notebook, type NotebookCell } from "./notebooks";
import type { TableArtifactPayload, MemoArtifactPayload } from "./stream/types";

const sqlCell: NotebookCell = { id: "cell-1", kind: "sql", source: "SELECT PLAYER, PTS FROM t", result: { columns: ["PLAYER", "PTS"], rows: [["Shai", 31.4], ["Jokic", 29.0]], ms: 42, capped: false }, ran_at: "2026-11-19T01:00:00Z" };
const askCell: NotebookCell = { id: "cell-2", kind: "ask", source: "Who leads?", result: { answer: "Shai leads on 31.4." }, ran_at: "2026-11-19T01:05:00Z" };

function nb(): Notebook {
  return { ...newNotebook("FA study"), cells: [sqlCell, askCell, { id: "cell-3", kind: "sql", source: "SELECT 1" }] };
}

test("validNotebook accepts real notebooks and rejects malformed cells", () => {
  assert.equal(validNotebook(nb()), true);
  assert.equal(validNotebook({ ...nb(), cells: [{ id: "x", kind: "python", source: "" }] }), false);
  assert.equal(validNotebook({ ...nb(), cells: [{ id: "x", kind: "sql", source: "s", result: { answer: "wrong kind" } }] }), false);
  assert.equal(validNotebook({ ...nb(), cells: [{ id: "x", kind: "ask", source: "s", result: { columns: ["A"] } }] }), false);
  assert.equal(validNotebook({ ...nb(), title: "x".repeat(161) }), false);
});

test("cell helpers add, patch, remove and reorder immutably", () => {
  const base = newNotebook();
  const { notebook: withCell, cell } = addCell(base, "sql");
  assert.equal(withCell.cells.length, 1);
  assert.equal(base.cells.length, 0);
  const patched = updateCell(withCell, cell.id, { source: "SELECT 1", ran_at: "2026-11-19T00:00:00Z" });
  assert.equal(patched.cells[0].source, "SELECT 1");
  assert.equal(withCell.cells[0].source, "");
  const { notebook: second } = addCell(patched, "ask");
  const moved = moveCell(second, 1, 0);
  assert.equal(moved.cells[0].kind, "ask");
  assert.equal(removeCell(moved, cell.id).cells.length, 1);
});

test("saveNotebook persists, dedupes and rejects invalid docs", () => {
  const saved = saveNotebook(nb());
  assert.equal(getNotebook(saved.id)?.cells.length, 3);
  assert.ok(listNotebooks().some(item => item.id === saved.id));
  deleteNotebook(saved.id);
  assert.equal(getNotebook(saved.id), null);
});

test("context serializes prior cells only, ask prompt embeds it", () => {
  const context = notebookContext(nb(), "cell-3");
  assert.match(context, /SELECT PLAYER, PTS FROM t/);
  assert.match(context, /Shai \| 31\.4/);
  assert.match(context, /Question: Who leads\?/);
  assert.match(context, /Shai leads on 31\.4/);
  assert.doesNotMatch(context, /SELECT 1/);
  const prompt = askCellPrompt(nb(), { ...askCell, id: "cell-3", source: "why?" });
  assert.match(prompt, /SELECT PLAYER, PTS FROM t/);
  assert.match(prompt, /Question: why\?/);
});

test("sqlCellChart picks numeric columns with a label column", () => {
  const chart = sqlCellChart(sqlCell.result!);
  assert.equal(chart!.series.length, 1);
  assert.equal(chart!.series[0].name, "PTS");
  assert.deepEqual(chart!.xLabels, ["Shai", "Jokic"]);
  assert.equal(sqlCellChart({ columns: ["A"], rows: [["x"]] }), null);
});

test("cellArtifact maps cells to pinnable artifacts with provenance", () => {
  const notebook = nb();
  const table = cellArtifact(notebook, sqlCell, 0) as TableArtifactPayload;
  assert.equal(table.kind, "table");
  assert.equal(table.title, "FA study · Cell 1 · SQL");
  assert.equal(table.provenance?.sql, sqlCell.source);
  assert.equal(table.provenance?.as_of, sqlCell.ran_at);
  const memo = cellArtifact(notebook, askCell, 1) as MemoArtifactPayload;
  assert.equal(memo.kind, "memo");
  assert.match(memo.text, /Q: Who leads\?/);
  assert.equal(cellArtifact(notebook, notebook.cells[2], 2), null);
  assert.equal(notebookArtifact(notebook).kind, "memo");
});

test("markdown export carries sources, results and provenance per cell", () => {
  const md = notebookMarkdown(nb());
  assert.match(md, /# FA study/);
  assert.match(md, /```sql\nSELECT PLAYER, PTS FROM t\n```/);
  assert.match(md, /\| Shai \| 31\.4 \|/);
  assert.match(md, /Source: sql_rerun · ran/);
  assert.match(md, /\*\*Question:\*\* Who leads\?/);
  assert.match(md, /Source: Dime answer · ran/);
  assert.match(md, /Not run/);
});

test("duplicateNotebook re-ids notebook and cells", () => {
  const copy = duplicateNotebook(nb());
  assert.notEqual(copy.id, nb().id);
  assert.ok(copy.cells.every((cell, i) => cell.id !== nb().cells[i].id));
});
