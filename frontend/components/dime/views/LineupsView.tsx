"use client";

import { useMemo, useState } from "react";
import { lineups, lineupTeams, type Lineup } from "../../../lib/dime-data-lineups";

type SortKey = "lineup" | "min" | "ortg" | "drtg" | "net";

const netOf = (l: Lineup) => l.ortg - l.drtg;

function Chevron({ dir }: { dir: 1 | -1 }) {
  return (
    <svg width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" aria-hidden
      style={{ transform: dir === 1 ? "rotate(180deg)" : "none", transition: "transform 150ms cubic-bezier(0.16,1,0.3,1)" }}>
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

const COLS: { key: SortKey; label: string; numeric: boolean }[] = [
  { key: "lineup", label: "Lineup", numeric: false },
  { key: "min", label: "MIN", numeric: true },
  { key: "ortg", label: "ORtg", numeric: true },
  { key: "drtg", label: "DRtg", numeric: true },
  { key: "net", label: "Net", numeric: true },
];

function cellVal(l: Lineup, k: SortKey): number | string {
  switch (k) {
    case "lineup": return l.players[0];
    case "min": return l.min;
    case "ortg": return l.ortg;
    case "drtg": return l.drtg;
    case "net": return netOf(l);
  }
}

function ShotDist({ l }: { l: Lineup }) {
  const dist: [string, number][] = [
    ["Rim", l.shots.rim],
    ["Mid", l.shots.mid],
    ["3PT", l.shots.three],
  ];
  return (
    <div>
      <div className="flex gap-5">
        {dist.map(([label, pct]) => (
          <div key={label} className="flex-1">
            <div className="flex items-baseline justify-between">
              <span className="text-[11px] text-ink-3">{label}</span>
              <span className="font-mono text-[11px] tabular-nums text-ink-2">{pct}%</span>
            </div>
            <div className="mt-1 h-1 rounded-full bg-hover">
              <div className="h-full rounded-full bg-ink" style={{ width: `${pct}%` }} />
            </div>
          </div>
        ))}
      </div>
      <p className="mt-2.5 max-w-[560px] text-[12.5px] leading-[1.55] text-ink-2">{l.note}</p>
    </div>
  );
}

export default function LineupsView() {
  const [team, setTeam] = useState("All");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "net", dir: -1 });
  const [expanded, setExpanded] = useState<string | null>(null);

  const rows = useMemo(() => {
    const arr = lineups.filter((l) => team === "All" || l.team === team);
    arr.sort((a, b) => {
      const va = cellVal(a, sort.key);
      const vb = cellVal(b, sort.key);
      const cmp =
        typeof va === "number" && typeof vb === "number"
          ? va - vb
          : String(va).localeCompare(String(vb));
      return cmp * sort.dir;
    });
    return arr;
  }, [team, sort]);

  const toggle = (key: SortKey) =>
    setSort((s) => {
      if (s.key === key) return { key, dir: s.dir === 1 ? -1 : 1 };
      const numeric = COLS.find((c) => c.key === key)!.numeric;
      return { key, dir: numeric ? -1 : 1 };
    });

  const fmtNet = (v: number) => (v > 0 ? "+" : "") + v.toFixed(1);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-line px-4">
        <span className="text-[13px] font-semibold text-ink">Lineups</span>
        <span className="font-mono text-[11px] tabular-nums text-ink-3">
          {rows.length} of {lineups.length}
        </span>
      </div>

      <div className="flex shrink-0 flex-wrap gap-1.5 px-4 pt-3">
        {["All", ...lineupTeams].map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => { setTeam(t); setExpanded(null); }}
            className={`h-7 shrink-0 select-none rounded-[7px] px-3 text-[12px] font-medium transition-[background-color,color,transform] duration-150 active:scale-[0.96] ${
              team === t
                ? "bg-ink text-[var(--surface)]"
                : "bg-surface text-ink-2 shadow-btn hover:bg-hover hover:text-ink"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="mt-3 min-h-0 flex-1 overflow-y-auto px-4 pb-8">
        <div className="overflow-x-auto rounded-card bg-surface shadow-hairline">
          <table className="w-full min-w-[620px] text-[13px]">
            <thead className="sticky top-0 z-10 bg-surface">
              <tr className="border-b border-line">
                {COLS.map((c, i) => (
                  <th key={c.key} className={`p-0 text-[13px] font-medium ${i === 0 ? "pl-4" : ""} ${i === COLS.length - 1 ? "pr-4" : ""}`}>
                    <button
                      type="button"
                      onClick={() => toggle(c.key)}
                      className={`flex h-[32px] w-full select-none items-center gap-1 transition-colors duration-100 hover:text-ink ${
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
              {rows.map((l) => {
                const n = netOf(l);
                const open = expanded === l.id;
                return [
                  <tr
                    key={l.id}
                    tabIndex={0}
                    aria-expanded={open}
                    onClick={() => setExpanded(open ? null : l.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setExpanded(open ? null : l.id);
                      }
                    }}
                    className="h-[35px] cursor-pointer transition-colors duration-100 hover:bg-hover focus-visible:outline-none focus-visible:bg-hover"
                  >
                    <td className="max-w-[300px] pl-4">
                      <div className="flex min-w-0 items-baseline gap-2">
                        <span className="shrink-0 font-mono text-[11px] text-ink-3">{l.team}</span>
                        <span className="min-w-0 flex-1 truncate text-ink" title={l.players.join(", ")}>
                          {l.players.join(" · ")}
                        </span>
                      </div>
                    </td>
                    <td className="text-right font-mono tabular-nums text-ink-2">{l.min.toFixed(1)}</td>
                    <td className="text-right font-mono tabular-nums text-ink-2">{l.ortg.toFixed(1)}</td>
                    <td className="text-right font-mono tabular-nums text-ink-2">{l.drtg.toFixed(1)}</td>
                    <td className={`pr-4 text-right font-mono tabular-nums font-medium ${n >= 0 ? "text-green" : "text-red"}`}>
                      {fmtNet(n)}
                    </td>
                  </tr>,
                  open && (
                    <tr key={`${l.id}-x`} className="border-b border-line bg-page">
                      <td colSpan={COLS.length} className="px-4 py-3.5">
                        <div style={{ animation: "fade-up 180ms cubic-bezier(0.23,1,0.32,1) both" }}>
                          <ShotDist l={l} />
                        </div>
                      </td>
                    </tr>
                  ),
                ];
              })}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={COLS.length} className="px-4 py-8 text-center font-mono text-[12px] text-ink-3">
                    No lineups match this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <p className="mt-2 px-1 font-mono text-[11px] text-ink-3">Ratings per 100 possessions. Click a row for shot mix.</p>
      </div>
    </div>
  );
}
