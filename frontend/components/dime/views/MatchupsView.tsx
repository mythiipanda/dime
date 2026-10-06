"use client";

import { useState } from "react";
import FormChips from "@/components/dime/views/FormChips";
import { matchups, type Matchup, type MatchupStat } from "@/lib/dime-data-matchups";

function MatchupBars({ rows, aName, bName }: { rows: MatchupStat[]; aName: string; bName: string }) {
  return (
    <div>
      <div className="divide-y divide-line">
        {rows.map((r) => {
          const max = Math.max(r.away, r.home) || 1;
          const aLead = r.lowerBetter ? r.away <= r.home : r.away >= r.home;
          return (
            <div key={r.label} className="py-2.5">
              <div className="flex items-baseline justify-between text-[12.5px]">
                <span className="text-ink-2">{r.label}</span>
                <span className="font-mono tabular-nums">
                  <span className={aLead ? "font-semibold text-ink" : "text-ink-3"}>{r.fmt(r.away)}</span>
                  <span className="text-ink-3"> · </span>
                  <span className={!aLead ? "font-semibold text-ink" : "text-ink-3"}>{r.fmt(r.home)}</span>
                </span>
              </div>
              <div className="mt-1.5 grid grid-cols-2 gap-1.5" aria-hidden>
                <div className="h-1 overflow-hidden rounded-full bg-field">
                  <div
                    className={`h-full rounded-full ${aLead ? "bg-ink" : "bg-line-strong"}`}
                    style={{ width: `${(r.away / max) * 100}%` }}
                  />
                </div>
                <div className="h-1 overflow-hidden rounded-full bg-field">
                  <div
                    className={`h-full rounded-full ${!aLead ? "bg-ink" : "bg-line-strong"}`}
                    style={{ width: `${(r.home / max) * 100}%` }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex items-center gap-1.5 py-2.5 text-[11px] text-ink-3">
        <span className="inline-block size-2 rounded-[2px] bg-ink" /> {aName}
        <span className="ml-2 inline-block size-2 rounded-[2px] bg-line-strong" /> {bName}
        <span className="ml-1">solid marks the leader</span>
      </div>
    </div>
  );
}

function MatchupDetail({ m }: { m: Matchup }) {
  return (
    <div
      className="rounded-[10px] bg-surface p-4 shadow-hairline sm:p-5"
      style={{ animation: "fade-up 200ms cubic-bezier(0.23,1,0.32,1) both" }}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <div className="text-[14px] font-medium text-ink">
          {m.awayName}{" "}
          <span className="font-mono text-[12px] font-normal tabular-nums text-ink-3">{m.awayRecord}</span>
          <span className="mx-1.5 text-[12px] font-normal text-ink-3">@</span>
          {m.homeName}{" "}
          <span className="font-mono text-[12px] font-normal tabular-nums text-ink-3">{m.homeRecord}</span>
        </div>
        <div className="shrink-0 text-[12px] text-ink-3">
          {m.time} · {m.network}
        </div>
      </div>

      <div className="mt-2">
        <MatchupBars rows={m.stats} aName={m.away} bName={m.home} />
      </div>

      <div className="mt-1 space-y-2 border-t border-line pt-3">
        <div className="flex flex-wrap items-center justify-between gap-y-1">
          <span className="text-[12px] text-ink-3">{m.away} last 10</span>
          <FormChips form={m.awayForm} />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-y-1">
          <span className="text-[12px] text-ink-3">{m.home} last 10</span>
          <FormChips form={m.homeForm} />
        </div>
      </div>

      <div className="mt-3 divide-y divide-line border-t border-line">
        {m.notes.map((n, i) => (
          <div key={i} className="py-2.5 text-[13px] leading-[1.55] text-ink-2">{n}</div>
        ))}
      </div>
    </div>
  );
}

export default function MatchupsView() {
  const [activeId, setActiveId] = useState(matchups[0]?.id ?? "");
  const active = matchups.find((m) => m.id === activeId) ?? matchups[0];

  if (!active) {
    return (
      <div className="mx-auto w-full max-w-[760px] px-4 py-6 sm:px-8">
        <h1 className="text-[15px] font-semibold text-ink">Matchups</h1>
        <div className="mt-4 rounded-[10px] bg-surface p-8 text-center text-[13px] text-ink-3 shadow-hairline">
          No games tonight.
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[760px] px-4 py-6 sm:px-8">
      <div className="flex items-baseline justify-between">
        <h1 className="text-[15px] font-semibold text-ink">Matchups</h1>
        <span className="text-[12px] tabular-nums text-ink-3">{matchups.length} {matchups.length === 1 ? "game" : "games"}</span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        {matchups.map((m) => {
          const selected = m.id === activeId;
          return (
            <button
              key={m.id}
              type="button"
              onClick={() => setActiveId(m.id)}
              aria-pressed={selected}
              className={`select-none rounded-[10px] p-3 text-left shadow-hairline transition-[background-color,transform] duration-150 active:scale-[0.98] ${
                selected ? "bg-hover-2" : "bg-surface hover:bg-hover"
              }`}
            >
              <div className={`text-[13px] font-medium ${selected ? "text-ink" : "text-ink-2"}`}>
                {m.away} <span className="font-normal text-ink-3">@</span> {m.home}
              </div>
              <div className="mt-0.5 text-[11.5px] tabular-nums text-ink-3">
                {m.time} · {m.network}
              </div>
            </button>
          );
        })}
      </div>
      <div className="mt-3">
        <MatchupDetail key={active.id} m={active} />
      </div>
    </div>
  );
}
