"use client";

import ArtifactChart from "@/components/dime/ArtifactChart";
import ArtifactCompare from "@/components/dime/ArtifactCompare";
import ArtifactShell from "@/components/dime/ArtifactShell";
import ArtifactShotChart from "@/components/dime/ArtifactShotChart";
import ArtifactTable, { type ArtifactColumn } from "@/components/dime/ArtifactTable";
import ThinkingState from "@/components/primitives/ThinkingState";
import ToolChips, { type ToolStep } from "@/components/primitives/ToolChips";
import {
  answerText,
  compareRows,
  exploreRows,
  followUps,
  lukaTrend,
  sgaTrend,
  sgaZones,
  thinkRows,
  tonightGames,
} from "@/lib/dime-data";

const TOOL_STEPS: ToolStep[] = [
  {
    icon: "read",
    label: "boxscores.query",
    chip: "per-game scoring \u00b7 last 30",
    mono: true,
    detailMono: true,
    detail: [
      { text: "SELECT player, AVG(pts), AVG(ts_pct)" },
      { text: "FROM player_game_logs \u00b7 2 rows \u00b7 412ms" },
    ],
  },
  {
    icon: "read",
    label: "lineups.query",
    chip: "on/off net rating",
    mono: true,
    detailMono: true,
    detail: [
      { text: "SELECT on_court_net, off_court_net" },
      { text: "FROM lineup_data \u00b7 2 rows \u00b7 388ms" },
    ],
  },
  {
    icon: "write",
    label: "artifact.build",
    chip: "scoring trend \u00b7 last 15",
    mono: true,
    detailMono: false,
    detail: [{ text: "2 series rendered \u00b7 pts by game" }],
  },
];

const TABLE_COLS: ArtifactColumn[] = [
  { key: "player", label: "Player" },
  { key: "team", label: "Team" },
  { key: "gp", label: "GP", numeric: true },
  { key: "ppg", label: "PPG", numeric: true },
  { key: "ts", label: "TS%", numeric: true },
  { key: "usg", label: "USG%", numeric: true },
  { key: "net", label: "Net/100", numeric: true },
];

type PlayerTuple = [string, string, number, number, number, number, number];
const TABLE_ROWS: PlayerTuple[] = exploreRows.map((r) => [
  r.name,
  r.team,
  r.gp,
  r.ppg,
  r.ts,
  r.usg,
  r.net,
]);

function renderPlayerCell(row: PlayerTuple, col: number) {
  if (col === 0) return <span className="font-medium text-ink">{row[0]}</span>;
  if (col === 1) return <span className="text-ink-2">{row[1]}</span>;
  if (col === 3) return <span className="text-ink">{row[3].toFixed(1)}</span>;
  if (col === 6) {
    return (
      <span className={row[6] >= 9 ? "text-green" : "text-ink-2"}>
        {row[6] > 0 ? "+" : ""}
        {row[6].toFixed(1)}
      </span>
    );
  }
  const v = row[col];
  return (
    <span className="text-ink-2">
      {typeof v === "number" ? v.toFixed(col === 2 ? 0 : 1) : v}
    </span>
  );
}

function TonightStrip() {
  return (
    <div className="grid grid-cols-2 gap-px bg-line sm:grid-cols-3">
      {tonightGames.map((g) => (
        <div
          key={g.away + g.home}
          className="min-w-0 bg-surface px-3.5 py-2.5 transition-colors duration-100 hover:bg-hover"
        >
          <div className="flex items-center gap-1.5">
            {g.live && <span className="size-1.5 shrink-0 rounded-full bg-red" />}
            <span className="truncate text-[13px] font-medium text-ink">
              {g.away}
              <span className="font-normal text-ink-3"> @ </span>
              {g.home}
            </span>
            <span className="ml-auto shrink-0 font-mono text-[11px] tabular-nums text-ink-3">
              {g.time}
            </span>
          </div>
          <div className="mt-1 truncate font-mono text-[11px] tabular-nums text-ink-2">
            {g.line}
            <span className="text-ink-3"> \u00b7 {g.ou}</span>
          </div>
          {g.note && <div className="mt-0.5 truncate text-[11px] text-ink-3">{g.note}</div>}
        </div>
      ))}
    </div>
  );
}

export function ReferenceExample({ onFollowUp }: { onFollowUp: (q: string) => void }) {
  return (
    <>
      <div className="mb-3 flex items-center gap-2">
        <span className="rounded-full border border-line px-2 py-0.5 text-[11px] font-medium text-ink-3">
          Sample analysis
        </span>
        <span className="text-[11px] text-ink-3">
          A worked example. Ask anything to start your own.
        </span>
      </div>
      <div
        className="flex justify-end pl-10 sm:pl-24"
        style={{ animation: "fade-up 280ms cubic-bezier(0.23,1,0.32,1) both" }}
      >
        <div className="rounded-xl bg-field px-3.5 py-2 text-[13px] leading-relaxed text-ink shadow-hairline">
          Compare SGA and Luka this season \u2014 scoring, efficiency, and team impact.
        </div>
      </div>

      <div className="mt-2">
        <ThinkingState variant="Steps" rows={thinkRows} done="Thought for 6 seconds" />
      </div>

      <div className="mt-3">
        <ToolChips
          steps={TOOL_STEPS}
          diffs={[]}
          labels={{ header: "3 warehouse calls", more: "" }}
        />
      </div>

      <div className="mt-5 flex flex-col gap-4">
        <ArtifactShell title="Scoring & efficiency \u2014 last 30 games" source="silver_boxscores" delay={0}>
          <ArtifactCompare rows={compareRows} aName="SGA" bName="Don\u010di\u0107" />
        </ArtifactShell>
        <ArtifactShell title="Scoring trend \u2014 last 15 games" source="silver_boxscores" delay={40}>
          <ArtifactChart
            series={[
              { name: "Gilgeous-Alexander", tone: "ink", values: sgaTrend },
              { name: "Don\u010di\u0107", tone: "muted", values: lukaTrend },
            ]}
            footnote="points per game \u00b7 last 15"
          />
        </ArtifactShell>
        <ArtifactShell title="Shot chart \u2014 Gilgeous-Alexander" source="tracking feed" delay={80}>
          <ArtifactShotChart zones={sgaZones} />
        </ArtifactShell>
      </div>

      <p className="mt-5 max-w-[620px] text-[13.5px] leading-[1.65] text-ink-2">{answerText}</p>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {followUps.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => onFollowUp(f)}
            className="rounded-full bg-surface px-3 py-1.5 text-left text-[12px] text-ink shadow-btn transition-[background-color,transform] duration-150 hover:bg-hover active:scale-[0.97]"
          >
            {f}
          </button>
        ))}
      </div>

      <div className="mt-6">
        <ArtifactShell title="League scoring" source="silver_boxscores \u00b7 8 of 330,485 rows" delay={120}>
          <ArtifactTable columns={TABLE_COLS} rows={TABLE_ROWS} renderCell={renderPlayerCell} />
        </ArtifactShell>
      </div>

      <div className="mt-4">
        <ArtifactShell title="Tonight" source="silver_schedule \u00b7 6 games" delay={160}>
          <TonightStrip />
        </ArtifactShell>
      </div>
    </>
  );
}
