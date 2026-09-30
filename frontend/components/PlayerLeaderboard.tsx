"use client";

import { useEffect, useMemo, useState } from "react";
import CopyLink from "./CopyLink";
import { PanelHeader } from "./ExplorePanel";
import { getQueryParam, setQueryParam } from "../lib/api";
import { BACKEND } from "../lib/chat";

const SEASONS = [
  "2015-16",
  "2016-17",
  "2017-18",
  "2018-19",
  "2019-20",
  "2020-21",
  "2021-22",
  "2022-23",
  "2023-24",
  "2024-25",
];

const STATS = [
  { key: "pts", label: "PTS" },
  { key: "reb", label: "REB" },
  { key: "ast", label: "AST" },
  { key: "stl", label: "STL" },
  { key: "blk", label: "BLK" },
  { key: "ts_pct", label: "TS%" },
  { key: "usg_pct", label: "USG%" },
  { key: "gp", label: "GP" },
  { key: "min", label: "MIN" },
] as const;

type StatKey = (typeof STATS)[number]["key"];
type SortKey = "player" | StatKey;
type SortDir = 1 | -1;
type FilterMode = "mpg" | "total" | "all";

const DEFAULT_SEASON = "2024-25";
const DEFAULT_MODE: FilterMode = "mpg";
const DEFAULT_SORT: SortKey = "pts";
const DEFAULT_DIR: SortDir = -1;
const BAR_KEYS: readonly StatKey[] = ["pts", "reb", "ast", "ts_pct"];

interface SeasonRow {
  key: string;
  name: string;
  team: string;
  pts: number | null;
  reb: number | null;
  ast: number | null;
  stl: number | null;
  blk: number | null;
  ts_pct: number | null;
  usg_pct: number | null;
  gp: number | null;
  min: number | null;
}

function toNum(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function toStr(v: unknown): string {
  return typeof v === "string" ? v : "";
}

function fmt1(v: number | null): string {
  if (v === null) return "—";
  return (Math.round(v * 10) / 10).toFixed(1);
}

function fmtPct(v: number | null): string {
  if (v === null) return "—";
  const p = Math.abs(v) <= 1.05 ? v * 100 : v;
  return `${(Math.round(p * 10) / 10).toFixed(1)}%`;
}

function fmtInt(v: number | null): string {
  if (v === null) return "—";
  return String(Math.round(v));
}

function fmtStat(key: StatKey, v: number | null): string {
  if (key === "ts_pct" || key === "usg_pct") return fmtPct(v);
  if (key === "gp") return fmtInt(v);
  return fmt1(v);
}

function lowerBound(sorted: number[], v: number): number {
  let lo = 0;
  let hi = sorted.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (sorted[mid] < v) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

function percentileFor(sorted: number[], v: number): number {
  if (sorted.length < 2) return 99;
  const below = lowerBound(sorted, v);
  return Math.min(99, Math.floor((below / (sorted.length - 1)) * 100));
}

const cellStyle: React.CSSProperties = {
  borderBottom: "1px solid var(--color-stone-border)",
  padding: "7px 10px",
  fontSize: 13,
  fontWeight: 400,
  textAlign: "right",
  fontVariantNumeric: "tabular-nums",
  whiteSpace: "nowrap",
};

const headStyle: React.CSSProperties = {
  borderBottom: "1px solid var(--color-stone-border)",
  padding: "7px 10px",
  color: "var(--color-warm-gray)",
  fontSize: 12,
  fontWeight: 500,
  textAlign: "right",
  whiteSpace: "nowrap",
};

export default function PlayerLeaderboard({
  onPlayerSelect,
}: {
  onPlayerSelect?: (playerName: string) => void;
}) {
  const [season, setSeason] = useState(DEFAULT_SEASON);
  const [mode, setMode] = useState<FilterMode>(DEFAULT_MODE);
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>(DEFAULT_SORT);
  const [sortDir, setSortDir] = useState<SortDir>(DEFAULT_DIR);
  const [pool, setPool] = useState<SeasonRow[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    const s = getQueryParam("lb_season");
    if (s && SEASONS.includes(s)) setSeason(s);
    const m = getQueryParam("lb_mode");
    if (m === "mpg" || m === "total" || m === "all") setMode(m);
    const q = getQueryParam("lb_q");
    if (q) setQuery(q);
    const sk = getQueryParam("lb_sort");
    if (sk === "player" || STATS.some((st) => st.key === sk)) setSortKey(sk as SortKey);
    const d = getQueryParam("lb_dir");
    if (d === "asc") setSortDir(1);
    else if (d === "desc") setSortDir(-1);
  }, []);

  const applySeason = (s: string) => {
    setSeason(s);
    setQueryParam("lb_season", s === DEFAULT_SEASON ? "" : s);
  };

  const applyMode = (m: FilterMode) => {
    setMode(m);
    setQueryParam("lb_mode", m === DEFAULT_MODE ? "" : m);
  };

  const applyQuery = (q: string) => {
    setQuery(q);
    setQueryParam("lb_q", q);
  };

  const applySort = (key: SortKey, dir: SortDir) => {
    setSortKey(key);
    setSortDir(dir);
    setQueryParam("lb_sort", key === DEFAULT_SORT ? "" : key);
    setQueryParam("lb_dir", dir === DEFAULT_DIR ? "" : "asc");
  };

  useEffect(() => {
    const ctrl = new AbortController();
    setStatus("loading");
    setError("");
    fetch(
      `${BACKEND}/api/v1/datasets/player_seasons?season=${encodeURIComponent(season)}&fmt=json`,
      { signal: ctrl.signal },
    )
      .then((res) => {
        if (!res.ok) throw new Error(`request failed: ${res.status}`);
        return res.json();
      })
      .then((payload: unknown) => {
        if (ctrl.signal.aborted) return;
        const rec =
          typeof payload === "object" && payload !== null
            ? (payload as Record<string, unknown>)
            : {};
        if (rec.ok === false) {
          throw new Error(
            typeof rec.error === "string" && rec.error
              ? rec.error
              : "player_seasons returned no rows",
          );
        }
        const raw = Array.isArray(rec.data)
          ? (rec.data as unknown[])
          : Array.isArray(rec.rows)
            ? (rec.rows as unknown[])
            : [];
        const rows: SeasonRow[] = (raw as Record<string, unknown>[]).map(
          (r, i) => {
            const rec2 = (typeof r === "object" && r !== null ? r : {}) as Record<
              string,
              unknown
            >;
            return {
              key: `${toStr(rec2.player_name) || i}#${toNum(rec2.player_id) ?? i}`,
              name: toStr(rec2.player_name),
              team: toStr(rec2.team_abbreviation),
              pts: toNum(rec2.pts),
              reb: toNum(rec2.reb),
              ast: toNum(rec2.ast),
              stl: toNum(rec2.stl),
              blk: toNum(rec2.blk),
              ts_pct: toNum(rec2.ts_pct),
              usg_pct: toNum(rec2.usg_pct),
              gp: toNum(rec2.gp),
              min: toNum(rec2.min),
            };
          },
        );
        setPool(rows);
        setStatus("ok");
      })
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return;
        setPool([]);
        setStatus("error");
        setError(e instanceof Error ? e.message : "player_seasons fetch failed");
      });
    return () => ctrl.abort();
  }, [season]);

  const pctByIndex = useMemo(() => {
    const sortedByKey = new Map<StatKey, number[]>();
    for (const s of STATS) {
      const vals: number[] = [];
      for (const row of pool) {
        const v = row[s.key];
        if (v !== null) vals.push(v);
      }
      vals.sort((a, b) => a - b);
      sortedByKey.set(s.key, vals);
    }
    return pool.map((row) => {
      const out = new Map<StatKey, number>();
      for (const s of STATS) {
        const v = row[s.key];
        if (v === null) continue;
        const sorted = sortedByKey.get(s.key) ?? [];
        out.set(s.key, percentileFor(sorted, v));
      }
      return out;
    });
  }, [pool]);

  const view = useMemo(() => {
    const q = query.trim().toLowerCase();
    const idx = pool.map((_, i) => i).filter((i) => {
      const row = pool[i];
      if (!row.name) return false;
      if (q && !row.name.toLowerCase().includes(q)) return false;
      if (mode === "all") return true;
      if (row.min === null || row.gp === null) return false;
      if (mode === "mpg") return row.min >= 15;
      return row.min * row.gp >= 500;
    });
    const dir = sortDir;
    idx.sort((a, b) => {
      if (sortKey === "player") {
        return pool[a].name.localeCompare(pool[b].name) * dir;
      }
      const va = pool[a][sortKey];
      const vb = pool[b][sortKey];
      if (va === null && vb === null) return 0;
      if (va === null) return 1;
      if (vb === null) return 1;
      return (va - vb) * dir;
    });
    return idx;
  }, [pool, query, mode, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey !== key) {
      applySort(key, key === "player" ? 1 : -1);
      return;
    }
    applySort(key, sortDir === 1 ? -1 : 1);
  };

  const arrow = (key: SortKey) =>
    sortKey === key ? (sortDir === 1 ? " ▲" : " ▼") : "";

  return (
    <section
      aria-label="Player season leaderboard"
      style={{ fontFamily: "var(--font-body)" }}
    >
      <PanelHeader
        kicker="Season leaderboard"
        title="Player seasons"
        action={<CopyLink panel="leaders" anchor="board" />}
      />
      <div
        style={{
          display: "flex",
          gap: 8,
          alignItems: "center",
          flexWrap: "wrap",
          marginTop: 12,
          marginBottom: 10,
        }}
      >
        <select
          className="field"
          aria-label="Season"
          value={season}
          onChange={(e) => applySeason(e.target.value)}
          style={{ fontSize: 13 }}
        >
          {SEASONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <input
          className="field"
          aria-label="Search players"
          value={query}
          onChange={(e) => applyQuery(e.target.value)}
          placeholder="Search players"
          style={{ fontSize: 13, width: 180 }}
        />
        <div
          role="group"
          aria-label="Minutes filter"
          style={{ display: "inline-flex", gap: 4 }}
        >
          {(
            [
              { v: "mpg", label: "15+ MPG" },
              { v: "total", label: "500+ MIN" },
              { v: "all", label: "All" },
            ] as { v: FilterMode; label: string }[]
          ).map((o) => (
            <button
              key={o.v}
              type="button"
              className={mode === o.v ? "tab-active" : "pill-ghost"}
              onClick={() => applyMode(o.v)}
              style={{ fontSize: 12, padding: "4px 12px" }}
            >
              {o.label}
            </button>
          ))}
        </div>
        <span
          style={{
            marginLeft: "auto",
            fontSize: 12,
            color: "var(--color-ash-gray)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          Showing {view.length} of {pool.length}
        </span>
      </div>
      {status === "loading" && (
        <div style={{ fontSize: 13, color: "var(--color-warm-gray)" }}>
          Loading player seasons...
        </div>
      )}
      {status === "error" && (
        <div style={{ fontSize: 13, color: "var(--color-warm-gray)" }}>
          player_seasons has no rows for {season}
          {error ? ` (${error})` : ""}. Try another season.
        </div>
      )}
      {status === "ok" && pool.length === 0 && (
        <div style={{ fontSize: 13, color: "var(--color-warm-gray)" }}>
          player_seasons returned no rows for {season}. Try another season.
        </div>
      )}
      {status === "ok" && pool.length > 0 && view.length === 0 && (
        <div style={{ fontSize: 13, color: "var(--color-warm-gray)" }}>
          No players match this filter for {season}. Loosen the minutes filter
          or clear the search.
        </div>
      )}
      {status === "ok" && view.length > 0 && (
        <div
          className="dime-table table-scroll"
          style={{
            border: "1px solid var(--color-stone-border)",
            borderRadius: 10,
            background: "var(--color-pure-white)",
            boxShadow: "var(--shadow-card)",
          }}
        >
          <table
            style={{
              borderCollapse: "collapse",
              width: "100%",
              fontFamily: "var(--font-body)",
            }}
          >
            <thead>
              <tr>
                <th
                  style={{
                    ...headStyle,
                    textAlign: "left",
                    position: "sticky",
                    left: 0,
                    background: "var(--color-pure-white)",
                  }}
                >
                  <button
                    type="button"
                    onClick={() => toggleSort("player")}
                    aria-sort={
                      sortKey === "player"
                        ? sortDir === 1
                          ? "ascending"
                          : "descending"
                        : "none"
                    }
                    title="Sort by player"
                    style={{
                      background: "none",
                      border: "none",
                      padding: 0,
                      font: "inherit",
                      color: "inherit",
                      cursor: "pointer",
                      fontWeight: 600,
                      fontSize: 10,
                      letterSpacing: ".08em",
                      textTransform: "uppercase",
                    }}
                  >
                    Player{arrow("player")}
                  </button>
                </th>
                {STATS.map((s) => (
                  <th key={s.key} style={headStyle}>
                    <button
                      type="button"
                      onClick={() => toggleSort(s.key)}
                      aria-sort={
                        sortKey === s.key
                          ? sortDir === 1
                            ? "ascending"
                            : "descending"
                          : "none"
                      }
                      title={`Sort by ${s.label}`}
                      style={{
                        background: "none",
                        border: "none",
                        padding: 0,
                        font: "inherit",
                        color: "inherit",
                        cursor: "pointer",
                        fontWeight: 600,
                        fontSize: 10,
                        letterSpacing: ".08em",
                        textTransform: "uppercase",
                        fontVariantNumeric: "tabular-nums",
                      }}
                    >
                      {s.label}
                      {arrow(s.key)}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {view.map((i) => {
                const row = pool[i];
                const pcts = pctByIndex[i];
                return (
                  <tr
                    key={row.key}
                    onClick={onPlayerSelect ? () => onPlayerSelect(row.name) : undefined}
                    style={onPlayerSelect ? { cursor: "pointer" } : undefined}
                  >
                    <td
                      style={{
                        ...cellStyle,
                        textAlign: "left",
                        position: "sticky",
                        left: 0,
                        background: "var(--color-pure-white)",
                      }}
                    >
                      {onPlayerSelect ? (
                        <button
                          type="button"
                          onClick={() => onPlayerSelect(row.name)}
                          title={`Open ${row.name}`}
                          style={{
                            background: "none",
                            border: "none",
                            padding: 0,
                            font: "inherit",
                            cursor: "pointer",
                            color: "var(--color-cyan-edge)",
                            textAlign: "left",
                            fontWeight: 500,
                            textDecoration: "underline",
                            textUnderlineOffset: 2,
                          }}
                        >
                          {row.name}
                        </button>
                      ) : (
                        <span style={{ fontWeight: 500 }}>{row.name}</span>
                      )}
                      {row.team && (
                        <span
                          style={{
                            marginLeft: 6,
                            fontSize: 11,
                            color: "var(--color-ash-gray)",
                          }}
                        >
                          {row.team}
                        </span>
                      )}
                    </td>
                    {STATS.map((s) => {
                      const v = row[s.key];
                      const p = pcts.get(s.key);
                      return (
                        <td key={s.key} style={cellStyle}>
                          {fmtStat(s.key, v)}
                          {p !== undefined && (
                            <sub
                              style={{
                                marginLeft: 3,
                                fontSize: 9,
                                color: "var(--color-ash-gray)",
                                fontVariantNumeric: "tabular-nums",
                              }}
                            >
                              {p}
                            </sub>
                          )}
                          {p !== undefined && BAR_KEYS.includes(s.key) && (
                            <span
                              style={{
                                display: "block",
                                width: 36,
                                height: 3,
                                marginTop: 3,
                                marginLeft: "auto",
                                background: "var(--color-stone-border)",
                                borderRadius: 2,
                                overflow: "hidden",
                              }}
                            >
                              <span
                                style={{
                                  display: "block",
                                  width: `${p}%`,
                                  height: "100%",
                                  background: "var(--color-cyan-signal)",
                                }}
                              />
                            </span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <div
        style={{
          marginTop: 8,
          fontSize: 12,
          color: "var(--color-ash-gray)",
        }}
      >
        Per-game numbers from player_seasons. Subscripts mark the 0-99
        percentile within this season. RAPTOR is unavailable for this season,
        so those columns are left out rather than estimated.
      </div>
    </section>
  );
}
