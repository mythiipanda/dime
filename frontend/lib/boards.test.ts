import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { addColumn, addRow, applyPinRerun, boardCsv, boardPrompt, boardTemplates, boardsArePersistent, cardRequeries, columnPercentiles, deleteBoard, duplicateBoard, getBoard, listBoards, newBoard, pinArtifact, removeColumn, removeRow, reorderColumns, reorderRows, saveBoard, sortByColumn, unpinArtifact, updatePin, validBoard, type Board, type BoardCell, type BoardMetric } from "./boards";
import type { DimeArtifact, TableArtifactPayload } from "./dime-stream";

const metric: BoardMetric = { id: "ppg", label: "Points", category: "Scoring", unit: "per_game", table: "silver_player_season", column: "PPG", higher_is_better: true, definition: "Points per game." };
const cell = (value: number | null): BoardCell => ({ value, citation: { table: metric.table, column: metric.column, season: "2025-26", sql: "SELECT * FROM silver_player_season WHERE _season = ?", params: ["2025-26"], source: "warehouse", fetched_at: "2026-09-01", row_key: { PLAYER_ID: 1 } }, ...(value == null ? { reason: "no_metric_row" } : {}) });
function sample(): Board { return { ...newBoard(), title: "FA guard targets", rows: [1, 2, 3, 4].map((id) => ({ player_id: id, name: `Player ${id}`, team: "OKC" })), columns: [{ metric_id: "ppg" }], cells: { "1": { ppg: cell(10) }, "2": { ppg: cell(null) }, "3": { ppg: cell(20) }, "4": { ppg: cell(20) } } }; }
function install() { const dom = new JSDOM("", { url: "http://localhost" }); Object.assign(globalThis, { window: dom.window }); return dom; }

test("boards round trip through versioned local storage, rename, duplicate and delete", () => {
  const dom = install();
  try {
    const original = sample(); saveBoard(original);
    assert.ok(JSON.parse(dom.window.localStorage.getItem("dime_boards_v1")!).version === 1);
    assert.deepEqual(getBoard(original.id)?.cells, original.cells);
    saveBoard({ ...original, title: "Renamed" });
    assert.equal(getBoard(original.id)?.title, "Renamed");
    const copy = saveBoard(duplicateBoard(original));
    assert.notEqual(copy.id, original.id);
    assert.equal(listBoards().length, 2);
    deleteBoard(original.id);
    assert.equal(getBoard(original.id), null);
    assert.equal(getBoard(copy.id)?.title, "FA guard targets · copy");
  } finally { dom.window.close(); }
});

test("validation rejects corrupt, nonfinite, duplicate, oversized and unknown-version documents", () => {
  const dom = install();
  try {
    const board = sample();
    assert.ok(validBoard(board));
    for (const invalid of [null, {}, { ...board, season: "oops" }, { ...board, updated_at: "bad" }, { ...board, rows: [...board.rows, board.rows[0]] }, { ...board, columns: Array(31).fill({ metric_id: "ppg" }) }, { ...board, cells: { "1": { ppg: cell(Infinity) } } }, { ...board, cells: { "999": { ppg: cell(2) } } }, { ...board, cells: { "1": { ppg: { ...cell(2), citation: {} } } } }]) assert.equal(validBoard(invalid), false);
    dom.window.localStorage.setItem("dime_boards_v1", "not json"); assert.deepEqual(listBoards(), []);
    dom.window.localStorage.setItem("dime_boards_v1", JSON.stringify({ version: 2, boards: [board] })); assert.deepEqual(listBoards(), []);
    dom.window.localStorage.setItem("dime_boards_v1", JSON.stringify({ version: 1, boards: [board, {}, board] })); assert.equal(listBoards().length, 1);
    assert.throws(() => saveBoard({ ...board, rows: Array(51).fill(board.rows[0]) }), /invalid document/);
  } finally { dom.window.close(); }
});

test("column presentation snapshots round trip while legacy boards remain valid", () => {
  const dom = install();
  try {
    const legacy = sample();
    assert.equal(validBoard(legacy), true);
    const saved = saveBoard(legacy, [metric]);
    assert.deepEqual(getBoard(saved.id)?.columns[0].presentation, { label: "Points", unit: "per_game", format: "decimal" });
    const snapshot = saved.columns[0].presentation!;
    for (const presentation of [null, {}, { ...snapshot, unit: "unknown" }, { ...snapshot, format: "unknown" }, { ...snapshot, label: 1 }]) {
      assert.equal(validBoard({ ...saved, columns: [{ metric_id: "ppg", presentation }] }), false);
    }
    assert.equal(getBoard(saveBoard(duplicateBoard(saved)).id)?.columns[0].presentation?.label, "Points");
  } finally { dom.window.close(); }
});

test("failed storage writes use a readable memory shadow instead of returning stale disk values", () => {
  const dom = install();
  try {
    const board = sample(); saveBoard(board);
    Object.defineProperty(dom.window.localStorage, "unused", { value: true });
    const proto = Object.getPrototypeOf(dom.window.localStorage);
    const original = proto.setItem;
    proto.setItem = () => { throw new Error("quota exceeded"); };
    try {
      saveBoard({ ...board, title: "Memory only" });
      assert.equal(boardsArePersistent(), false);
      assert.equal(getBoard(board.id)?.title, "Memory only");
      deleteBoard(board.id); assert.equal(getBoard(board.id), null);
    } finally { proto.setItem = original; }
  } finally { dom.window.close(); }
});

test("unavailable localStorage falls back to memory", () => {
  const dom = install();
  try { Object.defineProperty(dom.window, "localStorage", { get() { throw new Error("denied"); } }); const b = saveBoard(sample()); assert.ok(getBoard(b.id)); assert.equal(boardsArePersistent(), false); deleteBoard(b.id); } finally { dom.window.close(); }
});

test("storage writes retry and persist the memory shadow after quota space is freed", () => {
  const dom = install();
  const proto = Object.getPrototypeOf(dom.window.localStorage);
  const original = proto.setItem;
  try {
    const first = saveBoard(sample());
    const second = saveBoard(duplicateBoard(first));
    let attempts = 0;
    proto.setItem = function(key: string, value: string) {
      attempts++;
      if (JSON.parse(value).boards.length > 1) throw new Error("quota exceeded");
      return original.call(this, key, value);
    };
    saveBoard({ ...first, title: "Memory edit" });
    assert.equal(boardsArePersistent(), false);
    assert.equal(getBoard(first.id)?.title, "Memory edit");
    deleteBoard(second.id);
    assert.equal(attempts, 2);
    assert.equal(boardsArePersistent(), true);
    const disk = JSON.parse(dom.window.localStorage.getItem("dime_boards_v1")!);
    assert.equal(disk.boards.length, 1);
    assert.equal(disk.boards[0].title, "Memory edit");
    saveBoard({ ...first, title: "Durable again" });
    assert.equal(getBoard(first.id)?.title, "Durable again");
    assert.equal(attempts, 3);
  } finally { proto.setItem = original; dom.window.close(); }
});

test("row and column helpers are immutable, unique, capped and clear removed caches", () => {
  const board = sample(); const original = JSON.stringify(board);
  assert.equal(addRow(board, board.rows[0]), board);
  assert.equal(addColumn(board, "ppg"), board);
  assert.equal(addRow(board, { player_id: 5, name: "Five", team: "DEN" }).rows.length, 5);
  assert.equal(addColumn(board, "ts_pct").columns.length, 2);
  assert.equal(removeRow(board, 1).cells["1"], undefined);
  assert.equal(removeColumn(board, "ppg").cells["1"].ppg, undefined);
  assert.deepEqual(reorderRows(board, 0, 3).rows.map((r) => r.player_id), [2, 3, 4, 1]);
  assert.deepEqual(reorderRows(board, -1, 3).rows, board.rows);
  const two = addColumn(board, "ts_pct"); assert.equal(reorderColumns(two, 0, 1).columns[0].metric_id, "ts_pct");
  assert.equal(JSON.stringify(board), original);
  assert.equal(addRow({ ...board, rows: Array.from({ length: 50 }, (_, i) => ({ player_id: i + 1, name: "P", team: "" })) }, { player_id: 99, name: "P", team: "" }).rows.length, 50);
});

test("quota recovery reads external saves and deletions before retrying the collection", () => {
  const dom = install();
  const proto = Object.getPrototypeOf(dom.window.localStorage);
  const original = proto.setItem;
  try {
    const deleted = saveBoard(sample());
    const retained = saveBoard(duplicateBoard(deleted));
    proto.setItem = () => { throw new Error("quota exceeded"); };
    saveBoard({ ...deleted, title: "Unsaved edit" });
    assert.equal(boardsArePersistent(), false);
    const external = { ...duplicateBoard(retained), title: "Other tab's board" };
    original.call(dom.window.localStorage, "dime_boards_v1", JSON.stringify({ version: 1, boards: [{ ...retained, title: "Other tab's rename" }, external] }));
    assert.equal(getBoard(deleted.id), null);
    assert.equal(getBoard(retained.id)?.title, "Other tab's rename");
    assert.equal(boardsArePersistent(), false);
    proto.setItem = original;
    const local = saveBoard({ ...duplicateBoard(retained), title: "New local board" });
    assert.deepEqual(new Set(listBoards().map(board => board.id)), new Set([retained.id, external.id, local.id]));
    assert.equal(getBoard(retained.id)?.title, "Other tab's rename");
    assert.equal(boardsArePersistent(), true);
  } finally { proto.setItem = original; dom.window.close(); }
});

test("sort is stable, respects metric direction and always puts nulls last", () => {
  const board = sample();
  assert.deepEqual(sortByColumn(board, metric).rows.map((r) => r.player_id), [3, 4, 1, 2]);
  assert.deepEqual(sortByColumn(board, { ...metric, higher_is_better: false }).rows.map((r) => r.player_id), [1, 3, 4, 2]);
  assert.deepEqual(sortByColumn(board, metric, false).rows.map((r) => r.player_id), [1, 3, 4, 2]);
  assert.equal(sortByColumn({ ...board, rows: [] }, metric).rows.length, 0);
});

test("percentiles handle ties, nulls, empty boards, singletons and lower-is-better metrics", () => {
  const board = sample();
  assert.deepEqual(columnPercentiles(board, metric), { "1": 0, "3": .75, "4": .75 });
  assert.deepEqual(columnPercentiles(board, { ...metric, higher_is_better: false }), { "1": 1, "3": .25, "4": .25 });
  assert.deepEqual(columnPercentiles({ ...board, rows: [] }, metric), {});
  assert.deepEqual(columnPercentiles({ ...board, rows: [board.rows[0]] }, metric), { "1": .5 });
});

test("CSV includes a citation for every metric, null reasons, quoting and spreadsheet-injection protection", () => {
  const board = sample(); board.rows[0].name = '=HYPERLINK("bad")'; board.rows[1].name = "Name, with\nnewline";
  const csv = boardCsv(board, [metric]);
  assert.match(csv, /"Points","ppg citation"/);
  assert.match(csv, /silver_player_season/);
  assert.match(csv, /no_metric_row/);
  assert.match(csv, /"'=HYPERLINK\(""bad""\)"/);
  assert.match(csv, /"Name, with\nnewline"/);
  assert.equal(boardCsv(newBoard(), []), '"Player","Team"');
});

test("templates are declarative and board prompts list the season, players and metric labels", () => {
  assert.equal(new Set(boardTemplates.map((t) => t.id)).size, boardTemplates.length);
  for (const template of boardTemplates) { assert.ok(validBoard(newBoard(template))); assert.ok(template.summary); }
  const prompt = boardPrompt(sample(), [metric]);
  for (const text of ["FA guard targets", "2025-26", "Player 1", "Points", "citations"]) assert.ok(prompt.includes(text));
});

const cardArtifact = {
  kind: "player_card",
  title: "Shai Gilgeous-Alexander",
  playerName: "Shai Gilgeous-Alexander",
  nameColumn: "PLAYER",
  sourceRef: "silver_player_season",
  sourceRow: 0,
  provenance: { origin: "warehouse", liveSources: [], capability: "sql_exec", season: "2026-27", as_of: "2026-11-19", sql: "SELECT * FROM silver_player_season WHERE PLAYER = 'Shai Gilgeous-Alexander'" },
  metrics: [
    { column: "PTS", label: "Points", value: 31.4, unit: "per_game" },
    { column: "AST", label: "Assists", value: 6.1, unit: "per_game" },
  ],
  sections: [
    { label: "Contract", sourceRef: "cap_ledger", sourceRow: 2, provenance: { origin: "warehouse", liveSources: [], capability: "sql_exec", sql: "SELECT * FROM cap_ledger WHERE PLAYER = 'Shai Gilgeous-Alexander'" }, metrics: [{ column: "SALARY", label: "Salary", value: 39, unit: "usd_millions" }], fields: [{ column: "TEAM", label: "Team", value: "OKC" }] },
    { label: "Injury", sourceRef: "injuries", sourceRow: 0 },
  ],
} as unknown as DimeArtifact & { metrics: { column: string; label: string; value: number | null }[]; sections: { metrics: { column: string; label: string; value: number | null }[]; fields: { column: string; label: string; value: string | null }[] }[] };

test("pinArtifact persists cards and memos with ids and dates, enforces the cap", () => {
  const dom = install();
  try {
    const board = sample();
    const pinned = pinArtifact(board, cardArtifact);
    assert.equal(pinned.pins?.length, 1);
    const pin = pinned.pins![0];
    assert.match(pin.id, /^pin-/);
    assert.ok(!Number.isNaN(Date.parse(pin.pinned_at)));
    assert.equal(pin.artifact, cardArtifact);
    assert.ok(validBoard(pinned));
    saveBoard(pinned);
    assert.equal(getBoard(board.id)?.pins?.[0].artifact.title, "Shai Gilgeous-Alexander");
    const memo: TableArtifactPayload = { kind: "table", title: "Notes", columns: [{ key: "A", label: "A" }], rows: [["1"]] };
    const withMemo = pinArtifact(pinned, memo);
    assert.equal(withMemo.pins?.length, 2);
    assert.notEqual(withMemo.pins![0].id, withMemo.pins![1].id);
    assert.throws(() => saveBoard({ ...withMemo, pins: Array(61).fill(pin) }), /invalid document/);
  } finally { dom.window.close(); }
});

test("unpinArtifact and updatePin are immutable and stamp refreshed_at", () => {
  const dom = install();
  try {
    const pinned = saveBoard(pinArtifact(sample(), cardArtifact));
    const pinId = pinned.pins![0].id;
    const updated = updatePin(pinned, pinId, { ...cardArtifact, title: "Updated" });
    assert.equal(updated.pins?.[0].artifact.title, "Updated");
    assert.ok(!Number.isNaN(Date.parse(updated.pins![0].refreshed_at!)));
    assert.equal(pinned.pins![0].artifact.title, "Shai Gilgeous-Alexander");
    assert.equal(unpinArtifact(updated, pinId).pins?.length, 0);
    assert.equal(unpinArtifact(updated, "missing").pins?.length, 1);
    assert.equal(getBoard(pinned.id)?.pins?.[0].artifact.title, "Shai Gilgeous-Alexander");
  } finally { dom.window.close(); }
});

test("cardRequeries pulls header and section sql requeries and skips sections without sql", () => {
  const queries = cardRequeries(cardArtifact);
  assert.equal(queries.length, 2);
  assert.equal(queries[0].key, "header");
  assert.equal(queries[0].row, 0);
  assert.match(queries[0].sql, /silver_player_season/);
  assert.equal(queries[1].key, 0);
  assert.equal(queries[1].row, 2);
  assert.match(queries[1].sql, /cap_ledger/);
  const bare = { ...cardArtifact, sections: undefined, provenance: { origin: "warehouse", liveSources: [], capability: "get_leaders" } } as unknown as DimeArtifact;
  assert.equal(cardRequeries(bare).length, 0);
});

test("applyPinRerun re-resolves values from rerun rows and keeps pinned values on misses", () => {
  const rows = new Map<"header" | number, Record<string, unknown> | undefined>();
  rows.set("header", { PTS: 33.0, AST: null });
  rows.set(0, { SALARY: 41, TEAM: "Oklahoma City Thunder" });
  const next = applyPinRerun(cardArtifact, rows) as typeof cardArtifact;
  assert.equal(next.metrics[0].value, 33.0);
  assert.equal(next.metrics[1].value, null);
  assert.equal(next.sections[0].metrics[0].value, 41);
  assert.equal(next.sections[0].fields[0].value, "Oklahoma City Thunder");
  assert.equal(cardArtifact.metrics[0].value, 31.4);
  const missed = applyPinRerun(cardArtifact, new Map()) as typeof cardArtifact;
  assert.equal(missed.metrics[0].value, 31.4);
  assert.equal(missed.sections[0].metrics[0].value, 39);
  const wrongType = applyPinRerun(cardArtifact, new Map([["header", { PTS: "not-a-number" }]])) as typeof cardArtifact;
  assert.equal(wrongType.metrics[0].value, 31.4);
});
