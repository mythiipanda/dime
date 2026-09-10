"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  WatchItem,
  addWatchlist,
  getWatchlist,
  removeWatchlist,
  resolvePlayers,
} from "../lib/api";
import EmptyState from "./EmptyState";

function snapshotLabel(item: WatchItem): string {
  const s = item.snapshot || {};
  if (item.entity_type === "player") {
    if (s.found && typeof s.ppg === "number") {
      const parts = [`${s.ppg.toFixed(1)} PPG`];
      if (typeof s.rpg === "number") parts.push(`${s.rpg.toFixed(1)} RPG`);
      if (typeof s.apg === "number") parts.push(`${s.apg.toFixed(1)} APG`);
      return parts.join(" · ");
    }
    return "No stats yet";
  }
  if (s.found && s.record) return s.record;
  if (typeof s.wins === "number") return `${s.wins}-${s.losses ?? 0}`;
  return "No record yet";
}

function snapshotSub(item: WatchItem): string {
  const s = item.snapshot || {};
  if (item.entity_type === "player") {
    const bits = [s.team, typeof s.gp === "number" ? `${s.gp} GP` : ""].filter(Boolean);
    return bits.join(" · ");
  }
  return s.name || "";
}

export default function WatchlistPanel() {
  const [items, setItems] = useState<WatchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [etype, setEtype] = useState<"player" | "team">("player");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);

  const refresh = useCallback(async () => {
    try {
      setItems(await getWatchlist());
      setErr("");
    } catch {
      setErr("Watchlist is unavailable right now.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const add = async () => {
    const id = name.trim();
    if (!id || busy) return;
    setBusy(true);
    setFormErr("");
    try {
      const canonical =
        etype === "player" ? id : id.toUpperCase();
      if (etype === "player") {
        const hit = (await resolvePlayers(id, 1))[0];
        await addWatchlist(etype, hit ? hit.name : id);
      } else {
        await addWatchlist(etype, canonical);
      }
      setName("");
      await refresh();
    } catch (e) {
      setFormErr(e instanceof Error ? e.message : "Add failed. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (item: WatchItem) => {
    try {
      await removeWatchlist(item.entity_type, item.entity_id);
      await refresh();
    } catch {
      setErr("Remove failed. Try again.");
    }
  };

  return (
    <div className="card">
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Watchlist</div>
      <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 12 }}>
        {etype === "player"
          ? "Add a player by full name."
          : "Add a team by abbreviation (e.g. OKC)."}
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <select
          className="field"
          value={etype}
          onChange={(e) => setEtype(e.target.value as "player" | "team")}
          aria-label="Entity type"
        >
          <option value="player">Player</option>
          <option value="team">Team</option>
        </select>
        <input
          ref={inputRef}
          className="field"
          style={{ flex: 1 }}
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") add();
          }}
          placeholder={etype === "player" ? "Shai Gilgeous-Alexander" : "OKC"}
          aria-label="Name"
        />
        <button className="pill-cta" onClick={add} disabled={busy || !name.trim()}>
          {busy ? "Adding..." : "Add"}
        </button>
      </div>
      {formErr && (
        <div style={{ fontSize: 12, color: "#e11d48", marginBottom: 8 }}>{formErr}</div>
      )}

      {loading ? (
        <div>
          {[90, 70].map((w, d) => (
            <div key={d} className="shimmer skeleton-row" style={{ width: `${w}%` }} />
          ))}
        </div>
      ) : err && !items.length ? (
        <div style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>{err}</div>
      ) : !items.length ? (
        <EmptyState
          icon="👁"
          title="Your watchlist is empty"
          description="Track players and teams to see them here."
          actionLabel="Add your first player"
          onAction={() => inputRef.current?.focus()}
        />
      ) : (
        <div>
          {items.map((item) => (
            <div
              key={`${item.entity_type}:${item.entity_id}`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "8px 0",
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
                  color: "var(--color-warm-gray)",
                  border: "1px solid var(--color-stone-border)",
                  borderRadius: 9999,
                  padding: "2px 8px",
                  flexShrink: 0,
                }}
              >
                {item.entity_type}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 500, color: "var(--color-ink-black)" }}>
                  {item.snapshot?.player || item.snapshot?.team || item.entity_id}
                </div>
                {snapshotSub(item) && (
                  <div style={{ fontSize: 11, color: "var(--color-ash-gray)" }}>
                    {snapshotSub(item)}
                  </div>
                )}
              </div>
              <span style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>
                {snapshotLabel(item)}
              </span>
              <button
                className="pill-ghost"
                style={{ fontSize: 12, padding: "3px 10px" }}
                onClick={() => remove(item)}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
