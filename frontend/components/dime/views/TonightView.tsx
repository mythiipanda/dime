"use client";

import { useState } from "react";
import FormChips from "@/components/dime/views/FormChips";
import { tonightGames, tonightLabel, type TonightGame } from "@/lib/dime-data-tonight";

function WinProb({ game }: { game: TonightGame }) {
  const home = game.homeWinProb;
  const away = 100 - home;
  const homeLead = home >= away;
  return (
    <div>
      <div className="flex items-baseline justify-between text-[12px]">
        <span className="text-ink-2">
          {game.home}{" "}
          <span className={`font-mono tabular-nums ${homeLead ? "font-semibold text-ink" : "text-ink-3"}`}>
            {home}%
          </span>
        </span>
        <span className="text-ink-2">
          {game.away}{" "}
          <span className={`font-mono tabular-nums ${!homeLead ? "font-semibold text-ink" : "text-ink-3"}`}>
            {away}%
          </span>
        </span>
      </div>
      <div className="mt-1.5 flex h-1 overflow-hidden rounded-full bg-field" aria-hidden>
        <div className={`h-full rounded-full ${homeLead ? "bg-ink" : "bg-line-strong"}`} style={{ width: `${home}%` }} />
        <div className={`h-full rounded-full ${!homeLead ? "bg-ink" : "bg-line-strong"}`} style={{ width: `${away}%` }} />
      </div>
    </div>
  );
}

function GameCard({ game }: { game: TonightGame }) {
  const [open, setOpen] = useState(false);
  const fav = game.homeWinProb >= 50 ? game.home : game.away;
  const favProb = Math.max(game.homeWinProb, 100 - game.homeWinProb);
  return (
    <div className="rounded-[10px] bg-surface p-4 shadow-hairline">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full select-none items-start justify-between gap-3 text-left"
      >
        <div className="min-w-0">
          <div className="text-[13.5px] font-medium text-ink">
            {game.away} <span className="font-mono text-[12px] font-normal tabular-nums text-ink-3">{game.awayRecord}</span>
            <span className="mx-1.5 text-ink-3">@</span>
            {game.home} <span className="font-mono text-[12px] font-normal tabular-nums text-ink-3">{game.homeRecord}</span>
          </div>
          <div className="mt-1 font-mono text-[11px] tabular-nums text-ink-3">
            {game.spread} · {game.total} · {fav} {favProb}%
          </div>
          {game.injuries.length > 0 && (
            <div className="mt-1 text-[12px] text-ink-3">{game.injuries.join(" · ")}</div>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <div className="text-right">
            <div className="text-[12.5px] font-medium tabular-nums text-ink-2">{game.time}</div>
            {game.network !== "" && <div className="text-[11px] text-ink-3">{game.network}</div>}
          </div>
          <svg
            width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden
            className="mt-0.5 text-ink-3"
            style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 150ms cubic-bezier(0.16,1,0.3,1)" }}
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        </div>
      </button>
      <div
        className={`grid transition-[grid-template-rows] duration-220 ease-out ${open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}
        style={{ transitionTimingFunction: "cubic-bezier(0.23,1,0.32,1)" }}
      >
        <div className="overflow-hidden">
          <div className="mt-3 border-t border-line pt-3">
            <WinProb game={game} />
            <div className="mt-3 space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-y-1">
                <span className="text-[12px] text-ink-3">{game.away} last 10</span>
                <FormChips form={game.awayForm} />
              </div>
              <div className="flex flex-wrap items-center justify-between gap-y-1">
                <span className="text-[12px] text-ink-3">{game.home} last 10</span>
                <FormChips form={game.homeForm} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function TonightView() {
  return (
    <div className="mx-auto w-full max-w-[760px] px-4 py-6 sm:px-8">
      <div className="flex items-baseline justify-between">
        <h1 className="text-[15px] font-semibold text-ink">Tonight</h1>
        <span className="text-[12px] tabular-nums text-ink-3">{tonightLabel} · {tonightGames.length} {tonightGames.length === 1 ? "game" : "games"}</span>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
        {tonightGames.length > 0 ? (
          tonightGames.map((g) => <GameCard key={g.id} game={g} />)
        ) : (
          <div className="rounded-[10px] bg-surface p-8 text-center text-[13px] text-ink-3 shadow-hairline">
            No games tonight.
          </div>
        )}
      </div>
    </div>
  );
}
