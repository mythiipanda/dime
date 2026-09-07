"use client";

import { ThreadInfo } from "../lib/api";

export default function ThreadRail({
  threads,
  active,
  onSelect,
  onNew,
}: {
  threads: ThreadInfo[];
  active: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <button className="pill-cta" onClick={onNew} style={{ fontSize: 13 }}>
        New session
      </button>
      {threads.map((t) => (
        <button
          key={t.id}
          onClick={() => onSelect(t.id)}
          style={{
            textAlign: "left",
            borderRadius: 10,
            padding: "8px 12px",
            fontSize: 13,
            background: active === t.id ? "#ffffff" : "transparent",
            border: active === t.id ? "1px solid #e8e6e5" : "1px solid transparent",
          }}
        >
          <div style={{ fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {t.title || t.id}
          </div>
          <div style={{ fontSize: 11, color: "#a8a29e" }}>
            {String(t.updated).slice(0, 10)}
          </div>
        </button>
      ))}
      {!threads.length && (
        <div style={{ fontSize: 12, color: "#a8a29e" }}>
          Sessions appear here after the first question.
        </div>
      )}
    </div>
  );
}
