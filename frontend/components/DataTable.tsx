"use client";

import { useEffect, useMemo, useState } from "react";
import { getQueryParam, setQueryParam } from "../lib/api";

interface Props {
  rows: unknown;
  capCols?: number;
  capRows?: number;
  heat?: boolean;
  storeKey?: string;
}

function asTable(rows: unknown, capCols: number): {
  cols: string[];
  body: string[][];
  nums: (number | null)[][];
  maxs: (number | null)[];
  subs: Record<string, string>[];
  numeric: boolean[];
} | null {
  let list = rows;
  if (!Array.isArray(list) && typeof list === "object" && list !== null) {
    const first = Object.values(list as Record<string, unknown>).find((v) =>
      Array.isArray(v),
    );
    if (!first) return null;
    list = first;
  }
  if (!Array.isArray(list) || !list.length) return null;
  const first = (list as unknown[])[0] as Record<string, unknown>;
  if (typeof first !== "object" || first === null) return null;
  const cols = Object.keys(first).slice(0, Math.max(1, Math.min(12, capCols)));
  const recs = (list as Record<string, unknown>[]).slice(0, 500);
  const body = recs.map((r) =>
    cols.map((c) => {
      const v = r[c];
      if (v === null || v === undefined) return "";
      if (typeof v === "object") return JSON.stringify(v).slice(0, 60);
      return String(v).slice(0, 60);
    }),
  );
  const subs = recs.map((r) => {
    const out: Record<string, string> = {};
    if (typeof r.PLAYER === "string") {
      const bits = [];
      if (typeof r.TEAM === "string") bits.push(r.TEAM);
      if (typeof r.RANK === "number") bits.push(`#${r.RANK}`);
      if (bits.length) out.PLAYER = bits.join(" · ");
    }
    return out;
  });
  const nums = recs.map((r) =>
    cols.map((c) => {
      const v = r[c];
      return typeof v === "number" ? v : null;
    }),
  );
  const maxs = cols.map((_, j) => {
    const vals = nums.map((row) => row[j]).filter((v) => v !== null) as number[];
    if (!vals.length) return null;
    const m = Math.max(...vals.map((v) => Math.abs(v)));
    return m > 0 ? m : null;
  });
  const numeric = cols.map((_, j) => nums.some((row) => row[j] !== null));
  return { cols, body, nums, maxs, subs, numeric };
}

export default function DataTable({ rows, capCols = 8, capRows = 25, heat = false, storeKey }: Props) {
  const safeCapRows = Math.max(5, Math.min(100, capRows));
  const t = useMemo(() => asTable(rows, capCols), [rows, capCols]);
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<1 | -1>(1);
  const [filter, setFilter] = useState("");
  const [pct, setPct] = useState(false);
  useEffect(() => {
    if (!storeKey) return;
    const s = getQueryParam(`${storeKey}_sort`);
    if (s) {
      const i = s.lastIndexOf(":");
      setSortCol(i > 0 ? s.slice(0, i) : s);
      setSortDir(s.endsWith(":desc") ? -1 : 1);
    }
    const q = getQueryParam(`${storeKey}_q`);
    if (q) setFilter(q);
    if (getQueryParam(`${storeKey}_pct`) === "1") setPct(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storeKey]);
  const view = useMemo(() => {
    if (!t) return null;
    const q = filter.trim().toLowerCase();
    let idx = t.body.map((_, i) => i);
    if (q) {
      idx = idx.filter((i) =>
        t.body[i].some((cell) => cell.toLowerCase().includes(q)),
      );
    }
    if (sortCol) {
      const j = t.cols.indexOf(sortCol);
      if (j >= 0) {
        idx = [...idx].sort((a, b) => {
          const na = t.nums[a][j];
          const nb = t.nums[b][j];
          if (na !== null && nb !== null) return (na - nb) * sortDir;
          return t.body[a][j].localeCompare(t.body[b][j]) * sortDir;
        });
      }
    }
    return { idx, total: t.body.length };
  }, [t, filter, sortCol, sortDir]);
  const shown = useMemo(() => (view ? view.idx.slice(0, safeCapRows) : []), [view, safeCapRows]);
  const ranks = useMemo(() => {
    if (!t || !pct || shown.length < 2) return null;
    const m = new Map<string, number>();
    t.cols.forEach((_, j) => {
      const vals = shown.map((ri) => t.nums[ri][j]);
      if (vals.some((v) => v === null)) return;
      const sorted = [...(vals as number[])].sort((a, b) => a - b);
      shown.forEach((ri) => {
        const below = sorted.filter((x) => x < (t.nums[ri][j] as number)).length;
        m.set(`${ri}:${j}`, below / (sorted.length - 1));
      });
    });
    return m;
  }, [t, shown, pct]);
  if (!t || !view) return null;
  if (!t.body.length) return <div style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>No rows.</div>;
  const downloadCsv = () => {
    const esc = (v: string) =>
      /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
    const lines = [
      t.cols.map(esc).join(","),
      ...view.idx.map((i) => t.body[i].map(esc).join(",")),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "dime-table.csv";
    document.body.append(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };
  const toggleSort = (c: string) => {
    let col: string | null = c;
    let dir: 1 | -1 = 1;
    if (sortCol === c && sortDir === 1) dir = -1;
    else if (sortCol === c) col = null;
    setSortCol(col);
    setSortDir(dir);
    if (storeKey) {
      setQueryParam(`${storeKey}_sort`, col ? `${col}:${dir === 1 ? "asc" : "desc"}` : "", true);
    }
  };
  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}>
        <input
          className="field"
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            if (storeKey) setQueryParam(`${storeKey}_q`, e.target.value);
          }}
          placeholder="Filter rows..."
          style={{ fontSize: 12, width: 160 }}
          aria-label="Filter rows"
        />
        <span style={{ fontSize: 11, color: "var(--color-ash-gray)" }}>
          Showing {shown.length} of {view.idx.length}
          {view.idx.length !== view.total ? ` (filtered from ${view.total})` : ""}
          {view.total === 500 ? " (first 500)" : ""}
        </span>
        <button
          className={pct ? "tab-active" : "pill-ghost"}
          style={{ fontSize: 11, padding: "2px 10px" }}
          onClick={() => {
            const next = !pct;
            setPct(next);
            if (storeKey) setQueryParam(`${storeKey}_pct`, next ? "1" : "", true);
          }}
          title="Show percentile rank within each numeric column"
        >
          Pct
        </button>
        <button
          className="pill-ghost"
          style={{ fontSize: 11, padding: "2px 10px", marginLeft: "auto" }}
          onClick={downloadCsv}
        >
          CSV
        </button>
      </div>
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 12 }}>
        <thead>
          <tr>
            {t.cols.map((c) => (
              <th
                key={c}
                onClick={() => toggleSort(c)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    toggleSort(c);
                  }
                }}
                tabIndex={0}
                aria-sort={sortCol === c ? (sortDir === 1 ? "ascending" : "descending") : "none"}
                title={`Sort by ${c}`}
                style={{
                  textAlign: t.numeric[t.cols.indexOf(c)] ? "right" : "left",
                  borderBottom: "1px solid var(--color-stone-border)",
                  padding: "4px 8px",
                  color: "var(--color-warm-gray)",
                  fontWeight: 500,
                  cursor: "pointer",
                  userSelect: "none",
                  whiteSpace: "nowrap",
                }}
              >
                {c}
                {sortCol === c ? (sortDir === 1 ? " ▲" : " ▼") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((ri) => (
            <tr key={ri}>
              {t.body[ri].map((cell, j) => {
                const v = t.nums[ri][j];
                const m = t.maxs[j];
                const bg =
                  heat && v !== null && m !== null
                    ? `rgba(59, 166, 241, ${(0.04 + 0.22 * (Math.abs(v) / m)).toFixed(3)})`
                    : undefined;
                return (
                  <td
                    key={j}
                    style={{
                      borderBottom: "1px solid var(--color-stone-border)",
                      padding: "4px 8px",
                      background: bg,
                      textAlign: t.numeric[j] ? "right" : "left",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {cell}
                    {t.subs[ri][t.cols[j]] && (
                      <div style={{ fontSize: 10, color: "var(--color-ash-gray)" }}>
                        {t.subs[ri][t.cols[j]]}
                      </div>
                    )}
                    {ranks !== null &&
                      (() => {
                        const r = ranks.get(`${ri}:${j}`);
                        if (r === undefined) return null;
                        return (
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 4,
                              marginTop: 2,
                              justifyContent: t.numeric[j] ? "flex-end" : "flex-start",
                            }}
                          >
                            <span
                              style={{
                                width: 24,
                                height: 3,
                                background: "var(--color-stone-border)",
                                borderRadius: 2,
                                overflow: "hidden",
                              }}
                            >
                              <span
                                style={{
                                  display: "block",
                                  width: `${Math.round(r * 100)}%`,
                                  height: "100%",
                                  background: "var(--color-cyan-signal)",
                                }}
                              />
                            </span>
                            <span style={{ fontSize: 9, color: "var(--color-ash-gray)" }}>
                              p{Math.round(r * 100)}
                            </span>
                          </div>
                        );
                      })()}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    </div>
  );
}
