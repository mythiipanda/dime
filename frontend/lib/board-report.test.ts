import test from "node:test";
import assert from "node:assert/strict";
import { boardReportHtml, boardReportMarkdown, buildBoardReport, refreshBoardPins } from "./board-report";
import { newBoard, pinArtifact, type Board, type BoardCell, type BoardMetric } from "./boards";
import type { DimeArtifact, TableArtifactPayload } from "./dime-stream";

const metric: BoardMetric = { id: "ppg", label: "Points", category: "Scoring", unit: "per_game", table: "silver_player_season", column: "PPG", higher_is_better: true, definition: "Points per game." };
const cited: BoardCell = { value: 24.6, citation: { table: "silver_player_season", column: "PPG", season: "2026-27", sql: "SELECT * FROM silver_player_season", params: ["2026-27"], source: "warehouse", fetched_at: "2026-11-19", row_key: { PLAYER_ID: 1 } } };
const card = { kind: "player_card", title: "Shai Gilgeous-Alexander", playerName: "Shai Gilgeous-Alexander", nameColumn: "PLAYER", sourceRef: "season", sourceRow: 0, metrics: [{ column: "PTS", label: "Points", value: 31.4, unit: "per_game" }], provenance: { origin: "warehouse", liveSources: [], capability: "sql_exec", season: "2026-27", as_of: "2026-11-19", sql: "SELECT PTS FROM s" } } as unknown as DimeArtifact & { metrics: { column: string; label: string; value: number | null }[]; provenance: { sql?: string } };
const memo: TableArtifactPayload = { kind: "table", title: "Trade notes", columns: [{ key: "A", label: "Note" }], rows: [["value"]] };

function board(): Board {
  let next: Board = { ...newBoard(), title: "FA guards", season: "2026-27", rows: [{ player_id: 1, name: "Player One", team: "OKC" }], columns: [{ metric_id: "ppg" }], cells: { "1": { ppg: cited } } };
  next = pinArtifact(next, card);
  next = pinArtifact(next, memo);
  return next;
}

test("report carries board grid with citations and each pin's provenance and as-of dates", () => {
  const report = buildBoardReport(board(), [metric]);
  const md = boardReportMarkdown(report);
  assert.match(md, /# FA guards/);
  assert.match(md, /Player board · 2026-27/);
  assert.match(md, /Player One/);
  assert.match(md, /24\.6/);
  assert.match(md, /\[1\] Points: silver_player_season\.PPG · 2026-27/);
  assert.match(md, /## Shai Gilgeous-Alexander/);
  assert.match(md, /player card · pinned/);
  assert.match(md, /data as pinned/);
  assert.match(md, /Points: 31\.4 per_game/);
  assert.match(md, /Source: sql_exec · 2026-27 · 2026-11-19/);
  assert.match(md, /SQL: SELECT PTS FROM s/);
  assert.match(md, /## Trade notes/);
  assert.match(md, /\| Note \|/);
});

test("shot chart pins export zone labels and percent on the 0-100 scale", () => {
  const shot = { kind: "shot_chart", title: "Zones", zones: [{ x: 0, y: 0, att: 120, makes: 79, pct: 65.8, label: "Rim", delta: 3.1 }, { x: -220, y: 230, att: 57, pct: 35.1 }] } as unknown as DimeArtifact;
  const b = pinArtifact({ ...newBoard(), title: "Shots" }, shot);
  const md = boardReportMarkdown(buildBoardReport(b, [metric]));
  assert.match(md, /Rim: 120 attempts, 65\.8%, 79 makes, \+3\.1 pts vs league/);
  assert.match(md, /\(-220, 230\): 57 attempts, 35\.1%/);
  assert.ok(!/6580|3510/.test(md), md);
});

test("report escapes html and renders the same content for pdf", () => {
  const report = buildBoardReport({ ...board(), title: "Board <script>" }, [metric]);
  const html = boardReportHtml(report);
  assert.match(html, /Board &lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /Shai Gilgeous-Alexander/);
  assert.match(html, /@page/);
});

test("refreshBoardPins re-runs sql-backed pins, stamps refreshed_at and tolerates failures", async () => {
  const fresh = { ...card, provenance: { ...(card as { provenance: object }).provenance, sql: "SELECT PTS FROM s" } } as DimeArtifact;
  let called = 0;
  const { board: next, ran, failed } = await refreshBoardPins(board(), async sql => {
    called += 1;
    assert.equal(sql, "SELECT PTS FROM s");
    return { rows: [{ PTS: 40.0 }] };
  });
  assert.equal(called, 1);
  assert.equal(ran, 1);
  assert.deepEqual(failed, []);
  const pin = next.pins![0];
  assert.ok(pin.refreshed_at);
  assert.equal((pin.artifact as typeof card).metrics[0].value, 40.0);
  assert.equal((board().pins![0].artifact as typeof card).metrics[0].value, 31.4);
  const broken = await refreshBoardPins(board(), async () => { throw new Error("down"); });
  assert.deepEqual(broken.failed, ["Shai Gilgeous-Alexander"]);
  assert.equal(broken.board.pins![0].refreshed_at, undefined);
});
