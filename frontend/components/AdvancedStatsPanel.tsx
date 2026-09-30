"use client";

import { useEffect, useMemo, useState } from "react";
import ExplorePanel, { PanelHeader } from "./ExplorePanel";
import Skeleton from "./Skeleton";
import { datasetUrl, getDatasetJson, getQueryParam, setQueryParam } from "../lib/api";

type TabKey = "rapm" | "clutch" | "lineups";

type Row = Record<string, unknown>;

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

const TABS: { key: TabKey; label: string; dataset: string; note: string }[] = [
  { key: "rapm", label: "RAPM", dataset: "rapm", note: "RAPM ranks players by regularized plus-minus for the season. Subscripts mark the 0-99 percentile in this view." },
  { key: "clutch", label: "Clutch", dataset: "clutch", note: "Clutch ranks players by late-game production for the season. Subscripts mark the 0-99 percentile in this view." },
  { key: "lineups", label: "Lineups", dataset: "lineup_leaders", note: "Five-man units sorted by net rating. Possessions estimated from box score counts. Subscripts mark the 0-99 percentile in this view." },
];

const DEFAULT_SORT: Record<TabKey, string> = { rapm: "rapm", clutch: "PTS", lineups: "NET_RTG" };

const MIN_POSS_OPTIONS = ["100", "200", "500", "1000"];

const NAME_KEYS = ["PLAYER", "PLAYER_NAME", "player_name", "full_name", "player", "name"];

function isTabKey(v: string | null): v is TabKey {
  return v === "rapm" || v === "clutch" || v === "lineups";
}

function isIdKey(k: string): boolean {
  const l = k.toLowerCase();
  return l === "id" || l.endsWith("_id");
}

function toNum(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function fmtVal(col: string, v: number): string {
  const l = col.toLowerCase();
  const pctish = l.includes("pct") || l.includes("%") || l.includes("percent") || l.includes("rate") || l.includes("share");
  if (pctish) {
    const p = Math.abs(v) <= 1.05 ? v * 100 : v;
    return `${(Math.round(p * 10) / 10).toFixed(1)}%`;
  }
  if (Number.isInteger(v)) return String(v);
  return String(Math.round(v * 1000) / 1000);
}

function pctOf(sorted: number[], v: number): number {
  if (sorted.length < 2) return 99;
  let below = 0;
  for (const x of sorted) if (x < v) below += 1;
  return Math.min(99, Math.floor((below / (sorted.length - 1)) * 100));
}

function labelKeyFor(rows: Row[]): string | null {
  if (!rows.length) return null;
  for (const k of NAME_KEYS) {
    if (typeof rows[0][k] === "string" || typeof rows[0][k] === "number") return k;
  }
  const first = rows[0];
  for (const k of Object.keys(first)) {
    if (isIdKey(k)) continue;
    if (typeof first[k] === "string") return k;
  }
  return null;
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

function readSeason(): string {
  const v = getQueryParam("adv_season");
  return v && SEASONS.includes(v) ? v : "2024-25";
}

function readMinPoss(): string {
  const v = getQueryParam("adv_minposs");
  return v && MIN_POSS_OPTIONS.includes(v) ? v : "200";
}

export default function AdvancedStatsPanel({ onPlayerSelect }: { onPlayerSelect?: (playerName: string) => void }) {
  const [tab, setTab] = useState<TabKey>(() => {
    const v = getQueryParam("adv_tab");
    return isTabKey(v) ? v : "rapm";
  });
  const [season, setSeason] = useState<string>(readSeason);
  const [minPoss, setMinPoss] = useState<string>(readMinPoss);
  const [pool, setPool] = useState<Row[]>([]);
  const [meta, setMeta] = useState<Record<string, unknown> | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState("");
  const [sortKey, setSortKey] = useState<string | null>(() => getQueryParam("adv_sort"));
  const [sortDir, setSortDir] = useState<1 | -1>(() => (getQueryParam("adv_dir") === "asc" ? 1 : -1));
  const [filter, setFilter] = useState<string>(() => getQueryParam("adv_q") ?? "");

  useEffect(() => {
    const def = TABS.find((t) => t.key === tab);
    if (!def) return;
    const ctrl = new AbortController();
    setStatus("loading");
    setError("");
    const params: Record<string, string> = { season };
    if (tab === "lineups") params.min_poss = minPoss;
    getDatasetJson(def.dataset, params)
      .then((res) => {
        if (ctrl.signal.aborted) return;
        if (!res.ok) {
          setPool([]);
          setMeta(null);
          setStatus("error");
          setError(typeof res.error === "string" && res.error ? res.error : "warehouse returned no rows");
          return;
        }
        setPool(Array.isArray(res.data) ? (res.data as Row[]) : []);
        setMeta((res.meta as Record<string, unknown>) ?? null);
        setStatus("ok");
      })
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return;
        setPool([]);
        setMeta(null);
        setStatus("error");
        setError(e instanceof Error ? e.message : "request failed");
      });
    return () => ctrl.abort();
  }, [tab, season, minPoss]);

  const cols = useMemo(() => {
    if (!pool.length) return { label: null as string | null, rest: [] as string[], numeric: new Set<string>() };
    const keys = Object.keys(pool[0]).filter((k) => !isIdKey(k));
    const label = labelKeyFor(pool);
    const rest = keys.filter((k) => k !== label);
    const numeric = new Set<string>();
    for (const k of rest) {
      if (pool.some((r) => toNum(r[k]) !== null)) numeric.add(k);
    }
    return { label, rest, numeric };
  }, [pool]);

  const nameCol = cols.label && NAME_KEYS.includes(cols.label) ? cols.label : null;

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const idx = pool.map((_, i) => i);
    if (!q) return idx;
    return idx.filter((i) =>
      Object.values(pool[i]).some((v) => String(v ?? "").toLowerCase().includes(q)),
    );
  }, [pool, filter]);

  const pcts = useMemo(() => {
    const m = new Map<string, number>();
    if (filtered.length < 2) return m;
    for (const k of cols.numeric) {
      const vals = filtered.map((i) => toNum(pool[i][k])).filter((v): v is number => v !== null);
      vals.sort((a, b) => a - b);
      for (const i of filtered) {
        const v = toNum(pool[i][k]);
        if (v !== null) m.set(`${i}:${k}`, pctOf(vals, v));
      }
    }
    return m;
  }, [pool, filtered, cols]);

  const activeSort = sortKey ?? DEFAULT_SORT[tab];

  const view = useMemo(() => {
    const idx = [...filtered];
    const dir = sortKey ? sortDir : -1;
    idx.sort((a, b) => {
      if (!cols.rest.includes(activeSort)) return 0;
      if (activeSort === cols.label) {
        return String(pool[a][activeSort] ?? "").localeCompare(String(pool[b][activeSort] ?? "")) * (sortKey ? sortDir : 1);
      }
      const va = toNum(pool[a][activeSort]);
      const vb = toNum(pool[b][activeSort]);
      if (va === null && vb === null) return 0;
      if (va === null) return 1;
      if (vb === null) return 1;
      if (cols.numeric.has(activeSort)) return (va - vb) * dir;
      return String(pool[a][activeSort] ?? "").localeCompare(String(pool[b][activeSort] ?? "")) * dir;
    });
    return idx;
  }, [filtered, activeSort, sortKey, sortDir, pool, cols]);

  const toggleSort = (k: string) => {
    if (sortKey !== k) {
      setSortKey(k);
      setSortDir(k === cols.label ? 1 : -1);
      setQueryParam("adv_sort", k, true);
      setQueryParam("adv_dir", k === cols.label ? "asc" : "desc", true);
      return;
    }
    if (sortDir === -1 && k !== cols.label) {
      setSortDir(1);
      setQueryParam("adv_dir", "asc", true);
      return;
    }
    setSortKey(null);
    setQueryParam("adv_sort", "", true);
    setQueryParam("adv_dir", "", true);
  };

  const pickTab = (t: TabKey) => {
    setTab(t);
    setSortKey(null);
    setSortDir(-1);
    setFilter("");
    setQueryParam("adv_tab", t, true);
    setQueryParam("adv_sort", "", true);
    setQueryParam("adv_dir", "", true);
    setQueryParam("adv_q", "", true);
  };

  const pickSeason = (s: string) => {
    setSeason(s);
    setQueryParam("adv_season", s, true);
  };

  const pickMinPoss = (m: string) => {
    setMinPoss(m);
    setQueryParam("adv_minposs", m, true);
  };

  const arrow = (k: string) => {
    const active = (sortKey ?? DEFAULT_SORT[tab]) === k;
    if (!active) return "";
    if (sortKey) return sortDir === 1 ? " ▲" : " ▼";
    return " ▼";
  };

  const csvParams: Record<string, string> = { season };
  if (tab === "lineups") csvParams.min_poss = minPoss;
  const csvName = TABS.find((t) => t.key === tab)?.dataset ?? tab;
  const note = TABS.find((t) => t.key === tab)?.note ?? "";
  const rowCount = typeof meta?.rows === "number" ? meta.rows : pool.length;

  return (
    <section aria-label="Advanced stats" style={{ fontFamily: "var(--font-body)" }}>
      <div className="panel-kicker">Advanced</div>
      <h2 className="panel-title" style={{ margin: "4px 0 12px" }}>
        Advanced stats
      </h2>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 10 }}>
        <div role="tablist" aria-label="Advanced stat views" style={{ display: "inline-flex", gap: 4 }}>
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={tab === t.key}
              className={tab === t.key ? "tab-active" : "pill-ghost"}
              onClick={() => pickTab(t.key)}
              style={{ fontSize: 12, padding: "4px 12px" }}
            >
              {t.label}
            </button>
          ))}
        </div>
        <select
          className="field"
          aria-label="Season"
          value={season}
          onChange={(e) => pickSeason(e.target.value)}
          style={{ fontSize: 13 }}
        >
          {SEASONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        {tab === "lineups" && (
          <div role="group" aria-label="Minimum possessions" style={{ display: "inline-flex", gap: 4, alignItems: "center" }}>
            <span style={{ fontSize: 11, color: "var(--color-ash-gray)" }}>Min poss</span>
            {MIN_POSS_OPTIONS.map((m) => (
              <button
                key={m}
                type="button"
                className={minPoss === m ? "tab-active" : "pill-ghost"}
                onClick={() => pickMinPoss(m)}
                style={{ fontSize: 12, padding: "4px 10px" }}
                aria-pressed={minPoss === m}
              >
                {m}
              </button>
            ))}
          </div>
        )}
        <input
          className="field"
          aria-label="Filter rows"
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            setQueryParam("adv_q", e.target.value);
          }}
          placeholder="Filter rows"
          style={{ fontSize: 13, width: 150 }}
        />
        <a className="pill-ghost" style={{ fontSize: 12 }} href={datasetUrl(csvName, csvParams, "csv")}>
          CSV
        </a>
        <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--color-ash-gray)", fontVariantNumeric: "tabular-nums" }}>
          Showing {view.length} of {rowCount}
        </span>
      </div>
      {status === "loading" && <Skeleton lines={5} label={`Loading ${tab} for ${season}`} />}
      {status === "error" && (
        <div style={{ fontSize: 13, color: "var(--color-warm-gray)" }}>
          {error} Try another season{tab === "lineups" ? " or a lower possession cutoff" : ""}.
        </div>
      )}
      {status === "ok" && !pool.length && (
        <div style={{ fontSize: 13, color: "var(--color-warm-gray)" }}>
          No rows for {season}. Try another season.
        </div>
      )}
      {status === "ok" && pool.length > 0 && view.length === 0 && (
        <div style={{ fontSize: 13, color: "var(--color-warm-gray)" }}>
          No rows match this filter for {season}. Clear the search.
        </div>
      )}
      {status === "ok" && view.length > 0 && (
        <div
          className="dime-table table-scroll"
          style={{ border: "1px solid var(--color-stone-border)", borderRadius: 10, background: "var(--color-pure-white)", boxShadow: "var(--shadow-card)" }}
        >
          <table style={{ borderCollapse: "collapse", width: "100%", fontFamily: "var(--font-body)" }}>
            <thead>
              <tr>
                <th style={{ ...headStyle, textAlign: "right", width: 44 }}>#</th>
                {cols.label && (
                  <th style={{ ...headStyle, textAlign: "left", position: "sticky", left: 0, background: "var(--color-pure-white)" }}>
                    <button
                      type="button"
                      onClick={() => toggleSort(cols.label as string)}
                      aria-sort={(sortKey ?? DEFAULT_SORT[tab]) === cols.label ? (sortKey && sortDir === 1 ? "ascending" : "descending") : "none"}
                      title={`Sort by ${cols.label}`}
                      style={{ background: "none", border: "none", padding: 0, font: "inherit", color: "inherit", cursor: "pointer", fontWeight: 600, fontSize: 10, letterSpacing: ".08em", textTransform: "uppercase" }}
                    >
                      {cols.label}{arrow(cols.label)}
                    </button>
                  </th>
                )}
                {cols.rest.map((c) => (
                  <th key={c} style={headStyle}>
                    <button
                      type="button"
                      onClick={() => toggleSort(c)}
                      aria-sort={(sortKey ?? DEFAULT_SORT[tab]) === c ? (sortKey && sortDir === 1 ? "ascending" : "descending") : "none"}
                      title={`Sort by ${c}`}
                      style={{ background: "none", border: "none", padding: 0, font: "inherit", color: "inherit", cursor: "pointer", fontWeight: 600, fontSize: 10, letterSpacing: ".08em", textTransform: "uppercase", fontVariantNumeric: "tabular-nums" }}
                    >
                      {c}{arrow(c)}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {view.map((i, rank) => (
                <tr key={i}>
                  <td style={{ ...cellStyle, color: "var(--color-ash-gray)" }}>{rank + 1}</td>
                  {cols.label && (
                    <td style={{ ...cellStyle, textAlign: "left", position: "sticky", left: 0, background: "var(--color-pure-white)" }}>
                      {(() => {
                        const raw = pool[i][cols.label as string];
                        const text = String(raw ?? "");
                        if (nameCol && text && onPlayerSelect) {
                          return (
                            <button
                              type="button"
                              onClick={() => onPlayerSelect(text)}
                              title={`Open ${text}`}
                              style={{ background: "none", border: "none", padding: 0, font: "inherit", cursor: "pointer", color: "var(--color-cyan-edge)", fontWeight: 500, textDecoration: "underline", textUnderlineOffset: 2, textAlign: "left" }}
                            >
                              {text}
                            </button>
                          );
                        }
                        return <span style={{ fontWeight: 500 }}>{text}</span>;
                      })()}
                    </td>
                  )}
                  {cols.rest.map((c) => {
                    const v = toNum(pool[i][c]);
                    const p = pcts.get(`${i}:${c}`);
                    return (
                      <td key={c} style={cellStyle}>
                        {v === null ? String(pool[i][c] ?? "") : fmtVal(c, v)}
                        {p !== undefined && (
                          <sub style={{ marginLeft: 3, fontSize: 9, color: "var(--color-ash-gray)", fontVariantNumeric: "tabular-nums" }}>
                            {p}
                          </sub>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div style={{ marginTop: 8, fontSize: 12, color: "var(--color-ash-gray)" }}>
        {note}
      </div>
    </section>
  );
}
