"use client";

import { useMemo, useState } from "react";
import ArtifactTable, { type ArtifactColumn } from "@/components/dime/ArtifactTable";
import { explorePlayers, exploreTeams, type ExplorePlayer } from "@/lib/dime-data-explore";

const columns: ArtifactColumn[] = [
  { key: "name", label: "Player" },
  { key: "team", label: "Team" },
  { key: "pos", label: "Pos" },
  { key: "gp", label: "GP", numeric: true },
  { key: "mpg", label: "MPG", numeric: true },
  { key: "ppg", label: "PPG", numeric: true },
  { key: "rpg", label: "RPG", numeric: true },
  { key: "apg", label: "APG", numeric: true },
  { key: "ts", label: "TS%", numeric: true },
  { key: "usg", label: "USG%", numeric: true },
  { key: "net", label: "Net/100", numeric: true },
];

const signed = (v: number) => (v > 0 ? "+" : "") + v.toFixed(1);

export default function ExploreView() {
  const [query, setQuery] = useState("");
  const [team, setTeam] = useState("ALL");

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return explorePlayers
      .filter((p) => (team === "ALL" || p.team === team) && (q === "" || p.name.toLowerCase().includes(q)))
      .map((p: ExplorePlayer): (string | number)[] => [
        p.name, p.team, p.pos, p.gp, p.mpg, p.ppg, p.rpg, p.apg, p.ts, p.usg, p.net,
      ]);
  }, [query, team]);

  return (
    <div className="mx-auto w-full max-w-[900px] px-4 py-6 sm:px-8">
      <div className="flex items-baseline justify-between">
        <h1 className="text-[15px] font-semibold text-ink">Explore</h1>
        <span className="text-[12px] text-ink-3 tabular-nums">{rows.length} {rows.length === 1 ? "player" : "players"}</span>
      </div>
      <div className="mt-4 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search players"
          aria-label="Search players"
          enterKeyHint="search"
          className="h-8 min-w-0 flex-1 rounded-[8px] border border-line bg-field px-2.5 text-[13px] text-ink outline-none placeholder:text-ink-3 focus:border-line-strong [@media(pointer:coarse)]:text-base"
        />
        <select
          value={team}
          onChange={(e) => setTeam(e.target.value)}
          aria-label="Filter by team"
          className="h-8 shrink-0 rounded-[8px] border border-line bg-field px-2 text-[13px] text-ink-2 outline-none focus:border-line-strong [@media(pointer:coarse)]:text-base"
        >
          <option value="ALL">All teams</option>
          {exploreTeams.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>
      <div className="mt-3 overflow-x-auto rounded-[10px] bg-surface shadow-hairline">
        {rows.length > 0 ? (
          <ArtifactTable
            columns={columns}
            rows={rows}
            renderCell={(row, col) => {
              const v = row[col];
              if (col === 0)
                return (
                  <span className="block max-w-[170px] truncate" title={String(v)}>
                    {String(v)}
                  </span>
                );
              if (col === 3) return String(v);
              if (col === 8) return `${(v as number).toFixed(1)}%`;
              if (col === 9) return `${(v as number).toFixed(1)}%`;
              if (col === 10) {
                const n = v as number;
                return <span className={n > 0 ? "text-ink" : n < 0 ? "text-ink-2" : ""}>{signed(n)}</span>;
              }
              if (typeof v === "number") return v.toFixed(1);
              return String(v);
            }}
          />
        ) : (
          <div className="px-4 py-10 text-center text-[13px] text-ink-3">No players match.</div>
        )}
      </div>
    </div>
  );
}
