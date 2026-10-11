"use client";

import { useEffect, useMemo, useState } from "react";
import WorkspaceShell from "@/components/site/WorkspaceShell";
import {
  getWarehouseTables,
  type WarehouseSourceBadge,
  type WarehouseTableRow,
} from "@/lib/api";
import { getSeason2627Coverage, hasSeason2627 } from "@/lib/warehouse";

export { getSeason2627Coverage, hasSeason2627 };

type SourceFilter = "all" | WarehouseSourceBadge;
type SeasonFilter = "all" | "with-season" | "without-season";
type SortKey = "rows-desc" | "rows-asc" | "name";

const SOURCE_OPTIONS: { value: SourceFilter; label: string }[] = [
  { value: "all", label: "All sources" },
  { value: "nba_official", label: "NBA official" },
  { value: "bbref", label: "Basketball-Reference" },
  { value: "derived", label: "Derived" },
  { value: "internal", label: "Internal" },
  { value: "unknown", label: "Unknown" },
];

const SEASON_OPTIONS: { value: SeasonFilter; label: string }[] = [
  { value: "all", label: "Any season info" },
  { value: "with-season", label: "With season range" },
  { value: "without-season", label: "Without season range" },
];

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "rows-desc", label: "Most rows first" },
  { value: "rows-asc", label: "Fewest rows first" },
  { value: "name", label: "Name A–Z" },
];

const SOURCE_LABEL: Record<WarehouseSourceBadge, string> = {
  nba_official: "NBA official",
  bbref: "Basketball-Reference",
  derived: "Derived",
  internal: "Internal",
  unknown: "Unknown",
};

function fmtRows(n: number) {
  return n.toLocaleString("en-US");
}

function fmtSeason(table: WarehouseTableRow) {
  const range = table.season_range;
  if (!range) return "—";
  if (range.min === range.max) return range.min;
  return `${range.min} – ${range.max}`;
}

function selectClass() {
  return "h-8 min-w-0 max-w-full rounded-[8px] border border-line bg-field px-2 text-[13px] text-ink shadow-hairline outline-none";
}

export default function WarehousePage() {
  const [tables, setTables] = useState<WarehouseTableRow[]>([]);
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [source, setSource] = useState<SourceFilter>("all");
  const [season, setSeason] = useState<SeasonFilter>("all");
  const [sort, setSort] = useState<SortKey>("rows-desc");

  useEffect(() => {
    let cancelled = false;
    getWarehouseTables()
      .then((rows) => {
        if (!cancelled) {
          setTables(rows);
          setLoaded(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFailed(true);
          setLoaded(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const visible = useMemo(() => {
    const kept = tables.filter((t) => {
      if (source !== "all" && t.source_badge !== source) return false;
      if (season === "with-season" && !t.season_range) return false;
      if (season === "without-season" && t.season_range) return false;
      return true;
    });
    kept.sort((a, b) => {
      if (sort === "name") return a.name.localeCompare(b.name);
      if (sort === "rows-asc") return a.row_count - b.row_count;
      return b.row_count - a.row_count;
    });
    return kept;
  }, [tables, source, season, sort]);

  const totalRows = useMemo(
    () => tables.reduce((sum, t) => sum + t.row_count, 0),
    [tables],
  );

  return (
    <WorkspaceShell active="Warehouse">
      <main className="flex min-h-0 flex-1 flex-col overflow-hidden bg-page">
        <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[14px] border border-line bg-page">
          <div className="flex min-h-11 shrink-0 flex-col gap-2 border-b border-line px-4 py-2 sm:flex-row sm:items-center sm:justify-between sm:py-0">
            <h1 className="w-full min-w-0 truncate text-[13.5px] font-medium text-ink sm:w-auto sm:flex-1">
              Warehouse
              {!failed && loaded && tables.length > 0 && (
                <span className="ml-2 font-mono text-[11px] tabular-nums text-ink-3">
                  {tables.length} tables · {fmtRows(totalRows)} rows
                </span>
              )}
            </h1>
            <div className="flex w-full max-w-full flex-wrap items-center gap-2 sm:w-auto sm:flex-nowrap sm:shrink-0">
              <label className="sr-only" htmlFor="warehouse-source">
                Filter by source
              </label>
              <select
                id="warehouse-source"
                value={source}
                onChange={(e) => setSource(e.target.value as SourceFilter)}
                className={selectClass()}
              >
                {SOURCE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <label className="sr-only" htmlFor="warehouse-season">
                Filter by season presence
              </label>
              <select
                id="warehouse-season"
                value={season}
                onChange={(e) => setSeason(e.target.value as SeasonFilter)}
                className={selectClass()}
              >
                {SEASON_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <label className="sr-only" htmlFor="warehouse-sort">
                Sort tables
              </label>
              <select
                id="warehouse-sort"
                value={sort}
                onChange={(e) => setSort(e.target.value as SortKey)}
                className={selectClass()}
              >
                {SORT_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4" aria-busy={!loaded}>
            <p className="text-[13px] text-ink-2">
              Live inventory of the DuckDB warehouse behind your analysis.{" "}
              {loaded && tables.length > 0 && (
                <span className="text-ink-3">
                  {(() => {
                    const coverage = getSeason2627Coverage(tables);
                    if (coverage === "available") return "2026-27 season: data available.";
                    if (coverage === "unavailable") return "No 2026-27 season data in the warehouse yet.";
                    return "2026-27 season coverage is unknown.";
                  })()}
                </span>
              )}
            </p>

            {failed ? (
              <p className="py-10 text-center text-[13px] text-ink-3">
                Could not reach the warehouse.
              </p>
            ) : !loaded ? (
              <p role="status" aria-live="polite" className="py-10 text-center text-[13px] text-ink-3">
                Loading tables…
              </p>
            ) : tables.length === 0 ? (
              <p role="status" data-state="empty" className="py-10 text-center text-[13px] font-medium text-ink-2">
                No tables in the warehouse.
              </p>
            ) : visible.length === 0 ? (
              <p className="py-10 text-center text-[13px] text-ink-3">
                No tables match these filters.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="mt-3 w-full text-[13px]">
                  <thead className="sticky top-0 z-10 bg-page">
                    <tr className="border-b border-line">
                      <th className="h-[32px] pr-4 text-left text-[13px] font-medium text-ink-2">
                        Table
                      </th>
                      <th className="h-[32px] pr-4 text-right text-[13px] font-medium text-ink-2">
                        Rows
                      </th>
                      <th className="h-[32px] pr-4 text-right text-[13px] font-medium text-ink-2">
                        Columns
                      </th>
                      <th className="h-[32px] pr-4 text-left text-[13px] font-medium text-ink-2">
                        Seasons
                      </th>
                      <th className="h-[32px] pr-4 text-left text-[13px] font-medium text-ink-2">
                        Source
                      </th>
                      <th className="h-[32px] text-left text-[13px] font-medium text-ink-2">
                        Description
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {visible.map((t) => (
                      <tr key={t.name} className="transition-colors duration-100 hover:bg-hover">
                        <td className="h-[32px] whitespace-nowrap pr-4 font-mono text-[12.5px] text-ink">
                          {t.name}
                        </td>
                        <td className="h-[32px] whitespace-nowrap pr-4 text-right font-mono text-[12.5px] tabular-nums text-ink-2">
                          {fmtRows(t.row_count)}
                        </td>
                        <td className="h-[32px] whitespace-nowrap pr-4 text-right font-mono text-[12.5px] tabular-nums text-ink-2">
                          {t.column_count}
                        </td>
                        <td className="h-[32px] whitespace-nowrap pr-4 font-mono text-[12.5px] text-ink-2">
                          {fmtSeason(t)}
                        </td>
                        <td className="h-[32px] whitespace-nowrap pr-4">
                          <span className="inline-flex h-6 items-center rounded-[6px] border border-line bg-inset px-2 font-mono text-[11px] text-ink-2">
                            {SOURCE_LABEL[t.source_badge]}
                          </span>
                        </td>
                        <td className="h-[32px] min-w-[220px] text-[13px] text-ink-2">
                          {t.description}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      </main>
    </WorkspaceShell>
  );
}
