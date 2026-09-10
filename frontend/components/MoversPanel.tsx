"use client";

import { useEffect, useState } from "react";
import { Mover, MoversRows, NewEntry, getMovers } from "../lib/api";
import EmptyState from "./EmptyState";

const DAYS = [7, 14, 30];

function MoverRow({ m }: { m: Mover }) {
  const up = (m.rank_change || 0) > 0;
  const pts = m.pts_change || 0;
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
          minWidth: 44,
          color: "var(--color-cyan-edge)",
        }}
      >
        {up ? `+${m.rank_change}` : m.rank_change}
      </span>
      <span style={{ flex: 1, fontWeight: 500, color: "var(--color-ink-black)" }}>
        {m.player || "Unknown"}
      </span>
      <span style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>{m.team}</span>
      <span style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>
        {m.rank_base} → {m.rank_now}
      </span>
      <span style={{ fontSize: 12, color: "var(--color-warm-gray)", minWidth: 56, textAlign: "right" }}>
        {pts > 0 ? `+${pts.toFixed(1)}` : pts.toFixed(1)} pts
      </span>
    </div>
  );
}

function EntryRow({ e }: { e: NewEntry }) {
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
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          color: "var(--color-cyan-edge)",
          background: "var(--color-sky-wash)",
          borderRadius: 9999,
          padding: "2px 8px",
          flexShrink: 0,
        }}
      >
        New
      </span>
      <span style={{ flex: 1, fontWeight: 500, color: "var(--color-ink-black)" }}>
        {e.player || "Unknown"}
      </span>
      <span style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>{e.team}</span>
      <span style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>#{e.rank}</span>
    </div>
  );
}

function Column({
  title,
  empty,
  children,
  count,
}: {
  title: string;
  empty: string;
  children: React.ReactNode;
  count: number;
}) {
  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 4 }}>
        {title}
      </div>
      {!count ? (
        <EmptyState icon="📈" title={empty} description="Check back after the next slate of games." />
      ) : (
        children
      )}
    </div>
  );
}

export default function MoversPanel() {
  const [days, setDays] = useState(7);
  const [rows, setRows] = useState<MoversRows | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let live = true;
    setLoading(true);
    getMovers("2025-26", days)
      .then((r) => {
        if (live) {
          setRows(r);
          setErr("");
        }
      })
      .catch(() => {
        if (live) setErr("Movers are unavailable right now.");
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [days]);

  return (
    <div className="card">
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 12,
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 600 }}>Leaderboard movers</div>
        <div style={{ display: "inline-flex", gap: 4 }} role="group" aria-label="Days">
          {DAYS.map((d) => (
            <button
              key={d}
              type="button"
              className={days === d ? "tab-active" : "pill-ghost"}
              aria-pressed={days === d}
              style={{ fontSize: 12, padding: "3px 10px", cursor: "pointer" }}
              onClick={() => setDays(d)}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div>
          {[90, 70, 55].map((w, i) => (
            <div key={i} className="shimmer skeleton-row" style={{ width: `${w}%` }} />
          ))}
        </div>
      ) : err || !rows ? (
        <EmptyState
          icon="📈"
          title="No movers yet"
          description={err || "Rankings need another slate of games before movers appear."}
        />
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: 16,
          }}
        >
          <Column title="Climbers" empty="No climbers." count={rows.climbers.length}>
            {rows.climbers.map((m, i) => (
              <MoverRow key={m.player || i} m={m} />
            ))}
          </Column>
          <Column title="Fallers" empty="No fallers." count={rows.fallers.length}>
            {rows.fallers.map((m, i) => (
              <MoverRow key={m.player || i} m={m} />
            ))}
          </Column>
          <Column title="New entries" empty="No new entries." count={rows.new_entries.length}>
            {rows.new_entries.map((e, i) => (
              <EntryRow key={e.player || i} e={e} />
            ))}
          </Column>
        </div>
      )}
    </div>
  );
}
