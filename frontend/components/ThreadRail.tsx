"use client";

import { ThreadInfo } from "../lib/api";

export default function ThreadRail({
  threads,
  active,
  onSelect,
  onNew,
  onSearch,
}: {
  threads: ThreadInfo[];
  active: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onSearch?: () => void;
}) {
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
        justifyContent: "space-between",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 12, minHeight: 0 }}>
        {/* Brand & Action Top Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 4px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: "var(--color-cyan-signal)",
                display: "inline-block",
              }}
            />
            <span style={{ fontWeight: 600, fontSize: 16, letterSpacing: "-0.01em" }}>Dime</span>
          </div>
          {onSearch && (
            <button
              onClick={onSearch}
              className="pill-ghost"
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
          className="pill-ghost"
          onClick={onNew}
          style={{
            fontSize: 13,
            fontWeight: 500,
            width: "100%",
            justifyContent: "flex-start",
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 12px",
            background: "var(--color-pure-white)",
            boxShadow: "var(--shadow-card)",
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          <span>New session</span>
        </button>

        {/* Recents Section */}
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", minHeight: 0, flex: 1 }}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 500,
              color: "var(--color-ash-gray)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              padding: "0 6px",
              marginBottom: 6,
            }}
          >
            Recents
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
            {threads.map((t) => (
              <button
                key={t.id}
                onClick={() => onSelect(t.id)}
                style={{
                  textAlign: "left",
                  borderRadius: 8,
                  padding: "7px 10px",
                  fontSize: 13,
                  background: active === t.id ? "var(--color-pure-white)" : "transparent",
                  border: active === t.id ? "1px solid var(--color-stone-border)" : "1px solid transparent",
                  boxShadow: active === t.id ? "var(--shadow-card)" : "none",
                  cursor: "pointer",
                  transition: "background 120ms ease",
                  width: "100%",
                  color: "var(--color-ink-black)",
                }}
              >
                <div
                  style={{
                    fontWeight: active === t.id ? 500 : 400,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {t.title || t.id}
                </div>
              </button>
            ))}

            {!threads.length && (
              <div style={{ fontSize: 12, color: "var(--color-ash-gray)", padding: "12px 6px" }}>
                No recent sessions
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
