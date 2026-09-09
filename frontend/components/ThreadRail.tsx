"use client";

import { useState } from "react";
import { ThreadInfo } from "../lib/api";

export default function ThreadRail({
  threads,
  active,
  onSelect,
  onNew,
  onHomeClick,
  onSearch,
}: {
  threads: ThreadInfo[];
  active: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onHomeClick?: () => void;
  onSearch?: () => void;
}) {
  const [filterQuery, setFilterQuery] = useState("");

  const filtered = filterQuery.trim()
    ? threads.filter((t) => (t.title || t.id).toLowerCase().includes(filterQuery.toLowerCase()))
    : threads;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        padding: "16px 12px",
        background: "var(--color-stone-canvas)",
        borderRight: "1px solid var(--color-stone-border)",
        boxSizing: "border-box",
        justifyContent: "flex-start",
        gap: 12,
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 10, minHeight: 0, flex: 1 }}>
        {/* Brand & Action Top Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 4px" }}>
          <button
            type="button"
            onClick={onHomeClick}
            className="interactive-tactile"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              background: "none",
              border: "none",
              padding: "2px 4px",
              cursor: "pointer",
            }}
            title="Return to Home"
          >
            <span style={{ fontWeight: 600, fontSize: 16, letterSpacing: "-0.02em", color: "var(--color-ink-black)" }}>
              Dime
            </span>
          </button>
          {onSearch && (
            <button
              type="button"
              onClick={onSearch}
              className="pill-ghost interactive-tactile"
              style={{ padding: "4px 8px", fontSize: 12, display: "flex", alignItems: "center", gap: 4 }}
              title="Search commands and players"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </button>
          )}
        </div>

        {/* New Session Button */}
        <button
          type="button"
          onClick={onNew}
          className="interactive-tactile"
          style={{
            fontSize: 13,
            fontWeight: 500,
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 12px",
            background: "var(--color-pure-white)",
            border: "1px solid var(--color-stone-border)",
            borderRadius: 8,
            boxShadow: "0 1px 2px rgba(0, 0, 0, 0.04)",
            cursor: "pointer",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--color-ink-black)" }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>New session</span>
          </div>
          <span
            style={{
              fontSize: 10,
              color: "var(--color-ash-gray)",
              fontFamily: "monospace",
              background: "var(--color-stone-canvas)",
              padding: "1px 5px",
              borderRadius: 4,
              border: "1px solid var(--color-stone-border)",
            }}
          >
            ⌘N
          </span>
        </button>

        {/* Recents Section */}
        <div style={{ marginTop: 6, display: "flex", flexDirection: "column", minHeight: 0, flex: 1 }}>
          <div
            style={{
              fontSize: 12,
              fontWeight: 500,
              color: "var(--color-warm-gray)",
              padding: "0 6px",
              marginBottom: 8,
            }}
          >
            Recent sessions
          </div>

          <div style={{ padding: "0 2px 8px" }}>
            <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                style={{ position: "absolute", left: 8, color: "var(--color-ash-gray)", pointerEvents: "none" }}
              >
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                className="field"
                placeholder="Search history..."
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
                style={{
                  fontSize: 12,
                  padding: "5px 8px 5px 26px",
                  width: "100%",
                  boxSizing: "border-box",
                  borderRadius: 6,
                  height: 28,
                  background: "var(--color-pure-white)",
                }}
              />
            </div>
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 2,
              overflowY: "auto",
              flex: 1,
              paddingRight: 2,
            }}
          >
            {filtered.map((t) => {
              const isSelected = active === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => onSelect(t.id)}
                  className="interactive-tactile"
                  style={{
                    textAlign: "left",
                    borderRadius: 6,
                    padding: "6px 8px",
                    fontSize: 13,
                    background: isSelected ? "var(--color-pure-white)" : "transparent",
                    border: isSelected ? "1px solid var(--color-stone-border)" : "1px solid transparent",
                    boxShadow: isSelected ? "0 1px 2px rgba(0, 0, 0, 0.04)" : "none",
                    cursor: "pointer",
                    width: "100%",
                    color: isSelected ? "var(--color-ink-black)" : "var(--color-warm-gray)",
                  }}
                >
                  <div
                    style={{
                      fontWeight: isSelected ? 500 : 400,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {t.title || t.id}
                  </div>
                </button>
              );
            })}

            {!filtered.length && (
              <div style={{ fontSize: 12, color: "var(--color-ash-gray)", padding: "12px 6px" }}>
                {filterQuery ? "No matching sessions" : "No recent sessions"}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
