"use client";

import { useEffect, useMemo, useState } from "react";
import { getDatasetJson, getFreshness, getRevision, type FreshRow } from "@/lib/api";
import { BACKEND } from "@/lib/chat";

const LOGICAL_DATASETS = new Set([
  "standings", "leaders", "injuries", "player_gamelogs", "team_games",
  "scoreboard", "shots", "lineups", "on_off", "wowy", "four_factors",
  "hustle", "combine", "ratings", "playoffs", "playoff_gamelogs",
  "draft", "raptor", "player_seasons",
]);

function fmtRows(n: number) {
  return n.toLocaleString("en-US");
}

function relTime(iso: string | null): string {
  if (!iso) return "unknown";
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return "unknown";
  const mins = Math.max(0, Math.round((Date.now() - ms) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function logicalName(table: string): string | null {
  const stripped = table.startsWith("silver_") ? table.slice("silver_".length) : table;
  if (LOGICAL_DATASETS.has(stripped)) return stripped;
  if (stripped.startsWith("leaders")) return "leaders";
  return null;
}

type Detail =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "ready"; columns: string[]; types: Record<string, string>; sample: string[][] }
  | { state: "unavailable"; reason: string };

function cellType(v: unknown): string {
  if (v === null || v === undefined) return "null";
  if (typeof v === "number") return Number.isInteger(v) ? "int" : "double";
  if (typeof v === "boolean") return "boolean";
  return "string";
}

function fmtCell(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export default function WarehouseView() {
  const [tables, setTables] = useState<FreshRow[]>([]);
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail>({ state: "idle" });
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getFreshness()
      .then((rows) => {
        if (cancelled) return;
        setTables(rows);
        setSelected((s) => s ?? rows[0]?.table ?? null);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    getRevision()
      .then((rev) => {
        if (cancelled) return;
        const r = rev as { revision?: string };
        const short = typeof r.revision === "string" ? r.revision.slice(0, 8) : "";
        fetch(`${BACKEND}/api/healthz`)
          .then((res) => res.json())
          .then((h) => {
            if (!cancelled) setStatus(h && h.ok ? `rev ${short} · healthy` : `rev ${short}`);
          })
          .catch(() => {
            if (!cancelled) setStatus(`rev ${short}`);
          });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selected) return;
    setDetail({ state: "loading" });
    const name = logicalName(selected);
    if (!name) {
      setDetail({ state: "unavailable", reason: "Detail is not exposed for this table yet." });
      return;
    }
    let cancelled = false;
    getDatasetJson(name, { season: "2025-26" })
      .then((res) => {
        if (cancelled) return;
        const rows = Array.isArray(res.data) ? (res.data as Record<string, unknown>[]) : [];
        if (!res.ok || rows.length === 0) {
          setDetail({
            state: "unavailable",
            reason: typeof res.error === "string" ? res.error : "No rows returned for this table.",
          });
          return;
        }
        const columns = Object.keys(rows[0]).filter((c) => !c.startsWith("_"));
        const types: Record<string, string> = {};
        for (const c of columns) types[c] = cellType(rows[0][c]);
        setDetail({
          state: "ready",
          columns,
          types,
          sample: rows.slice(0, 5).map((r) => columns.map((c) => fmtCell(r[c]))),
        });
      })
      .catch(() => {
        if (!cancelled) setDetail({ state: "unavailable", reason: "Could not load this table." });
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return tables;
    return tables.filter((t) => t.table.toLowerCase().includes(q));
  }, [query, tables]);

  const table = tables.find((t) => t.table === selected) ?? null;

  return (
    <section className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-[14px] border border-line bg-page">
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-line px-4">
        <h1 className="text-[13.5px] font-medium text-ink">Warehouse</h1>
        <div className="flex h-8 w-56 items-center gap-1.5 rounded-[8px] bg-field px-2 text-ink-3 shadow-hairline focus-within:text-ink-2">
          <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth={2} strokeLinecap="round" aria-hidden className="shrink-0">
            <circle cx="11" cy="11" r="7" />
            <path d="M20 20l-3.5-3.5" />
          </svg>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search tables"
            aria-label="Search tables"
            className="min-w-0 flex-1 bg-transparent text-[13px] text-ink outline-none placeholder:text-ink-3 [@media(pointer:coarse)]:text-[16px]"
          />
          {query && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => setQuery("")}
              className="flex size-6 shrink-0 touch-manipulation select-none items-center justify-center rounded-[6px] text-ink-3 transition-colors duration-100 hover:bg-hover hover:text-ink"
            >
              <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor"
                strokeWidth={2} strokeLinecap="round" aria-hidden>
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          )}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col sm:flex-row">
        <div className="max-h-[38dvh] w-full shrink-0 overflow-y-auto overscroll-contain border-b border-line sm:max-h-none sm:w-64 sm:border-b-0 sm:border-r">
          {failed ? (
            <p className="px-4 py-6 text-[13px] text-ink-3">Could not reach the warehouse.</p>
          ) : filtered.length === 0 ? (
            <p className="px-4 py-6 text-[13px] text-ink-3">
              {tables.length === 0 ? "Loading tables…" : `No tables match “${query.trim()}”.`}
            </p>
          ) : (
            <ul>
              {filtered.map((t) => {
                const active = t.table === table?.table;
                return (
                  <li key={t.table}>
                    <button
                      type="button"
                      onClick={() => setSelected(t.table)}
                      className={`flex w-full touch-manipulation select-none flex-col gap-0.5 px-4 py-2.5 text-left transition-colors duration-100 ${
                        active ? "bg-hover-2" : "hover:bg-hover"
                      }`}
                    >
                      <span className="truncate font-mono text-[12.5px] text-ink" title={t.table}>
                        {t.table}
                      </span>
                      <span className="whitespace-nowrap font-mono text-[11px] tabular-nums text-ink-3">
                        {fmtRows(t.rows)} rows · {relTime(t.last_fetch)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="min-w-0 flex-1 overflow-y-auto px-5 py-4">
          {!table ? (
            <p className="py-10 text-center text-[13px] text-ink-3">Select a table.</p>
          ) : (
            <>
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <h2 className="break-all font-mono text-[13.5px] font-medium text-ink">{table.table}</h2>
                <p className="shrink-0 font-mono text-[11px] tabular-nums text-ink-3">
                  {fmtRows(table.rows)} rows · updated {relTime(table.last_fetch)}
                </p>
              </div>
              {table.data_through && (
                <p className="mt-1 text-[13px] text-ink-2">Data through {table.data_through}.</p>
              )}

              {detail.state === "loading" && (
                <p className="mt-5 text-[13px] text-ink-3">Loading schema…</p>
              )}
              {detail.state === "unavailable" && (
                <p className="mt-5 text-[13px] text-ink-3">{detail.reason}</p>
              )}
              {detail.state === "ready" && (
                <>
                  <h3 className="mb-1 mt-5 text-[12px] font-medium text-ink-3">Schema</h3>
                  <table className="w-full text-[13px]">
                    <thead className="sticky top-0 z-10 bg-page">
                      <tr className="border-b border-line">
                        <th className="h-[32px] text-left text-[13px] font-medium text-ink-2">Column</th>
                        <th className="h-[32px] text-left text-[13px] font-medium text-ink-2">Type</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {detail.columns.map((c) => (
                        <tr key={c} className="h-[32px]">
                          <td className="break-all font-mono text-[12.5px] text-ink">{c}</td>
                          <td className="font-mono text-[12.5px] text-ink-3">{detail.types[c]}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  <h3 className="mb-1 mt-5 text-[12px] font-medium text-ink-3">Sample rows</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-[13px]">
                      <thead className="sticky top-0 z-10 bg-page">
                        <tr className="border-b border-line">
                          {detail.columns.map((c) => (
                            <th key={c} className="h-[32px] whitespace-nowrap pr-4 text-left font-mono text-[12px] font-medium text-ink-2">
                              {c}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-line">
                        {detail.sample.map((row, i) => (
                          <tr key={i} className="h-[32px] transition-colors duration-100 hover:bg-hover">
                            {row.map((v, j) => (
                              <td key={j} className="whitespace-nowrap pr-4 font-mono text-[12.5px] tabular-nums text-ink-2">
                                {v}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}

              {status && (
                <p className="mt-6 font-mono text-[11px] text-ink-3">Backend {status}</p>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
