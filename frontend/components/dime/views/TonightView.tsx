"use client";

import { useEffect, useState } from "react";
import FormChips from "@/components/dime/views/FormChips";
import { getToday, type GameRow } from "@/lib/api";
import { tonightGames as sampleGames, tonightLabel as sampleLabel, type TonightGame } from "@/lib/dime-data-tonight";

function SampleBadge() {
  return (
    <span className="ml-2 shrink-0 rounded-full border border-line px-2 py-0.5 align-middle font-mono text-[10.5px] uppercase tracking-wide text-ink-3">
      Sample data
    </span>
  );
}

function WinProb({ home, away, prob }: { home: string; away: string; prob: number }) {
  const awayProb = 100 - prob;
  const homeLead = prob >= awayProb;
  return (
    <div>
      <div className="flex items-baseline justify-between text-[12px]">
        <span className="text-ink-2">
          {home}{" "}
          <span className={`font-mono tabular-nums ${homeLead ? "font-semibold text-ink" : "text-ink-3"}`}>
            {prob}%
          </span>
        </span>
        <span className="text-ink-2">
          {away}{" "}
          <span className={`font-mono tabular-nums ${!homeLead ? "font-semibold text-ink" : "text-ink-3"}`}>
            {awayProb}%
          </span>
        </span>
      </div>
      <div className="mt-1.5 flex h-1 overflow-hidden rounded-full bg-field" aria-hidden>
        <div className={`h-full rounded-full ${homeLead ? "bg-ink" : "bg-line-strong"}`} style={{ width: `${prob}%` }} />
        <div className={`h-full rounded-full ${!homeLead ? "bg-ink" : "bg-line-strong"}`} style={{ width: `${awayProb}%` }} />
      </div>
    </div>
  );
}

function GameCard({ game }: { game: TonightGame }) {
  const [open, setOpen] = useState(false);
  const expandable = game.expandable ?? true;
  const prob = game.homeWinProb ?? null;
  const fav = prob !== null ? (prob >= 50 ? game.home : game.away) : null;
  const favProb = prob !== null ? Math.max(prob, 100 - prob) : null;
  const metaBits = [game.spread, game.total]
    .filter(Boolean)
    .concat(fav && favProb !== null ? [`${fav} ${favProb}%`] : [])
    .concat(game.score ? [game.score] : []);

  const header = (
    <div className="flex w-full select-none items-start justify-between gap-3 text-left">
      <div className="min-w-0">
        <div className="text-[13.5px] font-medium text-ink">
          {game.away}{" "}
          {game.awayRecord && (
            <span className="font-mono text-[12px] font-normal tabular-nums text-ink-3">{game.awayRecord}</span>
          )}
          <span className="mx-1.5 text-ink-3">@</span>
          {game.home}{" "}
          {game.homeRecord && (
            <span className="font-mono text-[12px] font-normal tabular-nums text-ink-3">{game.homeRecord}</span>
          )}
        </div>
        <div className="mt-1 font-mono text-[11px] tabular-nums text-ink-3">
          {metaBits.length > 0 ? metaBits.join(" · ") : " "}
        </div>
        {game.injuries && game.injuries.length > 0 && (
          <div className="mt-1 text-[12px] text-ink-3">{game.injuries.join(" · ")}</div>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <div className="text-right">
          <div className="text-[12.5px] font-medium tabular-nums text-ink-2">{game.time}</div>
          {game.network && <div className="text-[11px] text-ink-3">{game.network}</div>}
        </div>
        {expandable && (
          <svg
            width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden
            className="mt-0.5 text-ink-3"
            style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 150ms cubic-bezier(0.16,1,0.3,1)" }}
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        )}
      </div>
    </div>
  );

  return (
    <div className="rounded-[10px] bg-surface p-4 shadow-hairline">
      {expandable ? (
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="block w-full">
          {header}
        </button>
      ) : (
        header
      )}
      {expandable && (
        <div
          className={`grid transition-[grid-template-rows] duration-220 ease-out ${open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}
          style={{ transitionTimingFunction: "cubic-bezier(0.23,1,0.32,1)" }}
        >
          <div className="overflow-hidden">
            <div className="mt-3 border-t border-line pt-3">
              {prob !== null && <WinProb home={game.home} away={game.away} prob={prob} />}
              <div className="mt-3 space-y-2">
                {game.awayForm && game.awayForm.length > 0 && (
                  <div className="flex flex-wrap items-center justify-between gap-y-1">
                    <span className="text-[12px] text-ink-3">{game.away} last 10</span>
                    <FormChips form={game.awayForm} />
                  </div>
                )}
                {game.homeForm && game.homeForm.length > 0 && (
                  <div className="flex flex-wrap items-center justify-between gap-y-1">
                    <span className="text-[12px] text-ink-3">{game.home} last 10</span>
                    <FormChips form={game.homeForm} />
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function fromBackend(row: GameRow): TonightGame {
  const away = row.VISITOR_TEAM_ABBREVIATION ?? "?";
  const home = row.HOME_TEAM_ABBREVIATION ?? "?";
  const aPts = row.VISITOR_TEAM_PTS;
  const hPts = row.HOME_TEAM_PTS;
  const raw = row as Record<string, unknown>;
  return {
    id: String(raw.GAME_ID ?? `${away}-${home}`),
    away,
    home,
    time: row.GAME_STATUS_TEXT ?? "",
    score: aPts != null && hPts != null ? `${aPts} – ${hPts}` : undefined,
    expandable: false,
  };
}

export default function TonightView() {
  const [games, setGames] = useState<TonightGame[]>(sampleGames);
  const [live, setLive] = useState(false);
  const [label, setLabel] = useState(sampleLabel);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getToday()
      .then((rows) => {
        if (cancelled) return;
        if (rows.tonight.length > 0) {
          setGames(rows.tonight.map(fromBackend));
          setLive(true);
          setLabel(
            new Date().toLocaleDateString("en-US", {
              weekday: "short",
              month: "short",
              day: "numeric",
            }),
          );
        }
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="mx-auto w-full max-w-[760px] px-4 py-6 sm:px-8">
      <div className="flex items-baseline justify-between">
        <h1 className="text-[15px] font-semibold text-ink">
          Tonight
          {!live && <SampleBadge />}
        </h1>
        <span className="text-[12px] tabular-nums text-ink-3">
          {label} · {games.length} {games.length === 1 ? "game" : "games"}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
        {games.length > 0 ? (
          games.map((g) => <GameCard key={g.id} game={g} />)
        ) : (
          <div className="rounded-[10px] bg-surface p-8 text-center text-[13px] text-ink-3 shadow-hairline">
            {loading ? "Loading tonight's slate…" : "No games tonight."}
          </div>
        )}
      </div>
      {!live && (
        <p className="mt-3 font-mono text-[11px] text-ink-3">
          Sample slate — no games on the live schedule right now.
        </p>
      )}
    </div>
  );
}
