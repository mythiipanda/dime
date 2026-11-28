"use client";

import { SourceLine } from "@/components/ds/SourceLine";
import { useEffect, useState } from "react";
import { apiPath } from "@/lib/api";
import { Button } from "@/components/ds/Button";
import { BACKEND } from "@/lib/chat";
import type { DimeArtifact } from "@/lib/dime-stream";
import { nbaTeams } from "../../../lib/teams";
import PinButton from "../PinButton";

const money = (v: number) => `$${(v / 1_000_000).toFixed(1)}M`;
const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const TEAM_KEY = "dime_morning_team_v1";

type Provenance = { table?: string; as_of?: string | null };
type Block<T> = { ok?: boolean; error?: string; provenance?: Provenance } & T;

type Morning = {
  ok: boolean;
  team: string;
  season: string;
  blocks: {
    last_result: Block<{ game: { date: string; home: string; away: string; home_pts: number; away_pts: number; result: string; opponent: string } | null }>;
    next_game: Block<{ game: { date: string; name: string; short_name: string; season_type: string; opponent: string } | null }>;
    opponent: Block<{ row: { team: string; wins: number; losses: number; win_pct: number; playoff_rank: number; l10: string; conference: string } | null; name: string }>;
    standings: Block<{ row: { team: string; wins: number; losses: number; win_pct: number; playoff_rank: number; l10: string; conference: string } | null; projection: { projected_wins: number; projected_losses: number; make_playoffs_pct: number; win_title_pct: number } | null; pace_wins: number | null }>;
    injuries: Block<{ rows: Record<string, unknown>[] }>;
    news: Block<{ rows: Record<string, unknown>[] }>;
    cap: Block<{ row: { team: string; payroll: number; room_under_apron2: number; over_tax: boolean } | null; meta?: Record<string, unknown> }>;
  };
};

const table = (title: string, rows: (string | number)[][], provenance?: Provenance): DimeArtifact => ({
  kind: "table",
  title,
  columns: [
    { key: "item", label: "item" },
    { key: "value", label: "value" },
  ],
  rows,
  provenance: { origin: "warehouse", liveSources: [], capability: "product_morning", asOf: provenance?.as_of ?? undefined },
});

function Card({ title, cite, artifact, children }: { title: string; cite?: Provenance; artifact: DimeArtifact; children: React.ReactNode }) {
  return (
    <section className="flex flex-col rounded-xl border border-line bg-surface p-5">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h3 className="font-mono text-[10px] uppercase tracking-wider text-ink-3">{title}</h3>
        <PinButton artifact={artifact} />
      </div>
      <div className="min-h-12 flex-1">{children}</div>
      <SourceLine table={cite?.table} asOf={cite?.as_of ? String(cite.as_of) : null} />
    </section>
  );
}

function BlockError({ block, empty }: { block: { ok?: boolean; error?: string }; empty: string }) {
  return <p className="py-2 text-[12px] text-ink-3">{block.error ?? empty}</p>;
}

function staleness(dateText: string | undefined): string | null {
  if (!dateText) return null;
  const when = new Date(String(dateText).slice(0, 10) + "T12:00:00Z").getTime();
  if (Number.isNaN(when)) return null;
  const days = Math.floor((Date.now() - when) / 86400000);
  if (days <= 5) return null;
  return `warehouse snapshot; the latest result in the data is ${days} days behind today; this is a historical read, not this morning's`;
}

export default function MorningPage({ onAsk }: { onAsk?: (text: string, context?: import("@/lib/view-context").ViewContext) => void }) {
  const [team, setTeam] = useState("NYK");
  const [data, setData] = useState<Morning | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(TEAM_KEY);
      if (saved && nbaTeams.some(item => item.abbr === saved)) setTeam(saved);
    } catch {}
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    fetch(`${BACKEND}${apiPath(`/morning?team=${encodeURIComponent(team)}`)}`)
      .then(response => response.json())
      .then(value => {
        if (!active) return;
        if (!value.ok) {
          setError(value.error ?? "Could not load the morning page");
          setData(null);
        } else {
          setData(value);
        }
      })
      .catch(() => { if (active) setError("Could not reach the backend"); })
      .finally(() => { if (active) setLoading(false); });
    try { window.localStorage.setItem(TEAM_KEY, team); } catch {}
    return () => { active = false; };
  }, [team]);

  const blocks = data?.blocks;

  const lastRows = (): (string | number)[][] => {
    const game = blocks?.last_result.game;
    if (!game) return [["status", "no completed game found"]];
    return [
      ["result", `${game.result} ${game.away_pts}–${game.home_pts}`],
      ["line", `${game.away} @ ${game.home}`],
      ["date", game.date],
    ];
  };
  const nextRows = (): (string | number)[][] => {
    const game = blocks?.next_game.game;
    const opp = blocks?.opponent.row;
    const rows: (string | number)[][] = game ? [["game", game.name], ["date", String(game.date).slice(0, 10)], ["type", game.season_type]] : [["status", "no scheduled game found"]];
    if (opp) rows.push(["opponent form", `${opp.wins}-${opp.losses} · ${opp.conference} ${opp.playoff_rank} · L10 ${opp.l10}`]);
    return rows;
  };
  const injuryRows = (): (string | number)[][] => {
    const rows = blocks?.injuries.rows ?? [];
    if (!rows.length) return [["status", "no listed injury rows at source vintage"]];
    return rows.slice(0, 8).map(row => [String(row.player ?? row.PLAYER ?? row.name ?? "player"), String(row.status ?? row.STATUS ?? row.injury ?? row.detail ?? "listed")]);
  };
  const newsRows = (): (string | number)[][] => {
    const rows = blocks?.news.rows ?? [];
    if (!rows.length) return [["status", "no news items matched"]];
    return rows.slice(0, 6).map(row => [String(row.title ?? row.headline ?? "item"), String(row.source ?? row.published ?? row.date ?? "")]);
  };
  const standingsRows = (): (string | number)[][] => {
    const row = blocks?.standings.row;
    const proj = blocks?.standings.projection;
    const pace = blocks?.standings.pace_wins;
    if (!row) return [["status", "no standings row"]];
    const rows: (string | number)[][] = [
      ["record", `${row.wins}-${row.losses} (${pct(row.win_pct)})`],
      ["conference", `${row.conference} · seed ${row.playoff_rank}`],
      ["last 10", row.l10],
    ];
    if (pace != null && proj) rows.push(["pace vs projection", `${pace} wins pace vs ${proj.projected_wins} projected`]);
    return rows;
  };
  const capRows = (): (string | number)[][] => {
    const row = blocks?.cap.row;
    const meta = blocks?.cap.meta ?? {};
    if (!row) return [["status", "cap ledger unavailable"]];
    const rows: (string | number)[][] = [
      ["payroll", money(row.payroll)],
      ["room under apron 2", money(row.room_under_apron2)],
      ["over tax", row.over_tax ? "yes" : "no"],
    ];
    if (meta.apron1) rows.push(["apron 1", money(Number(meta.apron1))]);
    if (meta.apron2) rows.push(["apron 2", money(Number(meta.apron2))]);
    return rows;
  };

  return (
    <section className="mb-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-[15px] font-medium">Morning page</h2>
          <p className="mt-0.5 text-[12px] text-ink-3">One team's overnight read: last result, next opponent, health, standings and the cap sheet.{data?.season ? ` · ${data.season}` : ""}</p>
          {staleness(blocks?.last_result.game?.date) && (
            <p className="mt-0.5 text-[12px] text-orange">{staleness(blocks?.last_result.game?.date)}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
        {onAsk && data && (
          <Button
            size="sm"
            variant="secondary"
            onClick={() => onAsk(
              `Walk me through ${team}'s morning read: what matters most from the last result, the next opponent, the health picture, and where the team stands?`,
              {
                kind: "morning_briefing",
                summary: `${team} morning page${data.season ? ` · ${data.season}` : ""}`,
                entities: {
                  team,
                  season: data.season,
                  last_result: blocks?.last_result.game ?? null,
                  next_game: blocks?.next_game.game ?? null,
                  opponent_form: blocks?.opponent.row ?? null,
                  standings: { row: blocks?.standings.row ?? null, projection: blocks?.standings.projection ?? null },
                  injuries: (blocks?.injuries.rows ?? []).slice(0, 8),
                  cap: blocks?.cap.row ?? null,
                },
              },
            )}
          >
            Ask Dime about this morning
          </Button>
        )}
        <select
          aria-label="Morning page team"
          value={team}
          onChange={event => setTeam(event.target.value)}
          className="h-8 rounded-lg border border-line bg-surface px-2.5 text-[12px] text-ink"
        >
          {nbaTeams.map(item => <option key={item.abbr} value={item.abbr}>{item.abbr} · {item.name}</option>)}
        </select>
        </div>
      </div>
      {loading && <p role="status" className="py-8 text-[13px] text-ink-3">Loading the morning page…</p>}
      {error && !loading && <div role="alert" className="rounded-xl border border-line p-5"><p className="text-[13px] text-red">{error}. No sample data is substituted.</p></div>}
      {!loading && !error && blocks && (
        <div className="grid items-stretch gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <Card title="Last result" cite={blocks.last_result.provenance} artifact={table(`${team} last result`, lastRows(), blocks.last_result.provenance)}>
            {blocks.last_result.game
              ? <><p className="text-[17px] font-medium"><span className={blocks.last_result.game.result === "W" ? "text-green" : "text-red"}>{blocks.last_result.game.result}</span> {blocks.last_result.game.away} {blocks.last_result.game.away_pts} @ {blocks.last_result.game.home} {blocks.last_result.game.home_pts}</p><p className="mt-1 text-[12px] text-ink-3">{blocks.last_result.game.date}</p></>
              : <BlockError block={blocks.last_result} empty="No completed game found for this team." />}
          </Card>
          <Card title="Next opponent" cite={blocks.next_game.provenance} artifact={table(`${team} next opponent`, nextRows(), blocks.next_game.provenance)}>
            {blocks.next_game.game
              ? <><p className="text-[15px] font-medium leading-snug">{blocks.next_game.game.name}</p><p className="mt-1 text-[12px] text-ink-3">{String(blocks.next_game.game.date).slice(0, 16).replace("T", " ")} · {blocks.next_game.game.season_type}</p>
                  {blocks.opponent.row && <p className="mt-2 text-[12px] text-ink-2">{blocks.opponent.name || blocks.next_game.game.opponent}: {blocks.opponent.row.wins}-{blocks.opponent.row.losses}, {blocks.opponent.row.conference} #{blocks.opponent.row.playoff_rank}, last 10 {blocks.opponent.row.l10}</p>}
                  {blocks.opponent.error && <p className="mt-2 text-[12px] text-ink-3">Opponent form unavailable: {blocks.opponent.error}</p>}</>
              : <BlockError block={blocks.next_game} empty="No scheduled game found after the last result." />}
          </Card>
          <Card title="Injuries" cite={blocks.injuries.provenance} artifact={table(`${team} injuries`, injuryRows(), blocks.injuries.provenance)}>
            {blocks.injuries.error
              ? <BlockError block={blocks.injuries} empty="" />
              : blocks.injuries.rows.length
                ? <ul className="space-y-1.5">{blocks.injuries.rows.slice(0, 6).map((row, index) => <li key={index} className="text-[12px]"><span className="text-ink">{String(row.player ?? row.PLAYER ?? row.name ?? "player")}</span><span className="ml-2 text-ink-3">{String(row.status ?? row.STATUS ?? row.injury ?? row.detail ?? "listed")}</span></li>)}</ul>
                : <p className="py-2 text-[12px] text-ink-3">No listed injury rows at source vintage; availability unknown.</p>}
          </Card>
          <Card title="News" cite={blocks.news.provenance} artifact={table(`${team} news`, newsRows(), blocks.news.provenance)}>
            {blocks.news.error
              ? <BlockError block={blocks.news} empty="" />
              : blocks.news.rows.length
                ? <ul className="space-y-2">{blocks.news.rows.slice(0, 5).map((row, index) => <li key={index} className="text-[12px] leading-snug"><span className="text-ink-2">{String(row.title ?? row.headline ?? "item")}</span>{Boolean(row.source || row.date) && <span className="ml-2 text-[11px] text-ink-2">{String(row.source ?? row.date)}</span>}</li>)}</ul>
                : <p className="py-2 text-[12px] text-ink-3">No news items matched this team.</p>}
          </Card>
          <Card title="Standings vs expectation" cite={blocks.standings.provenance} artifact={table(`${team} standings`, standingsRows(), blocks.standings.provenance)}>
            {blocks.standings.row
              ? <><p className="text-[17px] font-medium">{blocks.standings.row.wins}-{blocks.standings.row.losses} <span className="text-[12px] font-normal text-ink-3">{blocks.standings.row.conference} #{blocks.standings.row.playoff_rank} · L10 {blocks.standings.row.l10}</span></p>
                  {blocks.standings.pace_wins != null && blocks.standings.projection
                    ? <p className="mt-1.5 text-[12px] text-ink-2">{blocks.standings.pace_wins} wins pace vs {blocks.standings.projection.projected_wins} projected{blocks.standings.projection.make_playoffs_pct != null ? ` · ${pct(blocks.standings.projection.make_playoffs_pct)} playoff odds` : ""}</p>
                    : <p className="mt-1.5 text-[12px] text-ink-3">No preseason projection seeded for a pace-vs-expectation read.</p>}</>
              : <BlockError block={blocks.standings} empty="No standings row for this team." />}
          </Card>
          <Card title="Cap sheet" cite={blocks.cap.provenance} artifact={table(`${team} cap sheet`, capRows(), blocks.cap.provenance)}>
            {blocks.cap.row
              ? <><p className="text-[17px] font-medium">{money(blocks.cap.row.payroll)} <span className="text-[12px] font-normal text-ink-3">payroll</span></p>
                  <p className="mt-1.5 text-[12px] text-ink-2">{money(blocks.cap.row.room_under_apron2)} under apron 2{blocks.cap.row.over_tax ? " · over the tax line" : ""}</p></>
              : <BlockError block={blocks.cap} empty="Cap ledger unavailable." />}
          </Card>
        </div>
      )}
    </section>
  );
}
