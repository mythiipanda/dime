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
import { TextField } from "./ds/TextField";
import { Button } from "./ds/Button";
import { Search, ArrowUpRight } from "iconoir-react";

























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
    <div className="relative mb-5">
      <div className="flex items-stretch gap-2">
        <div className="relative flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-line bg-surface px-3 focus-within:border-ink-3 focus-within:ring-2 focus-within:ring-hover" ref={fieldRef}>
          <Search aria-hidden="true" width={15} height={15} className="text-ink-3" />
          <TextField
            role="combobox"
            aria-expanded={showList}
            aria-controls="explore-search-results"
            aria-activedescendant={items[active] ? `explore-result-${active}` : undefined}
            aria-label="Search players, teams, and stats"
            className="w-full border-0 bg-transparent px-0 py-2.5 shadow-none focus-visible:outline-none"
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
          {busy && <span className="h-3 w-3 shrink-0 animate-spin rounded-full border-2 border-line border-t-ink-3 motion-reduce:animate-none" aria-hidden="true" />}
        </div>
        <Button
          type="button"
          size="sm"
          className="h-10 shrink-0 rounded-lg border border-line bg-surface"
          onClick={() => onAsk("What is the most important NBA trend in the data right now?")}
        >
          Ask Dime
          <ArrowUpRight width={13} height={13} />
        </Button>
      </div>

      {showList && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          {createPortal(
            <div
              id="explore-search-results"
              className="z-50 overflow-y-auto rounded-xl border border-line bg-surface p-1.5 shadow-float"
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
                <section key={kind} className="not-first:mt-1 not-first:border-t not-first:border-line not-first:pt-1">
                  <h2 className="px-2 py-1.5 text-[10px] font-medium uppercase tracking-wide text-ink-3">{groupLabel(kind)}</h2>
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
                          className={`grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-2 rounded-lg px-2 py-2 text-left text-[13px] hover:bg-hover ${index === active ? "bg-hover-2" : ""}`}
                          onMouseEnter={() => setActive(index)}
                          onClick={() => pick(item)}
                        >
                          <span className="truncate">{label}</span>
                          <small className="text-[11px] text-ink-3">{resultHint(item)}</small>
                        </button>
                      );
                    })}
                </section>
              ))}
              {empty && <div className="px-3 py-5 text-center text-[12px] text-ink-3">No matches</div>}
              {!empty && needle.length >= 2 && (
                <button
                  type="button"
                  className="mt-1 w-full rounded-lg border border-line px-2 py-2 text-left text-[12px] hover:bg-hover"
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
