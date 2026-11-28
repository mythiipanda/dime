"use client";

import { ArrowLeft, ArrowRight, ArrowUp, ArrowDown, Database, X } from "lucide-react";
import { Button } from "./ds/Button";
import { ValuePill } from "./ds/ValuePill";
import { Popover, PopoverTrigger, PopoverContent } from "./ui/popover";
import { columnPercentiles, metricPresentation, type Board, type BoardCell, type BoardColumn, type BoardMetric, type BoardPresentation } from "../lib/boards";

export function formatBoardValue(value: number, presentation?: BoardPresentation): string {
  if (!presentation) return value.toLocaleString("en-US", { maximumFractionDigits: 4 });
  if (presentation.format === "currency") return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(value);
  return value.toLocaleString("en-US", { minimumFractionDigits: presentation.format === "integer" ? 0 : 1, maximumFractionDigits: presentation.format === "integer" ? 0 : 1 }) + (presentation.format === "percent" ? "%" : "");
}

export function BoardValue({ cell, metric, column, player }: { cell: BoardCell; metric?: BoardMetric; column: BoardColumn; player: string }) {
  const c = cell.citation;
  const presentation = metric ? metricPresentation(metric) : column.presentation;
  const label = presentation?.label || column.metric_id;
  const reasons: Record<string, string> = {
    unmatched_salary_name: "No 2026-27 salary row for this player",
    ambiguous_salary_name: "Name matches multiple players; salary cannot be assigned safely",
    ambiguous_salary_rows: "Multiple salary rows match this player",
    identity_incomplete: "Player identity data is incomplete; salary cannot be matched safely",
    unknown_player: "Player not found in this season's warehouse data",
    unknown_metric: "This metric is not available",
    ambiguous_metric_rows: "Multiple rows match this player and metric",
    no_metric_row: "No data for this player and metric in the selected season",
    missing_or_nonfinite_value: "The source row has no usable value for this metric",
  };
  const reason = cell.value == null ? (reasons[cell.reason || ""] || "This value is unavailable in the warehouse") : undefined;
  return <Popover>
    <PopoverTrigger asChild><Button variant="quiet" size="sm" className="font-mono tabular-nums" aria-label={`Source: ${player} · ${label}${reason ? ` · ${reason}` : ""}`} title={reason}>
      {cell.value == null ? <span className="text-ink-3">—</span> : formatBoardValue(cell.value, presentation)}
    </Button></PopoverTrigger>
    <PopoverContent side="bottom" align="end" aria-label={`${player} · ${label} evidence`} className="w-[min(370px,calc(100vw-32px))] gap-3 border border-line bg-surface p-4 text-ink shadow-overlay ring-0">
      <div className="flex items-center gap-2 text-[12px] font-medium"><Database width={14} />{label}<span className="ml-auto text-[10px] font-normal text-ink-3">WAREHOUSE EVIDENCE</span></div>
      <p className="text-[12px] text-ink-2">{player}<span className="float-right font-mono tabular-nums text-ink">{cell.value == null ? "Not available" : cell.value.toLocaleString("en-US", { maximumFractionDigits: 4 }) + (presentation?.unit === "pct" ? "%" : presentation?.unit === "usd" ? " USD" : "")}</span></p>
      {reason && <p role="status" className="rounded-md bg-inset px-2 py-2 text-[11px] text-ink-2">{reason}</p>}
      <dl className="grid grid-cols-[62px_1fr] gap-x-3 gap-y-2 border-y border-line py-3 text-[11px]">
        <dt className="text-ink-3">Table</dt><dd className="break-all font-mono">{c.table || "Not recorded"}</dd>
        <dt className="text-ink-3">Column</dt><dd className="font-mono">{c.column || "Not recorded"}</dd>
        <dt className="text-ink-3">Season</dt><dd>{c.season}</dd>
        <dt className="text-ink-3">Source</dt><dd className="break-all">{c.source || "Not recorded"}</dd>
        <dt className="text-ink-3">Fetched</dt><dd>{c.fetched_at || "Not recorded"}</dd>
        {c.salary_vintage && <><dt className="text-ink-3">Vintage</dt><dd>{c.salary_vintage.season} salary</dd></>}
      </dl>
      <p className="text-[11px] leading-relaxed text-ink-2">{metric?.definition || "Metric catalog unavailable. Showing the saved value and warehouse evidence."}</p>
      <div><p className="mb-1.5 text-[10px] text-ink-3">SQL · PARAMETERIZED</p><pre className="max-h-28 overflow-auto whitespace-pre-wrap rounded-md bg-inset p-2 font-mono text-[10px] leading-relaxed text-ink-2">{c.sql || "Query not recorded"}{"\n"}Params: {JSON.stringify(c.params)}</pre></div>
      <details className="text-[11px] text-ink-3"><summary>Row key{c.identity_resolution ? " & identity resolution" : ""}</summary><pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap break-all font-mono text-[10px]">{JSON.stringify({ row_key: c.row_key, identity_resolution: c.identity_resolution }, null, 2)}</pre></details>
    </PopoverContent>
  </Popover>;
}


export function BoardsTable({ board, metrics, loading, sort, onSort, onRemoveRow, onRemoveColumn, onMoveRow, onMoveColumn, readOnly = false }: {
  board: Board; metrics: BoardMetric[]; loading: boolean; sort: { id: string; best: boolean } | null;
  onSort: (metric: BoardMetric) => void; onRemoveRow: (id: number) => void; onRemoveColumn: (id: string) => void;
  onMoveRow: (from: number, to: number) => void; onMoveColumn: (from: number, to: number) => void;
  readOnly?: boolean;
}) {
  const ranks = Object.fromEntries(metrics.map(metric => [metric.id, columnPercentiles(board, metric)]));
  return <div className="overflow-x-auto rounded-xl border border-line bg-surface">
    <table className="w-full border-collapse text-left text-xs" aria-label={board.title} aria-busy={loading}>
      <thead className="border-b border-line bg-inset"><tr><th scope="col" className="min-w-64 px-4 py-3 font-medium">Player</th>
        {board.columns.map(({ metric_id, presentation }, index) => {
          const metric = metrics.find(item => item.id === metric_id);
          const label = metric?.label || presentation?.label || metric_id;
          const unit = metric?.unit || presentation?.unit;
          return <th scope="col" key={metric_id} className="min-w-40 px-3 py-3 text-right font-normal" aria-sort={sort?.id === metric_id && metric ? (metric.higher_is_better === sort.best ? "descending" : "ascending") : "none"}>
            <div className="flex items-center justify-end gap-1"><Button size="xs" variant="quiet" disabled={!metric || readOnly} title={metric?.definition} onClick={() => metric && onSort(metric)}>{label}{sort?.id === metric_id && (metric?.higher_is_better === sort.best ? " ↓" : " ↑")}</Button>
              {!readOnly && <Popover><PopoverTrigger asChild><Button size="xs" variant="quiet" aria-label={`Manage ${label}`}>···</Button></PopoverTrigger><PopoverContent align="end" aria-label={`Manage ${label}`}>
                <Button size="sm" variant="quiet" disabled={index === 0} onClick={() => onMoveColumn(index, index - 1)}><ArrowLeft size={13} />Move left</Button>
                <Button size="sm" variant="quiet" disabled={index === board.columns.length - 1} onClick={() => onMoveColumn(index, index + 1)}><ArrowRight size={13} />Move right</Button>
                <Button size="sm" variant="quiet" onClick={() => onRemoveColumn(metric_id)}>Remove metric</Button>
              </PopoverContent></Popover>}
            </div><p className="mt-1 text-[10px] text-ink-3">{unit === "usd" ? "2026–27 · USD" : unit === "per_game" ? "Per game" : unit === "pct" ? "Percent" : unit || "Metric"}</p>
          </th>;
        })}
      </tr></thead>
      <tbody className="divide-y divide-line">{board.rows.map((row, index) => <tr key={row.player_id} className="hover:bg-hover">
        <th scope="row" className="px-4 py-3 font-normal"><div className="flex items-center gap-3"><span className="font-mono text-[10px] text-ink-3">{String(index + 1).padStart(2, "0")}</span><div className="min-w-28 flex-1"><p className="font-medium">{row.name}</p><p className="mt-1 text-[10px] text-ink-3">{row.team || "Team not recorded"}</p></div>
          {!readOnly && <Popover><PopoverTrigger asChild><Button size="xs" variant="quiet" aria-label={`Manage ${row.name}`}>···</Button></PopoverTrigger><PopoverContent align="start" aria-label={`Manage ${row.name}`}>
            <Button size="sm" variant="quiet" disabled={index === 0} onClick={() => onMoveRow(index, index - 1)}><ArrowUp size={13} />Move up</Button>
            <Button size="sm" variant="quiet" disabled={index === board.rows.length - 1} onClick={() => onMoveRow(index, index + 1)}><ArrowDown size={13} />Move down</Button>
            <Button size="sm" variant="quiet" onClick={() => onRemoveRow(row.player_id)}><X size={13} />Remove player</Button>
          </PopoverContent></Popover>}
        </div></th>
        {board.columns.map(column => { const { metric_id } = column, metric = metrics.find(item => item.id === metric_id), cell = board.cells[row.player_id]?.[metric_id]; return <td key={metric_id} className="px-3 py-3 text-right">
          {cell ? <div className="flex items-center justify-end gap-1"><BoardValue cell={cell} metric={metric} column={column} player={row.name} />{ranks[metric_id]?.[row.player_id] === 1 && <ValuePill tone="accent">Best</ValuePill>}</div> : <span className="text-ink-3">{loading ? "Loading…" : "Not filled"}</span>}
        </td>; })}
      </tr>)}</tbody>
    </table>
  </div>;
}
