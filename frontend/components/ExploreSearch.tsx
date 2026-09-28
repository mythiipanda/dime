"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { resolvePlayers, resolveTeams } from "../lib/api";
import { abbrForTeamId } from "../lib/teams";
import {
  contextForResult,
  groupLabel,
  matchStats,
  resultHint,
  type ExploreContext,
  type SearchResult,
} from "../lib/exploreSearch";

// Search-first header (redesign Phase 3). Structure adapts the repo's own
// CommandPalette pattern (grouped live results, arrow-key navigation,
// debounced /resolve calls) rendered inline instead of in a modal.
// Results are clickable: picking one opens the right panel with the
// query applied. Stat matches come from the Leaders categories;
// no pattern matching beyond case-insensitive substring.
export default function ExploreSearch({
  onSelect,
  onAsk,
}: {
  onSelect: (ctx: ExploreContext, result: SearchResult) => void;
  onAsk: (question: string) => void;
}) {
  const [q, setQ] = useState("");
  const [players, setPlayers] = useState<{ id: number; name: string }[]>([]);
  const [teams, setTeams] = useState<{ id: number; name: string; abbr: string | null }[]>([]);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);

  const needle = q.trim();

  useEffect(() => {
    if (needle.length < 2) {
      setPlayers([]);
      setTeams([]);
      setBusy(false);
      return;
    }
    setBusy(true);
    const t = setTimeout(async () => {
      try {
        const [p, tm] = await Promise.all([
          resolvePlayers(needle, 4),
          resolveTeams(needle, 4),
        ]);
        setPlayers(p);
        setTeams(
          tm.map((x) => ({
            ...x,
            abbr: x.abbr ?? abbrForTeamId(x.id),
          })),
        );
      } catch {
        setPlayers([]);
        setTeams([]);
      } finally {
        setBusy(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [needle]);

  const stats = useMemo(() => matchStats(needle), [needle]);

  const items: SearchResult[] = useMemo(
    () => [
      ...players.map((p): SearchResult => ({ kind: "player", id: p.id, name: p.name })),
      ...teams.map((x): SearchResult => ({ kind: "team", id: x.id, name: x.name, abbr: x.abbr })),
      ...stats,
    ],
    [players, teams, stats],
  );

  useEffect(() => {
    setActive(0);
  }, [needle, players.length, teams.length, stats.length]);

  const groups = useMemo(() => {
    const order: SearchResult["kind"][] = ["player", "team", "stat"];
    return order.filter((k) => items.some((x) => x.kind === k));
  }, [items]);

  const pick = (r: SearchResult) => {
    onSelect(contextForResult(r), r);
    setOpen(false);
    setQ("");
  };

  const showList = open && needle.length >= 2;
  const empty = showList && !busy && items.length === 0;

  return (
    <div className="explore-search" ref={boxRef}>
      <div className="explore-search-row">
        <div className="explore-search-field">
          <span aria-hidden="true" className="explore-search-icon">⌕</span>
          <input
            role="combobox"
            aria-expanded={showList}
            aria-controls="explore-search-results"
            aria-activedescendant={items[active] ? `explore-result-${active}` : undefined}
            aria-label="Search players, teams, and stats"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown" && items.length) {
                e.preventDefault();
                setActive((x) => Math.min(x + 1, items.length - 1));
              } else if (e.key === "ArrowUp" && items.length) {
                e.preventDefault();
                setActive((x) => Math.max(x - 1, 0));
              } else if (e.key === "Enter" && items[active]) {
                e.preventDefault();
                pick(items[active]);
              } else if (e.key === "Escape") {
                setOpen(false);
              }
            }}
            placeholder="Search players, teams, and stats"
          />
          {busy && <span className="explore-search-busy" aria-hidden="true" />}
        </div>
        <button
          type="button"
          className="explore-ask"
          onClick={() => onAsk("What is the most important NBA trend in the data right now?")}
        >
          Ask Dime
          <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <line x1="7" y1="17" x2="17" y2="7" />
            <polyline points="7 7 17 7 17 17" />
          </svg>
        </button>
      </div>

      {showList && (
        <>
          <div
            className="explore-search-dismiss"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div
            id="explore-search-results"
            className="explore-search-results"
            role="listbox"
            aria-label="Search results"
          >
            {groups.map((kind) => (
              <section key={kind}>
                <h2>{groupLabel(kind)}</h2>
                {items
                  .filter((x) => x.kind === kind)
                  .map((item) => {
                    const index = items.indexOf(item);
                    const label =
                      item.kind === "stat" ? item.stat : item.name;
                    return (
                      <button
                        id={`explore-result-${index}`}
                        key={`${item.kind}-${label}`}
                        type="button"
                        role="option"
                        aria-selected={index === active}
                        className={index === active ? "is-active" : ""}
                        onMouseEnter={() => setActive(index)}
                        onClick={() => pick(item)}
                      >
                        <span>{label}</span>
                        <small>{resultHint(item)}</small>
                      </button>
                    );
                  })}
              </section>
            ))}
            {empty && <div className="explore-search-empty">No matches</div>}
            {!empty && needle.length >= 2 && (
              <button
                type="button"
                className="explore-search-ask"
                onClick={() => {
                  setOpen(false);
                  onAsk(`Tell me about ${needle}`);
                }}
              >
                Ask Dime about {needle}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
