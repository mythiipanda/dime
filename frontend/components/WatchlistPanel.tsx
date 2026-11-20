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
import Skeleton from "./Skeleton";
import { Panel } from "./ds/Panel";
import { Button } from "./ds/Button";
import { Chip } from "./ds/Chip";
import { TextField } from "./ds/TextField";

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


  return <Panel title="Watchlist" description="A focused view of the players and teams that matter to your work.">
    <form className="mb-5 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); void add(); }}>
      <select aria-label="Entity type" value={etype} onChange={(e) => setEtype(e.target.value as "player" | "team")} className="rounded-lg border border-line-strong bg-field px-3 py-2 text-[12px] text-ink"><option value="player">Player</option><option value="team">Team</option></select>
      <TextField ref={inputRef} className="min-w-40 flex-1" value={name} onChange={(e) => setName(e.target.value)} placeholder={etype === "player" ? "Shai Gilgeous-Alexander" : "OKC"} aria-label="Name" />
      <Button variant="primary" size="sm" className="self-center" disabled={busy || !name.trim()}>{busy ? "Adding..." : "Add"}</Button>
    </form>
    {formErr && <p role="alert" className="mb-3 text-[12px] text-red">{formErr}</p>}
    {err && <p role="alert" className="mb-3 text-[12px] text-red">{err}</p>}
    {loading ? <Skeleton lines={2} /> : !items.length ? !err && <EmptyState title="Your watchlist is empty" description="Track players and teams to see them here." actionLabel="Add your first player" onAction={() => inputRef.current?.focus()} /> : <ul className="divide-y divide-line">{items.map((item) => <li key={item.entity_type + ":" + item.entity_id} className="flex flex-wrap items-center gap-3 py-3">
      <Chip>{item.entity_type}</Chip><div className="min-w-32 flex-1"><p className="text-[13px] font-medium">{item.snapshot?.player || item.snapshot?.team || item.entity_id}</p>{snapshotSub(item) && <p className="mt-1 text-[11px] text-ink-3">{snapshotSub(item)}</p>}</div><span className="text-[12px] tabular-nums text-ink-2">{snapshotLabel(item)}</span><Button size="xs" variant="quiet" onClick={() => remove(item)}>Remove</Button>
    </li>)}</ul>}
  </Panel>;
}
