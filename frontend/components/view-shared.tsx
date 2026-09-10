"use client";

import type { ReactNode } from "react";

export function num(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = parseFloat(v);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

export function str(v: unknown): string {
  return typeof v === "string" ? v : "";
}

export function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export function asList(v: unknown): Record<string, unknown>[] {
  return Array.isArray(v) ? v.filter(isObj) : [];
}

export function Bar({
  pct,
  color,
  height = 6,
}: {
  pct: number;
  color?: string;
  height?: number;
}) {
  const w = Math.max(0, Math.min(100, Number.isFinite(pct) ? pct : 0));
  return (
    <div
      style={{
        height,
        background: "var(--color-stone-border)",
        borderRadius: 3,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${w}%`,
          height: "100%",
          background: color ?? "var(--color-cyan-signal)",
          borderRadius: 3,
        }}
      />
    </div>
  );
}

export function Chip({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "accent";
}) {
  return (
    <span
      style={{
        display: "inline-block",
        fontSize: 11,
        fontWeight: 500,
        borderRadius: 9999,
        padding: "2px 10px",
        border: "1px solid var(--color-stone-border)",
        background:
          tone === "accent"
            ? "var(--color-sky-wash)"
            : "var(--color-stone-canvas)",
        color:
          tone === "accent"
            ? "var(--color-cyan-edge)"
            : "var(--color-warm-gray)",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <div
      className="display"
      style={{
        fontSize: 15,
        color: "var(--color-ink-black)",
        marginBottom: 10,
      }}
    >
      {children}
    </div>
  );
}

export function Caption({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        fontSize: 11,
        color: "var(--color-ash-gray)",
        lineHeight: 1.5,
      }}
    >
      {children}
    </div>
  );
}

const TITLE_TO_TOOL: Record<string, string> = {
  "Player comparison": "get_compare",
  "League leaders": "get_leaders",
  Lineups: "get_lineups",
  "Shot zones": "get_shot_zones",
  "Matchup splits": "get_matchup_splits",
  "Regression check": "get_regression_check",
  Comps: "get_comps",
  "Award race": "get_award_race",
  "Trade value": "get_trade_value",
  "Matchup preview": "get_matchup_preview",
  Streaks: "get_streaks",
  "Game Prediction": "get_game_prediction",
  "Game Logs": "search_game_logs",
  "Search Game Logs": "search_game_logs",
  "Rotation Check": "get_rotation_check",
};

function forwardTitle(tool: string): string {
  for (const [title, name] of Object.entries(TITLE_TO_TOOL)) {
    if (name === tool) return title;
  }
  if (tool.startsWith("get_")) {
    const rest = tool
      .slice(4)
      .split("_")
      .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
      .join(" ");
    if (rest) return rest;
  }
  return "";
}

export function resolveToolName(table: {
  tool?: string;
  title?: string;
}): string | undefined {
  if (table.tool) return table.tool;
  const raw = str(table.title).split(" · ")[0].trim();
  if (!raw || raw === "Dataset") return undefined;
  for (const [title, tool] of Object.entries(TITLE_TO_TOOL)) {
    if (title === raw) return tool;
  }
  if (/^[A-Z][A-Za-z]*(\s[A-Z][A-Za-z]*)*$/.test(raw)) {
    const candidate = "get_" + raw.toLowerCase().replace(/\s+/g, "_");
    if (forwardTitle(candidate) === raw) return candidate;
  }
  return undefined;
}
