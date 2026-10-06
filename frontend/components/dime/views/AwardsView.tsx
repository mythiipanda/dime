"use client";

import { useState } from "react";
import { awardTabs } from "../../../lib/dime-data-awards";

function MoveDelta({ move }: { move: number }) {
  if (move === 0)
    return (
      <span className="w-12 shrink-0 text-right font-mono text-[12px] tabular-nums text-ink-3">–</span>
    );
  const good = move < 0;
  return (
    <span className={`w-12 shrink-0 text-right font-mono text-[12px] tabular-nums ${good ? "text-green" : "text-red"}`}>
      {good ? "-" : "+"}{Math.abs(move)}
    </span>
  );
}

export default function AwardsView() {
  const [tab, setTab] = useState(awardTabs[0].key);
  const active = awardTabs.find((t) => t.key === tab)!;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-11 shrink-0 items-center border-b border-line px-4">
        <span className="text-[13px] font-semibold text-ink">Awards</span>
      </div>

      <div className="flex shrink-0 items-center gap-1 overflow-x-auto px-4 pt-3">
        {awardTabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            aria-pressed={tab === t.key}
            className={`h-7 shrink-0 select-none rounded-[7px] px-2.5 text-[12.5px] font-medium transition-[background-color,color,transform] duration-150 active:scale-[0.96] ${
              tab === t.key ? "bg-hover text-ink" : "text-ink-3 hover:text-ink-2"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-3 min-h-0 flex-1 overflow-y-auto px-4 pb-8">
        <div
          key={active.key}
          className="divide-y divide-line overflow-hidden rounded-card bg-surface shadow-hairline"
          style={{ animation: "fade-up 180ms cubic-bezier(0.23,1,0.32,1) both" }}
        >
          {active.candidates.map((c, i) => (
            <div key={c.player} className="px-4 py-3">
              <div className="flex items-center gap-3">
                <span className="w-5 shrink-0 font-mono text-[12px] tabular-nums text-ink-3">{i + 1}</span>
                <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-ink" title={`${c.player} · ${c.team}`}>
                  {c.player}
                  <span className="ml-2 font-mono text-[11px] font-normal text-ink-3">{c.team}</span>
                </span>
                <span className="shrink-0 font-mono text-[12px] tabular-nums text-ink-2">{c.odds}</span>
                <MoveDelta move={c.move} />
              </div>
              <div className="mt-0.5 truncate pl-8 font-mono text-[11.5px] tabular-nums text-ink-3" title={c.line}>
                {c.line}
              </div>
            </div>
          ))}
        </div>
        <p className="mt-2 px-1 font-mono text-[11px] text-ink-3">
          Negative move means odds shortened. Mock board, not live lines.
        </p>
      </div>
    </div>
  );
}
