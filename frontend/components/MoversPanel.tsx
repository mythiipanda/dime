"use client";

import { useEffect, useState } from "react";
import { type Mover, type MoversRows, getMovers, SEASON } from "../lib/api";
import EmptyState from "./EmptyState";
import Skeleton from "./Skeleton";
import { Panel } from "./ds/Panel";
import { RecordsTable } from "./ds/RecordsTable";
import { SegmentedControl } from "./ds/SegmentedControl";

const periods = ["7d", "14d", "30d"] as const;
const moverRows = (rows: Mover[]) => rows.map((m) => ({ Player: m.player || "Unknown", Team: m.team || "—", "Rank change": m.rank_change ?? "—", Rank: (m.rank_base ?? "—") + " → " + (m.rank_now ?? "—"), "Points change": m.pts_change == null ? "—" : (m.pts_change > 0 ? "+" : "") + m.pts_change.toFixed(1) }));

export default function MoversPanel() {
  const [period, setPeriod] = useState<typeof periods[number]>("7d");
  const [rows, setRows] = useState<MoversRows | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let live = true;
    setLoading(true);
    getMovers(SEASON, parseInt(period, 10)).then((data) => { if (live) { setRows(data); setErr(""); } }).catch(() => { if (live) setErr("Movers are unavailable right now."); }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [period]);
  return <Panel title="Leaderboard movers" description="Changes in scoring rank across your selected window." actions={<SegmentedControl options={periods} value={period} onChange={setPeriod} />}>
    {loading ? <Skeleton lines={3} /> : err ? <EmptyState title="Movers are unavailable" description={err} /> : !rows || ![...rows.climbers, ...rows.fallers, ...rows.new_entries].length ? <EmptyState title="No movers yet" description="Rankings need another slate of games before movers appear." /> : <div className="grid gap-4 xl:grid-cols-3">
      <RecordsTable title="Climbers" rows={moverRows(rows.climbers)} />
      <RecordsTable title="Fallers" rows={moverRows(rows.fallers)} />
      <RecordsTable title="New entries" rows={rows.new_entries.map((entry) => ({ Player: entry.player || "Unknown", Team: entry.team || "—", Rank: entry.rank ?? "—" }))} />
    </div>}
  </Panel>;
}
