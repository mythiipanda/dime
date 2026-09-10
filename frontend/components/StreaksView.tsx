"use client";

import { asList, Bar, Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface StreakEntry {
  holder: string;
  streak: number;
  startDate: string;
  endDate: string;
  active: boolean;
}

export interface StreaksRows {
  streaks: StreakEntry[];
  count: number | null;
}

export function parseStreaks(rows: unknown): StreaksRows | null {
  if (!isObj(rows)) return null;
  const list = asList(rows.streaks);
  if (!list.length) return null;
  const streaks: StreakEntry[] = [];
  for (const s of list) {
    const holder = str(s.holder);
    const streak = num(s.streak);
    if (!holder || streak === null) return null;
    streaks.push({
      holder,
      streak: Math.round(streak),
      startDate: str(s.start_date),
      endDate: str(s.end_date),
      active: s.active === true,
    });
  }
  return { streaks, count: num(rows.count) };
}

export default function StreaksView({
  rows,
  meta,
}: {
  rows: unknown;
  meta?: {
    season?: string;
    mode?: string;
    stat?: string;
    scope?: string;
    threshold?: number;
  };
}) {
  const parsed = parseStreaks(rows);
  if (!parsed) return null;
  const maxStreak = Math.max(1, ...parsed.streaks.map((s) => s.streak));
  const mode = (meta?.mode || "longest").toLowerCase();
  const title = `${mode === "active" ? "Active" : "Longest"} ${meta?.stat || "stat"} streaks`;

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
        <SectionTitle>{title}</SectionTitle>
        {meta?.season && <Chip>{meta.season}</Chip>}
        {meta?.scope && <Chip>{meta.scope}</Chip>}
        {meta?.threshold != null && <Chip>min {meta.threshold}/game</Chip>}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {parsed.streaks.map((s, i) => {
          const dates = [s.startDate, s.endDate].filter(Boolean).join(" – ");
          return (
            <div
              key={`${s.holder}-${i}`}
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
                  style={{ display: "flex", alignItems: "center", gap: 8 }}
                >
                  <span
                    style={{
                      fontSize: 11,
                      color: "var(--color-ash-gray)",
                      fontVariantNumeric: "tabular-nums",
                      minWidth: 20,
                    }}
                  >
                    {i + 1}.
                  </span>
                  <span
                    style={{
                      fontWeight: 600,
                      fontSize: 13,
                      color: "var(--color-ink-black)",
                    }}
                  >
                    {s.holder}
                  </span>
                  {s.active && <Chip tone="accent">active</Chip>}
                </div>
                {dates && (
                  <span
                    style={{ fontSize: 11, color: "var(--color-ash-gray)" }}
                  >
                    {dates}
                  </span>
                )}
              </div>
              <div
                style={{ display: "flex", alignItems: "center", gap: 12 }}
              >
                <span
                  style={{
                    width: 48,
                    fontSize: 15,
                    fontWeight: 600,
                    color:
                      i === 0
                        ? "var(--color-cyan-edge)"
                        : "var(--color-ink-black)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {s.streak}
                </span>
                <div style={{ flex: 1 }}>
                  <Bar
                    pct={(s.streak / maxStreak) * 100}
                    color={
                      i === 0 ? undefined : "var(--color-stone-muted)"
                    }
                  />
                </div>
                <span
                  style={{ fontSize: 11, color: "var(--color-ash-gray)" }}
                >
                  games
                </span>
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ marginTop: 10 }}>
        <Caption>
          Ranked by streak length. Active means the run includes the holder's
          latest game on record.
        </Caption>
      </div>
    </div>
  );
}
