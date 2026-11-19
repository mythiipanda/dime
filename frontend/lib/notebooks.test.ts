import test from "node:test";
import assert from "node:assert/strict";
import { addCell, chartable, moveCell, newCell, notebookDraft, notebookStarters, removeCell, saveStateLabel, updateCell } from "./notebooks";
import { notebookFromAnswer, notebookFromBoard } from "./notebook-seed";
import type { AiMessage } from "./chat";
import type { Board, BoardCitation } from "./boards";
import { scoutingEvents, scoutingQuestion } from "./replay-fixture";
import { applyEvent } from "./stream-event";

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

const recordedAnswer: AiMessage = { text: "Curry leads this shortlist.", done: true, carry: { run_id: "answer-fixture" }, nodes: { analytics: {
  status: "complete", thoughts: [], toolResults: [],
  toolCalls: [{ name: "query_warehouse", sql: "SELECT PLAYER, PPG FROM silver_player_season WHERE _season = $season", args: { params: { season: "2025-26" } } }],
  tables: [{ tool: "query_warehouse", rows: [{ PLAYER: "Stephen Curry", PPG: 28.5 }], meta: { source: "NBA warehouse", season: "2025-26" } }],
} } };

test("answer seeds preserve recorded SQL, named bindings, cached values, source list and origin without mutation", () => {
  const before = JSON.stringify(recordedAnswer), draft = notebookFromAnswer(recordedAnswer, "Who leads?");
  assert.equal(draft.title, "Who leads?"); assert.deepEqual(draft.origin, { kind: "chat", ref: "answer-fixture" });
  assert.match(draft.cells[0].source, /Who leads\?[\s\S]*Curry[\s\S]*NBA warehouse/);
  assert.equal(draft.cells.filter((cell) => cell.kind === "sql").length, 1);
  assert.match(draft.cells[1].source, /_season = '2025-26'/);
  const output = draft.cells[1].outputs as { data: { rows: unknown[]; columns: unknown[] } };
  assert.deepEqual(output.data.rows, [{ PLAYER: "Stephen Curry", PPG: 28.5 }]);
  assert.deepEqual(output.data.columns, [{ name: "PLAYER", type: "VARCHAR" }, { name: "PPG", type: "DOUBLE" }]);
  assert.equal(JSON.stringify(recordedAnswer), before);
  assert.deepEqual(notebookFromAnswer(recordedAnswer, "Who leads?"), draft);
});

test("table provenance SQL is retained on reopened answers, deduplicated, and safely binds positional parameters", () => {
  const query = "SELECT '?' AS label, PLAYER FROM silver_player_season WHERE _season = ? -- ? untouched";
  const table = { tool: "query_warehouse", rows: [{ PLAYER: "Curry" }], provenance: { sql: query, params: ["2025-26' OR TRUE --"] } };
  const ai: AiMessage = { text: "Recorded table", done: true, nodes: { analytics: { status: "complete", thoughts: [], toolCalls: [], toolResults: [], tables: [table, table] } } };
  const draft = notebookFromAnswer(ai, "Question");
  assert.equal(draft.cells.length, 2);
  assert.match(draft.cells[1].source, /SELECT '\?' AS label/);
  assert.match(draft.cells[1].source, /'2025-26'' OR TRUE --' -- \? untouched/);
  assert.ok(draft.cells[1].outputs);
});

test("SQL extraction preserves different parameter sets and refuses missing or unsupported bindings", () => {
  const ai: AiMessage = { text: "Two queries", done: true, nodes: { analytics: { status: "complete", thoughts: [], tables: [], toolResults: [], toolCalls: [
    { name: "query_warehouse", args: { sql: "SELECT $value::INTEGER AS value", params: { value: 1 } } },
    { name: "query_warehouse", sql: "SELECT $value::INTEGER AS value", args: { params: { value: 2 } } },
  ] } } };
  assert.deepEqual(notebookFromAnswer(ai, "Values").cells.slice(1).map((cell) => cell.source), ["SELECT 1::INTEGER AS value", "SELECT 2::INTEGER AS value"]);
  const call = ai.nodes.analytics!.toolCalls[0];
  call.args.params = {};
  assert.throws(() => notebookFromAnswer(ai, "Values"), /missing the parameter/);
  call.args.params = { value: [1, 2] };
  assert.throws(() => notebookFromAnswer(ai, "Values"), /supported scalar/);
});

test("replay and empty answers become honest Markdown snapshots, never fabricated SQL", () => {
  let ai: AiMessage = { text: "", nodes: {}, done: false };
  for (const event of scoutingEvents) ai = applyEvent(ai, event.type, event.data);
  const draft = notebookFromAnswer(ai, scoutingQuestion);
  assert.equal(draft.cells.filter((cell) => cell.kind === "sql").length, 0);
  assert.match(draft.cells[0].source, /synthetic|Synthetic/);
  assert.match(draft.cells[1].source, /Data snapshot[\s\S]*No executable SQL[\s\S]*Oklahoma City/);
  assert.equal(draft.origin?.ref, "dev-replay-scouting");
  assert.match(notebookFromAnswer({ text: "Nothing recorded", nodes: {}, done: true }, "").cells[1].source, /No tables/);
});

test("ambiguous call bindings never attach a cached table to the wrong parameter set", () => {
  const query = "SELECT $value AS value";
  const ai: AiMessage = { text: "Two runs", done: true, nodes: { analytics: { status: "complete", thoughts: [], toolResults: [],
    toolCalls: [1, 2].map((value) => ({ name: "query_warehouse", sql: query, args: { params: { value } } })),
    tables: [{ tool: "query_warehouse", rows: [{ value: 2 }], ...{ sql: query } }],
  } } };
  const sql = notebookFromAnswer(ai, "Which run?").cells.filter((cell) => cell.kind === "sql");
  assert.deepEqual(sql.map((cell) => cell.source), ["SELECT 1 AS value", "SELECT 2 AS value"]);
  assert.ok(sql.every((cell) => !cell.outputs));
});

test("answer caches are bounded and an explicit table binding does not require tool-call params", () => {
  const ai: AiMessage = { text: "Cached result", done: true, nodes: { analytics: { status: "complete", thoughts: [], toolResults: [],
    toolCalls: [{ name: "query_warehouse", sql: "SELECT $1 AS PLAYER", args: {} }],
    tables: [{ tool: "query_warehouse", rows: Array.from({ length: 150 }, () => ({ PLAYER: "A".repeat(1000) })), ...{ sql: "SELECT $1 AS PLAYER", params: ["Curry"] } }],
  } } };
  const draft = notebookFromAnswer(ai, "Cache");
  assert.equal(draft.cells.length, 2);
  assert.equal(draft.cells[1].source, "SELECT 'Curry' AS PLAYER");
  const output = draft.cells[1].outputs as { data: { rows: unknown[]; truncated: boolean } };
  assert.ok(output.data.rows.length < 100); assert.equal(output.data.truncated, true);
  assert.ok(new TextEncoder().encode(JSON.stringify(output)).length < 256 * 1024);
});

const boardCitation = (table: string, column: string): BoardCitation => ({ table, column, season: "2025-26", sql: `SELECT * FROM ${table}`, params: [], source: "NBA warehouse", fetched_at: "2026-01-01", row_key: { PLAYER_ID: 201939 } });
const seedBoard: Board = { id: "board-fixture", title: "Guard shortlist", season: "2025-26", created_at: "2026-01-01", updated_at: "2026-01-01", rows: [{ player_id: 201939, name: "Stephen Curry", team: "GSW" }, { player_id: 203999, name: "Nikola Jokić", team: "DEN" }], columns: [{ metric_id: "ppg" }, { metric_id: "ts_pct" }, { metric_id: "usg_pct" }], cells: {
  "201939": { ppg: { value: 28.5, citation: boardCitation("silver_player_season", "PPG") }, ts_pct: { value: 60, citation: boardCitation("silver_advanced", "TS_PCT") }, usg_pct: { value: 30, citation: boardCitation("silver_advanced", "USG_PCT") } },
} };

test("board fixtures generate one scoped, ordered SQL cell per source table and an independent optional chart", () => {
  const before = JSON.stringify(seedBoard), draft = notebookFromBoard(seedBoard), sql = draft.cells.filter((cell) => cell.kind === "sql");
  assert.equal(sql.length, 2); assert.deepEqual(draft.origin, { kind: "board", ref: "board-fixture" });
  assert.match(draft.cells[0].source, /Stephen Curry[\s\S]*Nikola Jokić[\s\S]*ppg, ts_pct, usg_pct/);
  for (const cell of sql) { assert.match(cell.source, /"_season" = '2025-26'/); assert.match(cell.source, /IN \(201939, 203999\)/); assert.match(cell.source, /ORDER BY "PLAYER_ID"/); assert.doesNotMatch(cell.source, /SELECT \*/); }
  assert.match(sql[1].source, /"TS_PCT", "USG_PCT"/);
  const python = draft.cells.at(-1)!;
  assert.equal(python.kind, "python"); assert.match(python.source, /Optional chart[\s\S]*df = sql\([\s\S]*barh/);
  assert.equal(JSON.stringify(seedBoard), before);
});

test("salary queries use the resolved citation identity and salary vintage, never guess a name join", () => {
  const board: Board = { ...seedBoard, columns: [{ metric_id: "salary" }], cells: { "201939": { salary: { value: 1, citation: { ...boardCitation("silver_cap_players", "salary"), season: "2026-27", row_key: { player: "O'Neal", team: "TEST" } } } } } };
  const query = notebookFromBoard(board).cells[1].source;
  assert.match(query, /201939, 'O''Neal', 'TEST'/);
  assert.match(query, /203999, NULL, NULL/);
  assert.match(query, /LEFT JOIN "silver_cap_players"[\s\S]*p\."_season" = '2026-27'/);
  assert.match(query, /ORDER BY s.PLAYER_ID/);
});

test("empty boards seed context only, missing citations and invalid identifiers produce actionable errors", () => {
  assert.equal(notebookFromBoard({ ...seedBoard, rows: [], cells: {} }).cells.length, 1);
  assert.throws(() => notebookFromBoard({ ...seedBoard, cells: {} }), /Refresh the board/);
  const invalid = structuredClone(seedBoard); invalid.cells[201939].ppg.citation.column = 'PPG"; DROP TABLE x';
  assert.throws(() => notebookFromBoard(invalid), /invalid SQL identifier/);
});
