"use client";

import { ArrowDown, ArrowUp, Database, Xmark } from "iconoir-react";
import { Popover, PopoverTrigger, PopoverContent } from "../ui/popover";
import { Shimmer } from "./Shimmer";
import { columnPercentiles, type Board, type BoardCell, type BoardMetric } from "../../lib/boards";

export function formatBoardValue(value: number, metric: BoardMetric): string {
  if (metric.unit === "usd") return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 2 }).format(value);
  return value.toLocaleString("en-US", { minimumFractionDigits: metric.unit === "count" ? 0 : 1, maximumFractionDigits: metric.unit === "count" ? 0 : 1 }) + (metric.unit === "pct" ? "%" : "");
}

function Cell({ cell, metric, player }: { cell: BoardCell; metric: BoardMetric; player: string }) {
  const c = cell.citation;
  const reason = cell.reason?.replaceAll("_", " ");
  return <Popover>
    <PopoverTrigger openOnHover delay={150} closeDelay={150} className="board-value" aria-label={`Source: ${player} · ${metric.label}`} title={reason}>
      {cell.value == null ? <span className="text-ink-3">—</span> : formatBoardValue(cell.value, metric)}
    </PopoverTrigger>
    <PopoverContent side="bottom" align="end" initialFocus={false} className="citation-card board-citation w-[370px] gap-3 border border-line bg-surface p-4 text-ink shadow-overlay ring-0">
      <div className="flex items-center gap-2 text-[12px] font-medium"><Database width={14} />{metric.label}<span className="ml-auto text-[10px] font-normal text-ink-3">WAREHOUSE EVIDENCE</span></div>
      <p className="text-[12px] text-ink-2">{player}<span className="float-right font-mono tabular-nums text-ink">{cell.value == null ? "Not available" : cell.value.toLocaleString("en-US", { maximumFractionDigits: 4 }) + (metric.unit === "pct" ? "%" : metric.unit === "usd" ? " USD" : "")}</span></p>
      {reason && <p role="status" className="rounded-md bg-inset px-2 py-2 text-[11px] text-ink-2">{reason}</p>}
      <dl className="grid grid-cols-[62px_1fr] gap-x-3 gap-y-2 border-y border-line py-3 text-[11px]">
        <dt className="text-ink-3">Table</dt><dd className="break-all font-mono">{c.table || "Not recorded"}</dd>
        <dt className="text-ink-3">Column</dt><dd className="font-mono">{c.column || "Not recorded"}</dd>
        <dt className="text-ink-3">Season</dt><dd>{c.season}</dd>
        <dt className="text-ink-3">Source</dt><dd className="break-all">{c.source || "Not recorded"}</dd>
        <dt className="text-ink-3">Fetched</dt><dd>{c.fetched_at || "Not recorded"}</dd>
        {c.salary_vintage && <><dt className="text-ink-3">Vintage</dt><dd>{c.salary_vintage.season} salary</dd></>}
      </dl>
      <p className="text-[11px] leading-relaxed text-ink-2">{metric.definition}</p>
      <div><p className="mb-1.5 text-[10px] text-ink-3">SQL · PARAMETERIZED</p><pre className="max-h-28 overflow-auto whitespace-pre-wrap rounded-md bg-inset p-2 font-mono text-[10px] leading-relaxed text-ink-2">{c.sql || "Query not recorded"}{"\n"}Params: {JSON.stringify(c.params)}</pre></div>
      <details className="text-[11px] text-ink-3"><summary>Row key{c.identity_resolution ? " & identity resolution" : ""}</summary><pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap break-all font-mono text-[10px]">{JSON.stringify({ row_key: c.row_key, identity_resolution: c.identity_resolution }, null, 2)}</pre></details>
    </PopoverContent>
  </Popover>;
}

export function BoardGrid({ board, metrics, loading, sort, onSort, onRemoveRow, onRemoveColumn, onMoveRow, onMoveColumn }: {
  board: Board; metrics: BoardMetric[]; loading: boolean; sort: { id: string; best: boolean } | null;
  onSort: (metric: BoardMetric) => void; onRemoveRow: (id: number) => void; onRemoveColumn: (id: string) => void;
  onMoveRow: (from: number, to: number) => void; onMoveColumn: (from: number, to: number) => void;
}) {
  const percentile = Object.fromEntries(metrics.map((m) => [m.id, columnPercentiles(board, m)]));
  return <div className="board-grid-wrap"><table className="board-grid" aria-label={board.title} aria-busy={loading}>
    <thead><tr><th className="board-player-col"><span className="text-[10px] uppercase tracking-widest text-ink-3">Player</span><span className="ml-2 text-[10px] font-normal text-ink-3">{board.rows.length}</span></th>
      {board.columns.map(({ metric_id }, index) => { const m = metrics.find((metric) => metric.id === metric_id); return <th key={metric_id} aria-sort={sort?.id === metric_id && m ? (m.higher_is_better === sort.best ? "descending" : "ascending") : "none"}>
        <div className="flex items-center justify-end gap-1"><button className="board-column-label" title={m?.definition} onClick={() => m && onSort(m)}>{m?.label || metric_id}{sort?.id === metric_id && <span>{m?.higher_is_better === sort.best ? "↓" : "↑"}</span>}</button>
          <details className="board-column-menu"><summary aria-label={`Manage ${m?.label || metric_id}`}>⋯</summary><div className="board-menu"><button disabled={index === 0} onClick={() => onMoveColumn(index, index - 1)}>Move left</button><button disabled={index === board.columns.length - 1} onClick={() => onMoveColumn(index, index + 1)}>Move right</button><button onClick={() => onRemoveColumn(metric_id)}>Remove metric</button></div></details>
        </div><p className="mt-1 text-[9px] font-normal uppercase tracking-wider text-ink-3">{m?.unit === "usd" ? "2026–27 · USD" : m?.unit === "per_game" ? "Per game" : m?.unit === "pct" ? "Percent" : m?.unit || "Metric"}</p>
      </th>; })}
    </tr></thead>
    <tbody>{board.rows.map((row, index) => <tr key={row.player_id}>
      <td className="board-player-col"><div className="flex items-center gap-2"><span className="w-4 shrink-0 font-mono text-[10px] text-ink-3">{String(index + 1).padStart(2, "0")}</span><div className="min-w-0 flex-1"><p className="truncate text-[12px] font-medium">{row.name}</p><p className="mt-1 text-[10px] text-ink-3">{row.team || "Team not recorded"}</p></div><div className="board-row-actions"><button disabled={index === 0} aria-label={`Move ${row.name} up`} onClick={() => onMoveRow(index, index - 1)}><ArrowUp width={11} /></button><button disabled={index === board.rows.length - 1} aria-label={`Move ${row.name} down`} onClick={() => onMoveRow(index, index + 1)}><ArrowDown width={11} /></button><button aria-label={`Remove ${row.name}`} onClick={() => onRemoveRow(row.player_id)}><Xmark width={12} /></button></div></div></td>
      {board.columns.map(({ metric_id }) => { const metric = metrics.find((m) => m.id === metric_id); const cell = board.cells[row.player_id]?.[metric_id]; const p = percentile[metric_id]?.[row.player_id]; return <td key={metric_id} style={p == null ? undefined : { backgroundColor: `color-mix(in srgb, var(--green) ${3 + p * 10}%, transparent)` }}>
        {cell && metric ? <Cell cell={cell} metric={metric} player={row.name} /> : loading ? <Shimmer className="font-mono text-[11px]">···</Shimmer> : <span className="text-ink-3" title="Not filled">—</span>}
      </td>; })}
    </tr>)}</tbody>
  </table></div>;
}
