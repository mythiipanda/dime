"use client";

import { useEffect, useState } from "react";

const KEY = "dime-compare-tray";
const EVT = "dime:compare-tray";

export function readTray(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function writeTray(names: string[]) {
  window.localStorage.setItem(KEY, JSON.stringify(names));
  window.dispatchEvent(new CustomEvent(EVT));
}

export function pinToTray(name: string): string[] {
  const cur = readTray();
  if (!cur.includes(name)) cur.push(name);
  writeTray(cur);
  return cur;
}

export default function CompareTray({
  onCompare,
  disabled,
}: {
  onCompare?: (names: string[]) => void;
  disabled?: boolean;
}) {
  const [names, setNames] = useState<string[]>([]);
  useEffect(() => {
    setNames(readTray());
    const sync = () => setNames(readTray());
    window.addEventListener(EVT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(EVT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  if (names.length === 0) return null;
  return (
    <div
      style={{
        position: "fixed",
        bottom: 96,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 40,
        display: "flex",
        alignItems: "center",
        gap: 8,
        flexWrap: "wrap",
        maxWidth: 640,
        padding: "8px 12px",
        borderRadius: 999,
        background: "var(--color-pure-white)",
        border: "1px solid var(--color-stone-border)",
        boxShadow: "0 6px 24px rgba(0, 0, 0, 0.10)",
      }}
    >
      <span
        style={{
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.08em",
          color: "var(--color-warm-gray)",
          textTransform: "uppercase",
        }}
      >
        Compare tray
      </span>
      {names.map((n) => (
        <span
          key={n}
          className="pill-ghost"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 12,
            padding: "2px 6px 2px 10px",
            background: "var(--color-sky-wash)",
          }}
        >
          {n}
          <button
            type="button"
            aria-label={`Remove ${n} from compare tray`}
            title={`Remove ${n}`}
            onClick={() => writeTray(readTray().filter((x) => x !== n))}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--color-warm-gray)",
              fontSize: 13,
              lineHeight: 1,
              padding: 2,
            }}
          >
            ×
          </button>
        </span>
      ))}
      <button
        type="button"
        className="pill-ghost interactive-tactile"
        style={{ fontSize: 12, padding: "3px 12px", fontWeight: 600 }}
        disabled={disabled || names.length < 2}
        title={names.length < 2 ? "Pin at least two players to compare" : `Compare ${names.join(" vs ")}`}
        onClick={() => onCompare?.(names)}
      >
        Compare {names.length >= 2 ? names.length : ""}
      </button>
      <button
        type="button"
        aria-label="Clear compare tray"
        title="Clear tray"
        onClick={() => writeTray([])}
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          color: "var(--color-warm-gray)",
          fontSize: 12,
          padding: 2,
        }}
      >
        Clear
      </button>
    </div>
  );
}
