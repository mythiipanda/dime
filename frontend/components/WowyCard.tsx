"use client";

import { useMemo, useState } from "react";
import DataTable from "./DataTable";

export interface WowySplit {
  split: string;
  minutes?: number;
  possessions?: number;
  off_rating?: number;
  def_rating?: number;
  net_rating?: number;
}

interface WowyCardProps {
  rows: unknown;
  verdict?: string;
}

export default function WowyCard({ rows, verdict }: WowyCardProps) {
  const [view, setView] = useState<"visual" | "table">("visual");

  const splits = useMemo<WowySplit[]>(() => {
    if (Array.isArray(rows)) return rows as WowySplit[];
    if (typeof rows === "object" && rows !== null && "rows" in rows) {
      const inner = (rows as { rows?: unknown }).rows;
      if (Array.isArray(inner)) return inner as WowySplit[];
    }
    return [];
  }, [rows]);

  if (!splits.length) return null;

  const maxNet = Math.max(10, ...splits.map((s) => Math.abs(s.net_rating ?? 0)));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {verdict && (
        <div
          style={{
            fontSize: 13,
            fontWeight: 500,
            color: "var(--ink)",
            background: "var(--page)",
            padding: "8px 14px",
            borderRadius: 8,
            border: "1px solid var(--line)",
          }}
        >
          {verdict}
        </div>
      )}


      <div style={{ display: "flex", justifyContent: "flex-end", gap: 6 }}>
        <button
          className={view === "visual" ? "inline-flex items-center justify-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] transition-colors bg-surface text-ink shadow-hairline" : "inline-flex items-center justify-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] transition-colors bg-field text-ink-2 hover:bg-hover"}
          style={{ fontSize: 11, padding: "2px 10px" }}
          onClick={() => setView("visual")}
        >
          Visual
        </button>
        <button
          className={view === "table" ? "inline-flex items-center justify-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] transition-colors bg-surface text-ink shadow-hairline" : "inline-flex items-center justify-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] transition-colors bg-field text-ink-2 hover:bg-hover"}
          style={{ fontSize: 11, padding: "2px 10px" }}
          onClick={() => setView("table")}
        >
          Table
        </button>
      </div>

      {view === "table" ? (
        <DataTable rows={splits} />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {splits.map((s, idx) => {
            const net = s.net_rating ?? 0;
            const isPos = net >= 0;
            const barWidth = Math.min(100, (Math.abs(net) / maxNet) * 100);
            const isBothOn = s.split.toLowerCase().includes("both on");

            return (
              <div
                key={idx}
                style={{
                  background: isBothOn ? "var(--page)" : "var(--surface)",
                  border: "1px solid var(--line)",
                  borderRadius: 10,
                  padding: "12px 16px",
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        background: isBothOn ? "var(--accent)" : "var(--ink-2)",
                      }}
                    />
                    <span style={{ fontWeight: 600, fontSize: 13, color: "var(--ink)" }}>
                      {s.split}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--ink-2)" }}>
                    {s.minutes?.toFixed(0)} min · {s.possessions?.toFixed(0)} poss
                  </div>
                </div>


                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span style={{ width: 60, fontSize: 12, fontWeight: 600, color: isPos ? "var(--accent-ink)" : "var(--ink)", fontVariantNumeric: "tabular-nums" }}>
                    {isPos ? "+" : ""}{net.toFixed(1)} NET
                  </span>
                  <div style={{ flex: 1, height: 6, background: "var(--line)", borderRadius: 3, overflow: "hidden", display: "flex" }}>
                    <div
                      style={{
                        width: `${barWidth}%`,
                        height: "100%",
                        background: isPos ? "var(--accent)" : "var(--ink-2)",
                        borderRadius: 3,
                        transition: "width 300ms cubic-bezier(0.16, 1, 0.3, 1)",
                      }}
                    />
                  </div>
                  <div style={{ display: "flex", gap: 8, fontSize: 11, color: "var(--ink-3)" }}>
                    <span>OFF {s.off_rating?.toFixed(1)}</span>
                    <span>DEF {s.def_rating?.toFixed(1)}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
