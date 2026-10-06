"use client";

import { useMemo, useState } from "react";
import { warehouseTables } from "@/lib/dime-data-warehouse";

function fmtRows(n: number) {
  return n.toLocaleString("en-US");
}

export default function WarehouseView() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(warehouseTables[0].name);

  const tables = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return warehouseTables;
    return warehouseTables.filter(
      (t) => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q)
    );
  }, [query]);

  const table = warehouseTables.find((t) => t.name === selected) ?? warehouseTables[0];

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
          {tables.length === 0 ? (
            <p className="px-4 py-6 text-[13px] text-ink-3">No tables match “{query.trim()}”.</p>
          ) : (
            <ul>
              {tables.map((t) => {
                const active = t.name === table.name;
                return (
                  <li key={t.name}>
                    <button
                      type="button"
                      onClick={() => setSelected(t.name)}
                      className={`flex w-full touch-manipulation select-none flex-col gap-0.5 px-4 py-2.5 text-left transition-colors duration-100 ${
                        active ? "bg-hover-2" : "hover:bg-hover"
                      }`}
                    >
                      <span className="truncate font-mono text-[12.5px] text-ink" title={t.name}>
                        {t.name}
                      </span>
                      <span className="whitespace-nowrap font-mono text-[11px] tabular-nums text-ink-3">
                        {fmtRows(t.rows)} rows · {t.freshness}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="min-w-0 flex-1 overflow-y-auto px-5 py-4">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h2 className="break-all font-mono text-[13.5px] font-medium text-ink">{table.name}</h2>
            <p className="shrink-0 font-mono text-[11px] tabular-nums text-ink-3">
              {fmtRows(table.rows)} rows · updated {table.freshness}
            </p>
          </div>
          <p className="mt-1 text-[13px] text-ink-2">{table.description}</p>

          <h3 className="mb-1 mt-5 text-[12px] font-medium text-ink-3">Schema</h3>
          <table className="w-full text-[13px]">
            <thead className="sticky top-0 z-10 bg-page">
              <tr className="border-b border-line">
                <th className="h-[32px] text-left text-[13px] font-medium text-ink-2">Column</th>
                <th className="h-[32px] text-left text-[13px] font-medium text-ink-2">Type</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {table.columns.map((c) => (
                <tr key={c.name} className="h-[32px]">
                  <td className="break-all font-mono text-[12.5px] text-ink">{c.name}</td>
                  <td className="font-mono text-[12.5px] text-ink-3">{c.type}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3 className="mb-1 mt-5 text-[12px] font-medium text-ink-3">Sample rows</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="sticky top-0 z-10 bg-page">
                <tr className="border-b border-line">
                  {table.columns.map((c) => (
                    <th key={c.name} className="h-[32px] whitespace-nowrap pr-4 text-left font-mono text-[12px] font-medium text-ink-2">
                      {c.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {table.sample.map((row, i) => (
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
        </div>
      </div>
    </section>
  );
}
