"use client";

import { useEffect, useState } from "react";
import { GameRow, TodayRows, getToday, getDatasetJson, SEASON } from "../lib/api";
import EmptyState from "./EmptyState";
import Skeleton from "./Skeleton";
import { Panel } from "./ds/Panel";
import { Chip } from "./ds/Chip";
import { RecordsTable } from "./ds/RecordsTable";







type SeasonWrap = {
  season: string;
  champion: string;
  runnerUp: string;
  series: string;
  scoring: string;
  best: string;
};

function useSeasonWrap(active: boolean): SeasonWrap | null {
  const [wrap, setWrap] = useState<SeasonWrap | null>(null);
  useEffect(() => {
    if (!active) return;
    let live = true;
    (async () => {
      try {
        const [po, ld, st] = await Promise.all([
          getDatasetJson("playoffs", { season: SEASON }),
          getDatasetJson("leaders", { season: SEASON, stat: "PTS" }),
          getDatasetJson("standings", { season: SEASON }),
        ]);
        if (!live) return;
        

        const finals = ((po.data || []) as Record<string, unknown>[]).filter(
          (r) => String(r.GAME_ID || "").slice(6, 8) === "04",
        );
        const wins: Record<string, { name: string; w: number }> = {};
        for (const r of finals) {
          const ab = String(r.TEAM_ABBREVIATION || "");
          if (!ab) continue;
          wins[ab] = wins[ab] || { name: String(r.TEAM_NAME || ab), w: 0 };
          if (String(r.WL) === "W") wins[ab].w += 1;
        }
        const teams = Object.values(wins).sort((a, b) => b.w - a.w);
        if (teams.length < 2 || teams[0].w < 4) return;
        const leaders = (ld.data || []) as Record<string, unknown>[];
        const top = [...leaders]
          .filter((r) => typeof r.PTS === "number" && typeof r.GP === "number" && (r.GP as number) > 0)
          .sort((a, b) => (b.PTS as number) / (b.GP as number) - (a.PTS as number) / (a.GP as number))[0];
        const standings = (st.data || []) as Record<string, unknown>[];
        const bestRow = [...standings]
          .filter((r) => typeof r.WINS === "number")
          .sort((a, b) => (b.WINS as number) - (a.WINS as number))[0];
        setWrap({
          season: SEASON,
          champion: teams[0].name,
          runnerUp: teams[1].name,
          series: `${teams[0].w}-${teams[1].w}`,
          scoring: top
            ? `${String(top.PLAYER)}, ${Math.round(((top.PTS as number) / (top.GP as number)) * 10) / 10} ppg`
            : "",
          best: bestRow
            ? `${String(bestRow.TeamCity)} ${String(bestRow.TeamName)}, ${bestRow.WINS}-${bestRow.LOSSES}`
            : "",
        });
      } catch {
        

      }
    })();
    return () => {
      live = false;
    };
  }, [active]);
  return wrap;
}


function Games({ games, title }: { games: GameRow[]; title: string }) {
  return <div><h3 className="mb-3 text-[11px] font-medium text-ink-3">{title}</h3>{games.length ? <div className="grid gap-2 sm:grid-cols-2">{games.map((game, i) => <div key={i} className="rounded-lg border border-line bg-inset px-4 py-3"><div className="mb-2 text-[10px] text-ink-3">{game.GAME_STATUS_TEXT || "Scheduled"}</div><div className="flex justify-between text-[13px]"><span>{game.VISITOR_TEAM_ABBREVIATION || "TBD"}</span><span className="font-mono">{game.VISITOR_TEAM_PTS ?? "—"}</span></div><div className="mt-1.5 flex justify-between text-[13px]"><span>{game.HOME_TEAM_ABBREVIATION || "TBD"}</span><span className="font-mono">{game.HOME_TEAM_PTS ?? "—"}</span></div></div>)}</div> : <p className="rounded-lg border border-dashed border-line px-4 py-5 text-[12px] text-ink-3">No games on this slate.</p>}</div>;
}

export default function TodayPanel() {
  const [rows, setRows] = useState<TodayRows | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let live = true;
    getToday().then((data) => { if (live) setRows(data); }).catch(() => { if (live) setErr("Today is unavailable right now."); }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);
  const noGames = !!rows && !(rows.last_night || []).length && !(rows.tonight || []).length;
  const wrap = useSeasonWrap(noGames);
  return <Panel title="Today" description="Scores and signals from the latest available data." actions={<Chip>League snapshot</Chip>}>
    {loading ? <Skeleton lines={3} label="Loading today..." /> : err || !rows ? <EmptyState title="Today is unavailable" description={err || "We couldn't load today's slate. Try again in a bit."} /> : <>
      {noGames ? <div className="rounded-lg border border-dashed border-line bg-inset"><EmptyState title="No games today" description="No games are posted for this slate. Explore season leaders or prepare your next scouting report." /></div> : <div className="grid gap-6 md:grid-cols-2"><Games title="Last night" games={rows.last_night || []} /><Games title="Tonight" games={rows.tonight || []} /></div>}
      {wrap && <div className="mt-5 grid gap-3 rounded-lg border border-line bg-inset p-4 text-[12px] sm:grid-cols-3"><div><p className="mb-2 text-[10px] text-ink-3">{wrap.season} CHAMPIONS</p><p>{wrap.champion}</p><p className="mt-1 text-ink-3">def. {wrap.runnerUp}, {wrap.series}</p></div><div><p className="mb-2 text-[10px] text-ink-3">SCORING LEADER</p><p>{wrap.scoring || "Not available"}</p></div><div><p className="mb-2 text-[10px] text-ink-3">BEST RECORD</p><p>{wrap.best || "Not available"}</p></div></div>}
      <div className="mt-5 grid gap-5 lg:grid-cols-2"><div>{rows.movers?.length ? <RecordsTable title="Leaderboard movers (7d)" rows={rows.movers.slice(0, 6).map((m) => ({ Player: m.PLAYER || "Unknown", Team: m.TEAM || "—", Rank: m.RANK_CHANGE || "—", "Points change": m.PTS_CHANGE ?? "—" }))} /> : <EmptyState title="Movers not loaded yet" description="Leaderboard movement hasn't loaded yet. Check back soon." />}</div><div>{rows.streaks?.length ? <RecordsTable title="Team streaks (3+ games)" rows={rows.streaks.map((s) => ({ Team: s.TEAM || "Unknown", Streak: s.STREAK || s.GAMES || "—", Record: (s.W ?? "—") + "–" + (s.L ?? "—") }))} /> : <EmptyState title="No active 3+ game streaks" description="No team is on a run right now. Check back after the next slate." />}</div></div>
    </>}
  </Panel>;
}
