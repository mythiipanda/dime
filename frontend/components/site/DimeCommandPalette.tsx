"use client";

import { useEffect, useMemo, useRef, useState } from "react";

export type PaletteEntry = {
  id: string;
  label: string;
  kind: "view" | "action";
  run: () => void;
};

function fuzzy(hay: string, needle: string): boolean {
  const h = hay.toLowerCase();
  const n = needle.toLowerCase().trim();
  if (!n) return true;
  let j = 0;
  for (let i = 0; i < h.length && j < n.length; i++) {
    if (h[i] === n[j]) j++;
  }
  return j === n.length;
}

export default function DimeCommandPalette({
  open,
  entries,
  onClose,
}: {
  open: boolean;
  entries: PaletteEntry[];
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const prevFocus = useRef<Element | null>(null);

  const results = useMemo(() => {
    const views = entries.filter((e) => e.kind === "view" && fuzzy(e.label, query));
    const actions = entries.filter((e) => e.kind === "action" && fuzzy(e.label, query));
    return [...views, ...actions];
  }, [entries, query]);

  useEffect(() => {
    if (!open) return;
    prevFocus.current = document.activeElement;
    setQuery("");
    setActive(0);
    const t = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => {
      window.clearTimeout(t);
      (prevFocus.current as HTMLElement | null)?.focus?.();
    };
  }, [open ]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  useEffect(() => {
    const row = listRef.current?.querySelector<HTMLElement>(`[data-palette-index="${active}"]`);
    row?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!open) return null;

  const run = (e: PaletteEntry) => {
    onClose();
    e.run();
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => (results.length ? (a + 1) % results.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => (results.length ? (a - 1 + results.length) % results.length : 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const e2 = results[active];
      if (e2) run(e2);
    }
  };

  const firstAction = results.findIndex((r) => r.kind === "action");

  return (
    <div className="fixed inset-0 z-50 flex justify-center overflow-y-auto overscroll-contain px-4 pt-[16dvh]">
      <button
        type="button"
        aria-label="Close command palette"
        onClick={onClose}
        className="fixed inset-0 cursor-default bg-black/45 transition-opacity duration-150"
        style={{ animation: "fade-in 150ms ease-out both" }}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onKeyDown={onKey}
        className="relative mb-8 h-fit w-full max-w-[560px] overflow-hidden rounded-card border border-line bg-surface shadow-overlay"
        style={{ animation: "pop-in 150ms cubic-bezier(0.23,1,0.32,1) both" }}
      >
        <div className="flex h-12 items-center gap-2 border-b border-line px-3.5">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--ink-3)" strokeWidth="2" strokeLinecap="round" className="shrink-0">
            <circle cx="11" cy="11" r="7" />
            <path d="M21 21l-4.3-4.3" />
          </svg>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a view or action…"
            aria-label="Type a view or action"
            role="combobox"
            aria-expanded="true"
            aria-controls="dime-palette-list"
            aria-activedescendant={results.length ? `dime-palette-${active}` : undefined}
            className="min-w-0 flex-1 bg-transparent text-[13.5px] text-ink outline-none placeholder:text-ink-3 [@media(pointer:coarse)]:text-base"
          />
          <kbd className="shrink-0 rounded-[6px] bg-field px-1.5 py-0.5 font-mono text-[11px] text-ink-3 shadow-hairline">
            esc
          </kbd>
        </div>
        <div ref={listRef} id="dime-palette-list" role="listbox" aria-label="Views and actions" className="max-h-[46dvh] overflow-y-auto overscroll-contain p-1.5">
          {results.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-1 px-4 py-8">
              <span className="text-[13px] font-medium text-ink">No matches</span>
              <span className="text-[12px] text-ink-3">Try a view name like Lineups or an action like New analysis</span>
            </div>
          )}
          {results.map((e, i) => (
            <div key={e.id}>
              {i === firstAction && firstAction > 0 && <div aria-hidden className="mx-2 my-1 border-t border-line" />}
              {i === firstAction && (
                <div className="px-2.5 pb-0.5 pt-1.5 text-[12px] font-medium text-ink-3">Actions</div>
              )}
              {i === 0 && firstAction !== 0 && (
                <div className="px-2.5 pb-0.5 pt-1.5 text-[12px] font-medium text-ink-3">Views</div>
              )}
              <button
                type="button"
                role="option"
                id={`dime-palette-${i}`}
                aria-selected={i === active}
                data-palette-index={i}
                onClick={() => run(e)}
                onMouseMove={() => setActive(i)}
                className={`flex min-h-[40px] w-full touch-manipulation select-none items-center gap-2.5 rounded-[8px] px-2.5 text-left text-[13px] transition-[background-color,color] duration-100 [@media(pointer:coarse)]:min-h-[44px] ${
                  i === active ? "bg-hover-2 text-ink" : "text-ink-2"
                }`}
              >
                <span className="min-w-0 flex-1 truncate font-medium">{e.label}</span>
                {e.kind === "view" && (
                  <span className="shrink-0 font-mono text-[11px] text-ink-3">view</span>
                )}
              </button>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-3 border-t border-line px-3.5 py-2 font-mono text-[11px] text-ink-3">
          <span>↑↓ navigate</span>
          <span>↵ open</span>
          <span>esc close</span>
        </div>
      </div>
    </div>
  );
}
