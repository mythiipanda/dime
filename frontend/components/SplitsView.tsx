"use client";

import { asList, Bar, Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface SplitRow {
  split: string;
  gp: number;
  ppg: number | null;
  rpg: number | null;
  apg: number | null;
  fgPct: number | null;
  plusMinus: number | null;
  lowSample: boolean;
}

export interface SplitsRows {
  player: string;
  windowGames: number | null;
  splits: SplitRow[];
}

export function parseSplits(rows: unknown): SplitsRows | null {
  if (!isObj(rows)) return null;
  const splits = asList(rows.splits);
  if (!splits.length) return null;
  const out: SplitRow[] = [];
  for (const s of splits) {
    const split = str(s.split);
    const gp = num(s.gp);
    if (!split || gp === null) return null;
    out.push({
      split,
      gp: Math.round(gp),
      ppg: num(s.ppg),
      rpg: num(s.rpg),
      apg: num(s.apg),
      fgPct: num(s.fg_pct),
      plusMinus: num(s.plus_minus),
      lowSample: s.low_sample === true,
    });
  }
  return {
    player: str(rows.player),
    windowGames: num(rows.window_games),
    splits: out,
  };
}

export default function SplitsView({
  rows,
  meta,
}: {
  rows: unknown;
  meta?: { season?: string; low_sample_rule?: string; defense?: string };
}) {
  const parsed = parseSplits(rows);
  if (!parsed) return null;
  const maxPpg = Math.max(1, ...parsed.splits.map((s) => s.ppg ?? 0));

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap",
          marginBottom: 12,
        }}
      >
        <SectionTitle>
          {parsed.player ? `${parsed.player} splits` : "Matchup splits"}
        </SectionTitle>
        {parsed.windowGames !== null && (
          <Chip>last {parsed.windowGames} games</Chip>
        )}
        {meta?.season && <Chip>{meta.season}</Chip>}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {parsed.splits.map((s, i) => (
          <div
            key={`${s.split}-${i}`}
            style={{
              background: "var(--color-pure-white)",
              border: "1px solid var(--color-stone-border)",
              borderRadius: 10,
              padding: "10px 14px",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 8,
                marginBottom: 6,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  flexWrap: "wrap",
                }}
              >
                <span
                  style={{
                    fontWeight: 600,
                    fontSize: 13,
                    color: "var(--color-ink-black)",
                  }}
                >
                  {s.split}
                </span>
                {s.lowSample && <Chip>low sample</Chip>}
              </div>
              <span
                style={{ fontSize: 11, color: "var(--color-ash-gray)" }}
              >
                {s.gp} gp
              </span>
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
              }}
            >
              <span
                style={{
                  width: 64,
                  fontSize: 13,
                  fontWeight: 600,
                  color: s.lowSample
                    ? "var(--color-warm-gray)"
                    : "var(--color-cyan-edge)",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {s.ppg !== null ? s.ppg.toFixed(1) : "—"}
              </span>
              <div style={{ flex: 1 }}>
                <Bar
                  pct={((s.ppg ?? 0) / maxPpg) * 100}
                  color={s.lowSample ? "var(--color-stone-muted)" : undefined}
                />
              </div>
            </div>
            <div
              style={{
                display: "flex",
                gap: 12,
                marginTop: 6,
                fontSize: 11,
                color: "var(--color-ash-gray)",
                fontVariantNumeric: "tabular-nums",
                flexWrap: "wrap",
              }}
            >
              {s.rpg !== null && <span>{s.rpg.toFixed(1)} reb</span>}
              {s.apg !== null && <span>{s.apg.toFixed(1)} ast</span>}
              {s.fgPct !== null && <span>{(s.fgPct * 100).toFixed(1)}% FG</span>}
              {s.plusMinus !== null && (
                <span>
                  {s.plusMinus >= 0 ? "+" : ""}
                  {s.plusMinus.toFixed(1)}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
      {(meta?.low_sample_rule || meta?.defense) && (
        <div
          style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 4 }}
        >
          {meta.low_sample_rule && (
            <Caption>Low-sample flag: {meta.low_sample_rule}</Caption>
          )}
          {meta.defense && <Caption>Defense data: {meta.defense}</Caption>}
        </div>
      )}
    </div>
  );
}
