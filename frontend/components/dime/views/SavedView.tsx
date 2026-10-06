"use client";

import { useMemo, useState } from "react";
import { savedThreads as seedThreads, type SavedThread } from "@/lib/dime-data-saved";

export default function SavedView() {
  const [threads, setThreads] = useState<SavedThread[]>(seedThreads);
  const [selected, setSelected] = useState<string | null>(seedThreads[0]?.id ?? null);
  const [query, setQuery] = useState("");

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return threads;
    return threads.filter(
      (t) => t.title.toLowerCase().includes(q) || t.preview.toLowerCase().includes(q)
    );
  }, [threads, query]);

  const remove = (id: string) => {
    setThreads((ts) => ts.filter((t) => t.id !== id));
    setSelected((s) => (s === id ? null : s));
  };

  const empty = threads.length === 0;

  return (
    <section className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-[14px] border border-line bg-page">
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-line px-4">
        <h1 className="text-[13.5px] font-medium text-ink">Saved</h1>
        {!empty && (
          <div className="flex h-8 w-56 items-center gap-1.5 rounded-[8px] bg-field px-2 text-ink-3 shadow-hairline focus-within:text-ink-2">
            <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth={2} strokeLinecap="round" aria-hidden className="shrink-0">
              <circle cx="11" cy="11" r="7" />
              <path d="M20 20l-3.5-3.5" />
            </svg>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search saved"
              aria-label="Search saved analyses"
              className="min-w-0 flex-1 bg-transparent text-[13px] text-ink outline-none placeholder:text-ink-3 [@media(pointer:coarse)]:text-[16px]"
            />
            {query && (
              <button
                type="button"
                aria-label="Clear search"
                onClick={() => setQuery("")}
                className="flex size-6 shrink-0 touch-manipulation select-none items-center justify-center rounded-[6px] text-ink-3 transition-colors duration-100 hover:bg-hover hover:text-ink"
              >
                <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth={2} strokeLinecap="round" aria-hidden>
                  <path d="M6 6l12 12M18 6L6 18" />
                </svg>
              </button>
            )}
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {empty ? (
          <div className="flex h-full flex-col items-center justify-center px-8 text-center">
            <p className="text-[13.5px] font-medium text-ink">Nothing saved yet</p>
            <p className="mt-1.5 max-w-[300px] text-[13px] leading-[1.5] text-ink-2">
              Save an analysis from any thread and it shows up here.
            </p>
          </div>
        ) : visible.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center px-8 text-center">
            <p className="text-[13.5px] font-medium text-ink">No matches</p>
            <p className="mt-1.5 max-w-[300px] text-[13px] leading-[1.5] text-ink-2">
              Nothing saved matches “{query.trim()}”.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-line">
            {visible.map((t) => {
              const active = t.id === selected;
              return (
                <li key={t.id}>
                  <div
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelected(t.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") setSelected(t.id);
                    }}
                    className={`group flex touch-manipulation cursor-pointer items-start gap-3 px-4 py-3 transition-colors duration-100 ${
                      active ? "bg-hover-2" : "hover:bg-hover"
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px] font-medium text-ink" title={t.title}>
                        {t.title}
                      </p>
                      <p className="mt-0.5 truncate text-[13px] text-ink-2" title={t.preview}>{t.preview}</p>
                      <p className="mt-1 font-mono text-[11px] text-ink-3">
                        {t.when} · {t.artifacts} {t.artifacts === 1 ? "artifact" : "artifacts"}
                      </p>
                    </div>
                    <button
                      type="button"
                      aria-label={`Delete ${t.title}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        remove(t.id);
                      }}
                      className="mt-0.5 flex size-7 shrink-0 touch-manipulation select-none items-center justify-center rounded-[8px] text-ink-3 opacity-0 transition-[opacity,background-color,color,transform] duration-150 hover:bg-hover hover:text-ink active:scale-[0.94] focus-visible:opacity-100 group-hover:opacity-100 [@media(hover:none)]:opacity-100"
                    >
                      <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor"
                        strokeWidth={2} strokeLinecap="round" aria-hidden>
                        <path d="M4 7h16M9 7V5a1 1 0 011-1h4a1 1 0 011 1v2m-9 0l1 13h10l1-13" />
                      </svg>
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
