"use client";

import { useEffect, useState } from "react";
import { GameRow, TodayMover, TeamStreak, TodayRows, getToday } from "../lib/api";
import EmptyState from "./EmptyState";
import Skeleton from "./Skeleton";

function GameChip({ g }: { g: GameRow }) {
  return (
    <div
      style={{
        flexShrink: 0,
        border: "1px solid var(--color-stone-border)",
        borderRadius: 10,
        padding: "6px 12px",
        background: "var(--color-pure-white)",
        fontSize: 12,
      }}
    >
      <span style={{ fontWeight: 500 }}>{g.VISITOR_TEAM_ABBREVIATION || "AWAY"}</span>{" "}
      {g.VISITOR_TEAM_PTS ?? "-"}
      {"  "}
      <span style={{ fontWeight: 500 }}>{g.HOME_TEAM_ABBREVIATION || "HOME"}</span>{" "}
      {g.HOME_TEAM_PTS ?? "-"}
      <div style={{ fontSize: 10, color: "var(--color-ash-gray)" }}>
        {g.GAME_STATUS_TEXT || "Scheduled"}
      </div>
    </div>
  );
}

function GameRowList({ games, emptyTitle, emptyDescription }: { games: GameRow[]; emptyTitle: string; emptyDescription: string }) {
  if (!games.length) {
    return (
      <EmptyState title={emptyTitle} description={emptyDescription} />
    );
  }
  return (
    <div style={{ display: "flex", gap: 8, overflowX: "auto", padding: "4px 0" }}>
      {games.map((g, i) => (
        <GameChip key={i} g={g} />
      ))}
    </div>
  );
}

function MoverRow({ m }: { m: TodayMover }) {
  if (m.note) {
    return (
      <div style={{ fontSize: 13, color: "var(--color-warm-gray)", padding: "6px 0" }}>
        {m.note}
      </div>
    );
  }
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "6px 0",
        borderTop: "1px solid var(--color-stone-border)",
        fontSize: 13,
      }}
    >
      <span
        style={{
          fontSize: 11,
          fontWeight: 600,
          minWidth: 36,
          color: "var(--color-cyan-edge)",
        }}
      >
        {m.RANK_CHANGE}
      </span>
      <span style={{ flex: 1, fontWeight: 500, color: "var(--color-ink-black)" }}>
        {m.PLAYER || "Unknown"}
      </span>
      <span style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>{m.TEAM}</span>
      <span style={{ fontSize: 12, color: "var(--color-warm-gray)", minWidth: 56, textAlign: "right" }}>
        {typeof m.PTS_CHANGE === "number"
          ? `${m.PTS_CHANGE > 0 ? "+" : ""}${m.PTS_CHANGE.toFixed(1)} pts`
          : ""}
      </span>
    </div>
  );
}

function StreakRow({ s }: { s: TeamStreak }) {
  const winning = (s.STREAK || "").toUpperCase().startsWith("W");
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "6px 0",
        borderTop: "1px solid var(--color-stone-border)",
        fontSize: 13,
      }}
    >
      <span
        style={{
          fontSize: 11,
          fontWeight: 600,
          padding: "2px 8px",
          borderRadius: 9999,
          background: winning ? "var(--color-sky-wash)" : "transparent",
          color: winning ? "var(--color-cyan-edge)" : "var(--color-warm-gray)",
          border: winning ? "none" : "1px solid var(--color-stone-border)",
        }}
      >
        {s.STREAK || `${s.GAMES} streak`}
      </span>
      <span style={{ flex: 1, fontWeight: 500 }}>{s.TEAM}</span>
      <span style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>
        {s.W ?? "-"}-{s.L ?? "-"}
      </span>
    </div>
  );
}

export default function TodayPanel() {
  const [rows, setRows] = useState<TodayRows | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let live = true;
    getToday()
      .then((r) => {
        if (live) setRows(r);
      })
      .catch(() => {
        if (live) setErr("Today is unavailable right now.");
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="card">
        <Skeleton lines={3} label="Loading today..." />
      </div>
    );
  }

  if (err || !rows) {
    return (
      <div className="card">
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Today</div>
        <EmptyState
          title="Today is unavailable"
          description={err || "We couldn't load today's slate. Try again in a bit."}
        />
      </div>
    );
  }

  const noGames =
    !(rows.last_night || []).length && !(rows.tonight || []).length;

  return (
    <div className="card">
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Today</div>

      {noGames ? (
        <EmptyState
          title="No games today"
          description="It's the offseason. Check back in October, or explore season leaders below."
        />
      ) : (
        <>
          <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 4 }}>
            Last night
          </div>
          <GameRowList
            games={rows.last_night || []}
            emptyTitle="No games last night"
            emptyDescription="Nothing on the slate last night."
          />

          <div style={{ fontSize: 12, color: "var(--color-warm-gray)", margin: "12px 0 4px" }}>
            Tonight
          </div>
          <GameRowList
            games={rows.tonight || []}
            emptyTitle="No games scheduled tonight"
            emptyDescription="Check back tomorrow, or explore season leaders below."
          />
        </>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: 16,
          marginTop: 16,
        }}
      >
        <div>
          <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 4 }}>
            Leaderboard movers (7d)
          </div>
          {(rows.movers || []).length ? (
            rows.movers.slice(0, 6).map((m, i) => (
              <MoverRow key={m.PLAYER || i} m={m} />
            ))
          ) : (
            <EmptyState
              title="Movers unavailable"
              description="Leaderboard movement hasn't loaded yet. Check back soon."
            />
          )}
        </div>
        <div>
          <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 4 }}>
            Team streaks (3+ games)
          </div>
          {(rows.streaks || []).length ? (
            rows.streaks.map((s, i) => <StreakRow key={s.TEAM || i} s={s} />)
          ) : (
            <EmptyState
              title="No active 3+ game streaks"
              description="No team is on a run right now. Check back after the next slate."
            />
          )}
        </div>
      </div>
    </div>
  );
}
