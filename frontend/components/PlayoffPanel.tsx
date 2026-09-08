"use client";

import { useEffect, useState } from "react";
import { BACKEND } from "../lib/chat";

type PlayoffRow = { TEAM_ABBREVIATION?: string; WL?: string };
type TeamWL = { team: string; w: number; l: number };

function derive(rows: PlayoffRow[]): { champion: TeamWL | null; table: TeamWL[] } {
  const m = new Map<string, TeamWL>();
  for (const r of rows) {
    const team = (r.TEAM_ABBREVIATION || "").toUpperCase();
    if (!team) continue;
    const cur = m.get(team) || { team, w: 0, l: 0 };
    if (r.WL === "W") cur.w += 1;
    else cur.l += 1;
    m.set(team, cur);
  }
  const table = [...m.values()].sort((a, b) => b.w - a.w || a.l - b.l);
  return { champion: table[0] || null, table };
}

export default function PlayoffPanel() {
  const [table, setTable] = useState<TeamWL[]>([]);
  const [champion, setChampion] = useState<TeamWL | null>(null);
  const [count, setCount] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    let live = true;
    fetch(`${BACKEND}/api/v1/datasets/playoffs?season=2025-26`)
      .then((r) => r.json())
      .then((data) => {
        if (!live) return;
        if (!data.ok) throw new Error(String(data.error || "failed"));
        const rows = (data.data || []) as PlayoffRow[];
        const d = derive(rows);
        setTable(d.table);
        setChampion(d.champion);
        setCount(rows.length);
      })
      .catch((e) => live && setError(String(e)))
      .finally(() => live && setBusy(false));
    return () => { live = false; };
  }, []);

  return (
    <div className="card">
      <div className="display" style={{ fontSize: 20 }}>Playoffs 2025-26</div>
      {busy && <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 8 }}>Loading</div>}
      {error && <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 8 }}>{error}</div>}
      {!busy && !error && champion && (
        <div style={{ fontSize: 14, color: "var(--color-ink-black)", marginTop: 8 }}>
          Champion {champion.team} ({champion.w}-{champion.l}, {count} rows)
        </div>
      )}
      {!busy && !error && (
        <table style={{ marginTop: 12, fontSize: 12, borderCollapse: "collapse", width: "100%" }}>
          <thead>
            <tr style={{ color: "var(--color-warm-gray)", textAlign: "left" }}>
              <th style={{ padding: "4px 8px 4px 0" }}>Team</th>
              <th style={{ padding: "4px 8px" }}>W</th>
              <th style={{ padding: "4px 8px" }}>L</th>
            </tr>
          </thead>
          <tbody>
            {table.map((t) => (
              <tr key={t.team} style={{ borderTop: "1px solid var(--color-stone-border)" }}>
                <td style={{ padding: "4px 8px 4px 0", color: "var(--color-ink-black)" }}>{t.team}</td>
                <td style={{ padding: "4px 8px" }}>{t.w}</td>
                <td style={{ padding: "4px 8px" }}>{t.l}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 12 }}>
        Simulated odds live in chat: ask Simulate the playoffs.
      </div>
    </div>
  );
}
