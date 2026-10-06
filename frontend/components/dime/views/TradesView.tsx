"use client";

import { useState } from "react";
import { tradeTeams } from "../../../lib/dime-data-trades";

const money = (v: number) => `$${v.toFixed(1)}M`;

function Check({ on }: { on: boolean }) {
  return (
    <span className={`flex size-5 shrink-0 items-center justify-center rounded-[6px] border transition-colors duration-100 ${on ? "border-ink bg-ink text-[var(--surface)]" : "border-line-strong text-transparent"}`}>
      <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d="M20 6 9 17l-5-5" />
      </svg>
    </span>
  );
}

function TeamSection({
  abbr,
  setAbbr,
  otherAbbr,
  picked,
  setPicked,
}: {
  abbr: string;
  setAbbr: (a: string) => void;
  otherAbbr: string;
  picked: string[];
  setPicked: (p: string[]) => void;
}) {
  const team = tradeTeams.find((t) => t.abbr === abbr)!;
  const total = picked.reduce((s, n) => s + team.players.find((p) => p.name === n)!.salary, 0);

  return (
    <section aria-label={`${team.name} roster`}>
      <div className="flex items-center justify-between px-1">
        <div className="flex flex-wrap items-center gap-0.5" role="group" aria-label="Pick a team">
          {tradeTeams
            .filter((t) => t.abbr !== otherAbbr)
            .map((t) => (
              <button
                key={t.abbr}
                type="button"
                onClick={() => { setAbbr(t.abbr); setPicked([]); }}
                aria-pressed={t.abbr === abbr}
                className={`h-7 rounded-[7px] px-2 font-mono text-[11px] transition-[background-color,color,transform] duration-150 active:scale-[0.96] ${
                  t.abbr === abbr ? "bg-hover font-medium text-ink" : "text-ink-3 hover:text-ink-2"
                }`}
              >
                {t.abbr}
              </button>
            ))}
        </div>
        <span className="font-mono text-[12px] tabular-nums text-ink-2">{money(total)}</span>
      </div>
      <div className="mt-1 divide-y divide-line overflow-hidden rounded-card bg-surface shadow-hairline">
        {team.players.map((p) => {
          const on = picked.includes(p.name);
          return (
            <button
              key={p.name}
              type="button"
              onClick={() => setPicked(on ? picked.filter((x) => x !== p.name) : [...picked, p.name])}
              aria-pressed={on}
              className="flex h-11 w-full select-none items-center gap-2.5 px-3 text-left transition-colors duration-100 hover:bg-hover"
            >
              <Check on={on} />
              <span className="min-w-0 flex-1 truncate text-[13px] text-ink">{p.name}</span>
              <span className="shrink-0 font-mono text-[12px] tabular-nums text-ink-2">{money(p.salary)}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

export default function TradesView() {
  const [aAbbr, setAAbbr] = useState("DAL");
  const [bAbbr, setBAbbr] = useState("NYK");
  const [aPicked, setAPicked] = useState<string[]>([]);
  const [bPicked, setBPicked] = useState<string[]>([]);

  const aTeam = tradeTeams.find((t) => t.abbr === aAbbr)!;
  const bTeam = tradeTeams.find((t) => t.abbr === bAbbr)!;
  const aOut = aPicked.reduce((s, n) => s + aTeam.players.find((p) => p.name === n)!.salary, 0);
  const bOut = bPicked.reduce((s, n) => s + bTeam.players.find((p) => p.name === n)!.salary, 0);

  const empty = aOut === 0 && bOut === 0;
  const aOk = bOut <= aOut * 1.25 + 0.25;
  const bOk = aOut <= bOut * 1.25 + 0.25;
  const legal = !empty && aOk && bOk;

  const line = (abbr: string, out: number, back: number) => {
    if (out === 0 && back === 0) return `${abbr} sends nothing yet`;
    if (out === 0) return `${abbr} sends nothing, takes back ${money(back)}`;
    const pct = Math.round((back / out) * 100);
    return `${abbr} sends ${money(out)}, takes back ${money(back)} (${pct}%)`;
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-11 shrink-0 items-center border-b border-line px-4">
        <span className="text-[13px] font-semibold text-ink">Trades</span>
      </div>

      <div className="flex h-11 shrink-0 items-center justify-between gap-2 border-b border-line bg-page px-4">
        <span className="min-w-0 flex-1 truncate font-mono text-[12px] tabular-nums text-ink-2">
          {aAbbr} {money(aOut)}
        </span>
        {empty ? (
          <span className="shrink-0 font-mono text-[11px] text-ink-3">pick players below</span>
        ) : legal ? (
          <span className="shrink-0 text-[12.5px] font-medium text-green">Inside the 125% band</span>
        ) : (
          <span className="shrink-0 text-[12.5px] font-medium text-red">Outside the band</span>
        )}
        <span className="min-w-0 flex-1 truncate text-right font-mono text-[12px] tabular-nums text-ink-2">
          {money(bOut)} {bAbbr}
        </span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-[640px] flex-col gap-5 px-4 py-4">
          <TeamSection abbr={aAbbr} setAbbr={setAAbbr} otherAbbr={bAbbr} picked={aPicked} setPicked={setAPicked} />
          <TeamSection abbr={bAbbr} setAbbr={setBAbbr} otherAbbr={aAbbr} picked={bPicked} setPicked={setBPicked} />

          {!empty && (
            <div className="flex flex-col gap-1.5 px-1">
              <span className="font-mono text-[12px] tabular-nums text-ink-2">{line(aAbbr, aOut, bOut)}</span>
              <span className="font-mono text-[12px] tabular-nums text-ink-2">{line(bAbbr, bOut, aOut)}</span>
              <button
                type="button"
                onClick={() => { setAPicked([]); setBPicked([]); }}
                className="mt-1 h-7 w-fit shrink-0 select-none rounded-[7px] px-3 text-[12px] font-medium text-ink-3 transition-[background-color,color,transform] duration-150 hover:bg-hover hover:text-ink active:scale-[0.96]"
              >
                Clear picks
              </button>
            </div>
          )}

          <p className="px-1 font-mono text-[11px] leading-[1.6] text-ink-3">
            Each side can take back up to 125% of the salary it sends, plus $250k.
            This is a rough check, not the full cap rules.
          </p>
        </div>
      </div>
    </div>
  );
}
