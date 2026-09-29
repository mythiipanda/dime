"use client";

import { useEffect, useState } from "react";
import CopyLink from "./CopyLink";
import ExplorePanel, { PanelHeader } from "./ExplorePanel";
import Skeleton from "./Skeleton";
import { BACKEND } from "../lib/chat";
import { apiPath } from "../lib/api";

type PlayoffRow = {
  TEAM_ABBREVIATION?: string;
  WL?: string;
  MATCHUP?: string;
  GAME_ID?: string;
};

type Series = {
  round: string;
  a: string;
  b: string;
  winsA: number;
  winsB: number;
  games: number;
};

const ROUND_LABELS: Record<string, string> = {
  "01": "First round",
  "02": "Conference semifinals",
  "03": "Conference finals",
  "04": "Finals",
};

function deriveSeries(rows: PlayoffRow[]): Series[] {


  const bySeries = new Map<string, Series & { seen: Set<string> }>();
  for (const r of rows) {
    const team = (r.TEAM_ABBREVIATION || "").toUpperCase();
    const gid = String(r.GAME_ID || "");
    const matchup = String(r.MATCHUP || "");
    if (!team || gid.length < 8 || !matchup) continue;
    const round = gid.slice(6, 8);
    const parts = matchup.split(/\s(?:@|vs\.?)\s/i).map((s) => s.trim().toUpperCase());
    const other = parts.find((p) => p && p !== team) || "";
    if (!other) continue;
    const [a, b] = [team, other].sort();
    const key = `${round}|${a}|${b}`;
    let s = bySeries.get(key);
    if (!s) {
      s = { round, a, b, winsA: 0, winsB: 0, games: 0, seen: new Set() };
      bySeries.set(key, s);
    }
    if (s.seen.has(gid)) continue;
    s.seen.add(gid);
    s.games += 1;


    const winner = r.WL === "W" ? team : other;
    if (winner === a) s.winsA += 1;
    else s.winsB += 1;
  }
  const order = ["04", "03", "02", "01"];
  return [...bySeries.values()].sort(
    (x, y) => order.indexOf(x.round) - order.indexOf(y.round)
  );
}

export default function PlayoffPanel() {
  const [series, setSeries] = useState<Series[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    let live = true;
    fetch(`${BACKEND}${apiPath("/datasets/playoffs?season=2025-26")}`)
      .then((r) => r.json())
      .then((data) => {
        if (!live) return;
        if (!data.ok) throw new Error(String(data.error || "failed"));
        setSeries(deriveSeries((data.data || []) as PlayoffRow[]));
      })
      .catch((e) => live && setError(String(e)))
      .finally(() => live && setBusy(false));
    return () => { live = false; };
  }, []);

  const finals = series.find((s) => s.round === "04");
  const champion = finals
    ? finals.winsA > finals.winsB
      ? finals.a
      : finals.b
    : null;
  const byRound = (["04", "03", "02", "01"] as const)
    .map((rd) => ({ rd, list: series.filter((s) => s.round === rd) }))
    .filter((g) => g.list.length > 0);

  return (
    <ExplorePanel id="explore-playoffs">
      <PanelHeader kicker="Season" title="Playoffs 2025-26" action={<CopyLink panel="playoffs" />} />
      {busy && <Skeleton lines={4} label="Loading playoff series" />}
      {error && <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 8 }}>{error}</div>}
      {!busy && !error && champion && (
        <div style={{ fontSize: 14, color: "var(--color-ink-black)", marginTop: 8, fontWeight: 600 }}>
          Champion: {champion}
        </div>
      )}
      {!busy && !error && series.length === 0 && (
        <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 8 }}>
          No playoff games. Series results appear here once the postseason field is set.
        </div>
      )}
      {!busy && !error && byRound.map(({ rd, list }) => (
        <div key={rd} style={{ marginTop: 12 }}>
          <div style={{ fontSize: 12, color: "var(--color-warm-gray)", textTransform: "uppercase", letterSpacing: 0.6 }}>
            {ROUND_LABELS[rd] || `Round ${rd}`}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 6 }}>
            {list.map((s) => {
              const winner = s.winsA > s.winsB ? s.a : s.b;
              const loser = winner === s.a ? s.b : s.a;
              const wWins = winner === s.a ? s.winsA : s.winsB;
              const lWins = winner === s.a ? s.winsB : s.winsA;
              return (
                <div
                  key={`${s.round}-${s.a}-${s.b}`}
                  style={{
                    fontSize: 12,
                    border: "1px solid var(--color-stone-border)",
                    borderRadius: 8,
                    padding: "6px 10px",
                    color: "var(--color-ink-black)",
                    background: "var(--color-pure-white)",
                  }}
                >
                  <span style={{ fontWeight: 600 }}>{winner}</span>
                  {" def. "}
                  {loser}
                  {" "}
                  <span style={{ color: "var(--color-warm-gray)" }}>{wWins}-{lWins}</span>
                </div>
              );
            })}
          </div>
        </div>
      ))}
      <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 12 }}>
        {champion
          ? "Final results. Simulated odds return when the next season begins."
          : "Simulated odds live in chat: ask Simulate the playoffs."}
      </div>
    </ExplorePanel>
  );
}
