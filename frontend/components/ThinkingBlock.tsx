"use client";

import { useEffect, useState } from "react";

interface Props {
  thoughts: string[];
  running: boolean;
  thoughtMs?: number;
  answerStarted: boolean;
}

export default function ThinkingBlock({ thoughts, running, thoughtMs, answerStarted }: Props) {
  const [open, setOpen] = useState(running);
  useEffect(() => {
    if (answerStarted || !running) setOpen(false);
  }, [answerStarted, running]);
  if (!thoughts.length) return null;
  const secs = thoughtMs ? (thoughtMs / 1000).toFixed(1) : null;
  return (
    <div style={{ marginBottom: 8 }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          padding: "3px 8px",
          background: "var(--color-stone-canvas)",
          border: "1px solid var(--color-stone-border)",
          borderRadius: 6,
          fontSize: 12,
          color: running ? "var(--color-ink-black)" : "var(--color-warm-gray)",
          fontWeight: running ? 500 : 400,
          cursor: "pointer",
        }}
      >
        {running ? "Thinking..." : secs ? `Thought for ${secs}s` : "Thought process"}
        <span style={{ fontSize: 9, opacity: 0.6 }}>{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div
          style={{
            marginTop: 6,
            background: "var(--color-stone-canvas)",
            border: "1px solid var(--color-stone-border)",
            borderRadius: 10,
            padding: "12px 14px",
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          {thoughts.map((t, i) => (
            <div key={i} style={{ fontSize: 12.5, lineHeight: 1.6, color: "var(--color-warm-gray)" }}>
              {t}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
