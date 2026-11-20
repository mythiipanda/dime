import test from "node:test";
import assert from "node:assert/strict";
import { addCell, chartable, moveCell, newCell, notebookDraft, notebookStarters, removeCell, saveStateLabel, updateCell } from "./notebooks";
import { notebookFromAnswer, notebookFromBoard } from "./notebook-seed";
import type { AiMessage } from "./chat";
import type { Board, BoardCitation } from "./boards";
import { scoutingEvents, scoutingQuestion } from "./replay-fixture";
import { aiFromRun, applyEvent } from "./stream-event";
import { readableSnapshot } from "./notebook-snapshot";

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
  assert.match(draft.cells[1].source, /Data snapshot[\s\S]*No executable SQL/);
  assert.doesNotMatch(draft.cells[1].source, /```|Oklahoma City/);
  const output = draft.cells[1].outputs as { kind: string; data: { columns: { name: string; type: string }[]; rows: Record<string, unknown>[] } };
  assert.equal(output.kind, "snapshot");
  assert.deepEqual(output.data.columns.slice(0, 2), [{ name: "Team", type: "VARCHAR" }, { name: "GP", type: "DOUBLE" }]);
  assert.equal(output.data.rows[0].Team, "Oklahoma City");
  assert.deepEqual(updateCell(draft.cells, draft.cells[1].id, { source: "Revised snapshot context" })[1].outputs, output);
  assert.equal(updateCell(draft.cells, draft.cells[1].id, { kind: "sql" })[1].outputs, undefined);
  assert.equal(draft.origin?.ref, "dev-replay-scouting");
  assert.match(notebookFromAnswer({ text: "Nothing recorded", nodes: {}, done: true }, "").cells[1].source, /No tables/);
});

test("each recorded snapshot table keeps its own typed rows, including empty and null values", () => {
  const draft = notebookFromAnswer({ text: "Snapshots", done: true, nodes: { analytics: { status: "complete", thoughts: [], toolResults: [], toolCalls: [], tables: [
    { tool: "team_ratings", rows: [{ Team: "A", value: null, qualified: true }] },
    { tool: "team_ratings", rows: [], ...{ columns: [{ name: "Team", type: "VARCHAR" }] } },
  ] } } }, "Snapshot question");
  assert.equal(draft.cells.length, 3);
  const outputs = draft.cells.slice(1).map((cell) => cell.outputs as { data: { columns: { name: string; type: string }[]; rows: unknown[] } });
  assert.deepEqual(outputs[0].data.columns.map((column) => column.type), ["VARCHAR", "UNKNOWN", "BOOLEAN"]);
  assert.deepEqual(outputs[1].data.rows, []);
  assert.deepEqual(outputs[1].data.columns, [{ name: "Team", type: "VARCHAR" }]);
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

test("flat public evidence becomes typed Cited values snapshots, alone or alongside recorded SQL", () => {
  for (const withSQL of [false, true]) {
    const evidence = { output_id: "NET_RATING", value: "9.4", unit: "points_per_100_possessions", subject_type: "team", subject_id: "OKC", provenance: { source: "NBA warehouse", season: "2025-26", capability: "team_ratings", table: "silver_team_ratings" } };
    const ai = aiFromRun({ question: "Rating?", answer: "Cited answer", tables: [evidence], suggestions: [], created_at: "2026-01-01" });
    if (withSQL) ai.nodes.analytics!.toolCalls = [{ name: "query_warehouse", sql: "SELECT 1", args: {} }];
    const draft = notebookFromAnswer(ai, "Rating?");
    const snapshot = draft.cells.find((cell) => cell.source.includes("### Cited values"))!;
    const output = snapshot.outputs as { kind: string; data: { columns: { name: string; type: string }[]; rows: Record<string, unknown>[]; raw_rows: unknown[] } };
    assert.equal(snapshot.kind, "markdown"); assert.equal(output.kind, "snapshot");
    assert.deepEqual(output.data.rows[0], { output: "NET_RATING", value: "9.4", unit: evidence.unit, subject: "OKC", subject_type: "team", Source: "NBA warehouse", Season: "2025-26", Capability: "team_ratings", Table: "silver_team_ratings" });
    assert.ok(output.data.columns.every((column) => column.name !== "provenance" && column.type !== "JSON"));
    assert.deepEqual(output.data.raw_rows, [evidence]);
    assert.doesNotMatch(draft.cells.map((cell) => cell.source).join("\n"), /No tables/);
  }
});

test("snapshot objects and arrays become short readable text without mutating data or losing scalars", () => {
  const input = { columns: [{ name: "details", type: "JSON" }, { name: "value", type: "DOUBLE" }], rows: [
    { details: { wins: 5, active: true, context: { season: "2025-26" } }, value: 9.4 },
    { details: ["NBA", { source: "Warehouse" }], value: null },
    { details: {}, value: 0 },
    { details: { long: "x".repeat(500), other: [1, 2, 3, 4, 5] }, value: false },
  ], truncated: false };
  const before = JSON.stringify(input), result = readableSnapshot(input);
  assert.equal(result.rows[0].details, "wins: 5 · active: true · context: season: 2025-26");
  assert.equal(result.rows[1].details, "NBA · source: Warehouse");
  assert.equal(result.rows[2].details, "—");
  assert.ok(String(result.rows[3].details).length <= 200);
  assert.deepEqual(result.rows.map((row) => row.value), [9.4, null, 0, false]);
  assert.equal(result.columns[0].type, "VARCHAR");
  assert.equal(JSON.stringify(input), before);
  assert.deepEqual(result.raw_rows, input.rows);
  assert.deepEqual(readableSnapshot(result).raw_rows, input.rows);
  assert.deepEqual(readableSnapshot({ columns: [], rows: [], truncated: false }), { columns: [], rows: [], raw_rows: [], truncated: false });
});

test("snapshot seeds preserve complete nested values behind their readable display and JSON serialization", () => {
  const rows = [{ details: { season: "2025-26", nested: { items: [1, 2, { value: "x".repeat(500) }] } } }];
  const ai = aiFromRun({ question: "Snapshot?", answer: "Answer", tables: [{ tool: "query_warehouse", rows }], suggestions: [], created_at: "2026-01-01" });
  const draft = notebookFromAnswer(ai, "Snapshot?");
  const saved = JSON.parse(JSON.stringify(draft));
  assert.deepEqual(saved.cells[1].outputs.data.raw_rows, rows);
  assert.equal(typeof saved.cells[1].outputs.data.rows[0].details, "string");
  assert.ok(saved.cells[1].outputs.data.rows[0].details.length <= 200);
});

test("Cited values preserve fetched, as-of and observed source dates without inventing one", () => {
  for (const field of ["fetched_at", "as_of", "observed_at", "observed"]) {
    for (const location of ["provenance", "meta", "top"]) {
      const when = "2026-01-02T03:04:05Z";
      const timestamp = location === "top" ? { [field]: when } : { [location]: { [field]: when } };
      const ai = aiFromRun({ question: "Date?", answer: "Answer", tables: [{ output_id: "PPG", value: 28, ...timestamp }], suggestions: [], created_at: "2026-02-01" });
      const output = notebookFromAnswer(ai, "Date?").cells[1].outputs as { data: { rows: Record<string, unknown>[] } };
      assert.equal(output.data.rows[0]["As of"], when);
    }
  }
  const ai = aiFromRun({ question: "Date?", answer: "Answer", tables: [{ output_id: "PPG", value: 28 }], suggestions: [], created_at: "2026-02-01" });
  assert.ok(!Object.hasOwn((notebookFromAnswer(ai, "Date?").cells[1].outputs as { data: { rows: Record<string, unknown>[] } }).data.rows[0], "As of"));
});

test("reopened answers retain run identity and flat citations; unidentified answers get unique origins", () => {
  const ai = aiFromRun({ id: "saved-run-id", question: "Question", answer: "Answer", tables: [{ output_id: "PPG", value: "28", subject_id: 201939, unit: "points", provenance: { source: "NBA warehouse" } }], suggestions: [], created_at: "2026-01-01" });
  assert.equal(ai.carry?.run_id, "saved-run-id");
  const draft = notebookFromAnswer(ai, "Question");
  assert.deepEqual(draft.origin, { kind: "chat", ref: "saved-run-id" });
  assert.match(draft.cells[1].source, /Cited values/);
  const unidentified = aiFromRun({ question: "Same question", answer: "Answer", tables: [], suggestions: [], created_at: "2026-01-01" });
  const first = notebookFromAnswer(unidentified, "Same question").origin!.ref;
  const second = notebookFromAnswer(unidentified, "Same question").origin!.ref;
  assert.match(first, /^[a-f0-9-]{36}$/);
  assert.notEqual(first, second);
});

test("published warehouse, live and mixed provenance labels survive in context and Cited values", () => {
  const fixtures = [
    { provenance: { origin: "warehouse", warehouse_id: "warehouse-123", table: "silver_player_season" }, expected: "Warehouse · silver_player_season · warehouse-123" },
    { provenance: { origin: "live", warehouse_id: null, live_sources: ["nba_stats", "espn"] }, expected: "Live · nba_stats · espn" },
    { provenance: { origin: "mixed", warehouse_id: "warehouse-456", live_sources: ["nba_stats"] }, expected: "Warehouse · warehouse-456; Live · nba_stats" },
    { provenance: { source: "Legacy source", origin: "warehouse", warehouse_id: "warehouse-789" }, expected: "Legacy source" },
    { provenance: { origin: "undeclared", warehouse_id: null, live_sources: [] }, expected: "Source not recorded" },
  ];
  for (const { provenance, expected } of fixtures) {
    const ai = aiFromRun({ question: "Source?", answer: "Answer", tables: [{ output_id: "PPG", value: 28, unit: "points", subject_id: 201939, provenance }], suggestions: [], created_at: "2026-01-01" });
    const draft = notebookFromAnswer(ai, "Source?");
    assert.ok(draft.cells[0].source.includes(expected));
    assert.equal((draft.cells[1].outputs as { data: { rows: Record<string, unknown>[] } }).data.rows[0].Source, expected);
  }
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
  for (const cell of sql) { assert.match(cell.source, /"_season" = '2025-26'/); assert.match(cell.source, /VALUES \(201939, 'Stephen Curry'\),\s*\(203999, 'Nikola Jokić'\)/); assert.match(cell.source, /ORDER BY s.PLAYER_ID/); assert.doesNotMatch(cell.source, /SELECT \*/); }
  assert.match(sql[1].source, /MAX\(p\."TS_PCT"\)[\s\S]*MAX\(p\."USG_PCT"\)/);
  const python = draft.cells.at(-1)!;
  assert.equal(python.kind, "python"); assert.match(python.source, /Optional chart[\s\S]*df = sql\([\s\S]*barh/);
  assert.equal(JSON.stringify(seedBoard), before);
});

test("salary queries use the resolved citation identity and salary vintage, never guess a name join", () => {
  const board: Board = { ...seedBoard, columns: [{ metric_id: "salary" }], cells: { "201939": { salary: { value: 1, citation: { ...boardCitation("silver_cap_players", "salary"), season: "2026-27", row_key: { player: "O'Neal", team: "TEST" } } } } } };
  const query = notebookFromBoard(board).cells[1].source;
  assert.match(query, /201939, 'Stephen Curry', 'O''Neal', 'TEST'/);
  assert.match(query, /203999, 'Nikola Jokić', NULL, NULL/);
  assert.match(query, /LEFT JOIN "silver_cap_players"[\s\S]*p\."_season" = '2026-27'/);
  assert.match(query, /ORDER BY s.PLAYER_ID/);
});

test("board SQL retains missing players and blanks ambiguous source rows for every source", () => {
  for (const table of ["silver_player_season", "silver_advanced", "silver_cap_players"]) {
    const board: Board = { ...seedBoard, rows: [...seedBoard.rows, seedBoard.rows[0]], columns: [{ metric_id: "metric" }], cells: { "201939": { metric: { value: null, citation: boardCitation(table, "metric") } } } };
    const query = notebookFromBoard(board).cells[1].source;
    assert.match(query, /FROM selected s LEFT JOIN/);
    assert.match(query, /CASE WHEN COUNT\(p\."(?:PLAYER_ID|player)"\) = 1 THEN MAX\(p\."metric"\) ELSE NULL END AS "metric"/);
    assert.match(query, /COUNT\(p\."(?:PLAYER_ID|player)"\) AS rows_matched/);
    assert.match(query, /GROUP BY s.PLAYER_ID, s.player_name/);
    assert.equal(query.match(/201939,/g)!.length, 1);
    assert.match(query, /203999, 'Nikola Jokić'/);
  }
});

test("empty boards seed context only, missing citations and invalid identifiers produce actionable errors", () => {
  assert.equal(notebookFromBoard({ ...seedBoard, rows: [], cells: {} }).cells.length, 1);
  assert.throws(() => notebookFromBoard({ ...seedBoard, cells: {} }), /Refresh the board/);
  const invalid = structuredClone(seedBoard); invalid.cells[201939].ppg.citation.column = 'PPG"; DROP TABLE x';
  assert.throws(() => notebookFromBoard(invalid), /invalid SQL identifier/);
});
=======
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
>>>>>>> origin/dev
