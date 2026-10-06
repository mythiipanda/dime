"use client";

import { useMemo, useState } from "react";
import { propMarkets, propRows, type PropMarket, type PropRow } from "@/lib/dime-data-props";

type SortKey = "player" | "market" | "line" | "hits" | "edge";

function Chevron({ dir }: { dir: 1 | -1 }) {
  return (
    <svg width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" aria-hidden
      style={{ transform: dir === 1 ? "rotate(180deg)" : "none", transition: "transform 150ms cubic-bezier(0.16,1,0.3,1)" }}>
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

const columns: { key: SortKey; label: string; numeric: boolean }[] = [
  { key: "player", label: "Player", numeric: false },
  { key: "market", label: "Market", numeric: false },
  { key: "line", label: "Line", numeric: true },
  { key: "hits", label: "Last 10", numeric: true },
  { key: "edge", label: "Edge", numeric: true },
];

export default function PropsView() {
  const [market, setMarket] = useState<"All" | PropMarket>("All");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "edge", dir: -1 });

  const rows = useMemo(() => {
    const filtered = market === "All" ? propRows : propRows.filter((r) => r.market === market);
    const arr = [...filtered];
    arr.sort((a, b) => {
      if (sort.key === "edge") {
        if (a.edge === null && b.edge === null) return 0;
        if (a.edge === null) return 1;
        if (b.edge === null) return -1;
        return ((a.edge as number) - (b.edge as number)) * sort.dir;
      }
      const va = a[sort.key];
      const vb = b[sort.key];
      const cmp =
        typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb));
      return cmp * sort.dir;
    });
    return arr;
  }, [market, sort]);

  const toggle = (key: SortKey, numeric: boolean) =>
    setSort((s) =>
      s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: numeric ? -1 : 1 }
    );

  return (
    <section className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-[14px] border border-line bg-page">
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-line px-4">
        <h1 className="shrink-0 text-[13.5px] font-medium text-ink">Props</h1>
        <div className="flex max-w-full items-center gap-1 overflow-x-auto">
          {propMarkets.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMarket(m)}
              className={`touch-manipulation select-none rounded-full px-2.5 py-1 text-[12px] font-medium transition-[background-color,color,transform] duration-150 active:scale-[0.96] ${
                market === m ? "bg-hover-2 text-ink" : "text-ink-3 hover:bg-hover hover:text-ink-2"
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[600px] text-[13px]">
            <thead className="sticky top-0 z-10 bg-page">
              <tr className="border-b border-line">
                {columns.map((c) => (
                  <th key={c.key} className={`p-0 text-[13px] font-medium ${c.key === "player" ? "pl-4" : ""} ${c.key === "edge" ? "pr-4" : ""}`}>
                    <button
                      type="button"
                      onClick={() => toggle(c.key, c.numeric)}
                      className={`flex h-[32px] w-full touch-manipulation select-none items-center gap-1 transition-colors duration-100 hover:text-ink ${
                        c.numeric ? "justify-end tabular-nums" : "justify-start"
                      } ${sort.key === c.key ? "text-ink" : "text-ink-2"}`}
                    >
                      {c.label}
                      {sort.key === c.key && <Chevron dir={sort.dir} />}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.map((r: PropRow, i: number) => (
                <tr key={`${r.player}-${r.market}-${i}`} className="h-[35px] transition-colors duration-100 hover:bg-hover">
                  <td className="max-w-[240px] pl-4">
                    <div className="flex min-w-0 items-baseline">
                      <span className="min-w-0 truncate font-medium text-ink" title={r.player}>
                        {r.player}
                      </span>
                      <span className="ml-2 shrink-0 text-[12px] text-ink-3">{r.team}</span>
                    </div>
                  </td>
                  <td className="whitespace-nowrap text-ink-2">{r.market}</td>
                  <td className="whitespace-nowrap text-right font-mono tabular-nums text-ink">{r.line.toFixed(1)}</td>
                  <td className="whitespace-nowrap text-right font-mono tabular-nums text-ink-2">{r.hits}/10</td>
                  <td className="whitespace-nowrap pr-4 text-right font-mono tabular-nums">
                    {r.edge === null ? (
                      <span className="text-ink-3">—</span>
                    ) : (
                      <span className={r.edge > 0 ? "text-green" : "text-red"}>
                        {r.edge > 0 ? "+" : ""}
                        {r.edge.toFixed(1)}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="px-4 py-3 font-mono text-[11px] text-ink-3">
          {rows.length} {rows.length === 1 ? "prop" : "props"} · hit rate over last 10 games · edge where the model disagrees with the line
        </p>
      </div>
    </section>
  );
}
