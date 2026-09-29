"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { resolveEntities, type ResolvePlayerRow, type ResolveTeamRow } from "../lib/api";
import {
  buildSearchItems,
  contextForResult,
  groupLabel,
  matchStats,
  placeSearchMenu,
  resultHint,
  type ExploreContext,
  type SearchResult,
} from "../lib/exploreSearch";













export default function ExploreSearch({
  onSelect,
  onAsk,
}: {
  onSelect: (ctx: ExploreContext, result: SearchResult) => void;
  onAsk: (question: string) => void;
}) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<{ players: ResolvePlayerRow[]; teams: ResolveTeamRow[] }>({
    players: [],
    teams: [],
  });
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const fieldRef = useRef<HTMLDivElement>(null);
  const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({});

  const needle = q.trim();

  useEffect(() => {
    if (needle.length < 2) {
      setHits({ players: [], teams: [] });
      setBusy(false);
      return;
    }
    setBusy(true);
    const t = setTimeout(async () => {
      try {
        setHits(await resolveEntities(needle, 4));
      } catch {
        setHits({ players: [], teams: [] });
      } finally {
        setBusy(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [needle]);

  const stats = useMemo(() => matchStats(needle), [needle]);

  const items: SearchResult[] = useMemo(
    () => buildSearchItems(hits.players, hits.teams, stats),
    [hits, stats],
  );

  useEffect(() => {
    setActive(0);
  }, [needle, hits.players.length, hits.teams.length, stats.length]);





  const showList = open && needle.length >= 2;
  useLayoutEffect(() => {
    if (!showList) return;
    const position = () => {
      if (!fieldRef.current) return;
      const r = fieldRef.current.getBoundingClientRect();
      setMenuStyle(
        placeSearchMenu(
          { top: r.top, bottom: r.bottom, left: r.left, width: r.width },
          { width: window.innerWidth, height: window.innerHeight },
        ),
      );
    };
    position();
    window.addEventListener("scroll", position, true);
    window.addEventListener("resize", position);
    return () => {
      window.removeEventListener("scroll", position, true);
      window.removeEventListener("resize", position);
    };
  }, [showList]);

  const groups = useMemo(() => {
    const order: SearchResult["kind"][] = ["player", "team", "stat"];
    return order.filter((k) => items.some((x) => x.kind === k));
  }, [items]);

  const pick = (r: SearchResult) => {
    onSelect(contextForResult(r), r);
    setOpen(false);
    setQ("");
  };

  const empty = showList && !busy && items.length === 0;

  return (
    <div className="explore-search">
      <div className="explore-search-row">
        <div className="explore-search-field" ref={fieldRef}>
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
          {createPortal(
            <div
              id="explore-search-results"
              className="explore-search-results"
              role="listbox"
              aria-label="Search results"
              style={{
                position: "fixed",
                right: "auto",
                left: menuStyle.left,
                width: menuStyle.width,
                maxHeight: menuStyle.maxHeight,
                top: menuStyle.top ?? "auto",
                bottom: menuStyle.bottom ?? "auto",
              }}
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
            </div>,
            document.body,
          )}
        </>
      )}
    </div>
  );
}
