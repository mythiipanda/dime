"use client";

import { asList, Bar, Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface HistoricalLeader {
  player: string;
  team: string;
  season: number | null;
  season_label: string;
  gp: number | null;
  value: number | null;
  display: string | null;
  raptor: number | null;
}

export interface HistoricalSeason {
  season: number | null;
  leaders: HistoricalLeader[];
}

export interface HistoricalLeadersMeta {
  label?: string;
  mode?: string;
  start_season?: number;
  end_season?: number;
  qualification?: string;
  source?: string;
  values?: string;
}

function parseLeader(r: Record<string, unknown>): HistoricalLeader | null {
  const player = str(r.player);
  const value = num(r.value);
  if (!player || value === null) return null;
  return {
    player,
    team: str(r.team),
    season: num(r.season),
    season_label: str(r.season_label),
    gp: num(r.gp),
    value,
    display: str(r.display) || null,
    raptor: num(r.raptor),
  };
}

export function parseHistoricalLeaders(
  rows: unknown,
): { seasons: HistoricalSeason[]; best: HistoricalLeader[] } | null {
  if (!isObj(rows)) return null;
  const seasons: HistoricalSeason[] = [];
  for (const s of asList(rows.seasons)) {
    const leaders = asList(s.leaders)
      .map(parseLeader)
      .filter((l): l is HistoricalLeader => l !== null);
    if (!leaders.length) continue;
    seasons.push({ season: num(s.season), leaders });
  }
  const best = asList(rows.leaders)
    .map(parseLeader)
    .filter((l): l is HistoricalLeader => l !== null);
  if (!seasons.length && !best.length) return null;
  return { seasons, best };
}

function LeaderCard({
  leader,
  rank,
  maxValue,
  unit,
}: {
  leader: HistoricalLeader;
  rank: number;
  maxValue: number;
  unit: string;
}) {
  const shown =
    leader.display ?? (leader.value !== null ? leader.value.toFixed(1) : "—");
  return (
    <div
      style={{
        background: "var(--color-pure-white)",
        border: "1px solid var(--color-stone-border)",
        borderRadius: 10,
        padding: "12px 16px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 8,
        }}
      >
        <span
          style={{
            width: 26,
            height: 26,
            borderRadius: "50%",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 12,
            fontWeight: 600,
            flexShrink: 0,
            background:
              rank === 1
                ? "var(--color-ink-black)"
                : "var(--color-stone-canvas)",
            color:
              rank === 1
                ? "var(--color-pure-white)"
                : "var(--color-warm-gray)",
            border: "1px solid var(--color-stone-border)",
          }}
        >
          {rank}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontWeight: 600,
              fontSize: 14,
              color: "var(--color-ink-black)",
            }}
          >
            {leader.player}
          </div>
          <div style={{ fontSize: 11, color: "var(--color-ash-gray)" }}>
            {[leader.team, leader.season_label || (leader.season ? `Season ${leader.season}` : "")]
              .filter(Boolean)
              .join(" · ")}
          </div>
        </div>
        <span
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "var(--color-cyan-edge)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {leader.value !== null ? shown : "—"}
        </span>
      </div>
      <Bar pct={((leader.value ?? 0) / Math.max(maxValue, 1)) * 100} />
      <div
        style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}
      >
        <Chip>
          {unit} {leader.value !== null ? shown : "—"}
        </Chip>
        {leader.gp !== null && <Chip>GP {leader.gp}</Chip>}
        {leader.raptor !== null && (
          <Chip tone="accent">RAPTOR {leader.raptor.toFixed(2)}</Chip>
        )}
      </div>
    </div>
  );
}

export default function HistoricalLeadersView({
  rows,
  meta,
}: {
  rows: unknown;
  meta?: HistoricalLeadersMeta;
}) {
  const parsed = parseHistoricalLeaders(rows);
  if (!parsed) return null;
  const unit = meta?.label || "value";
  const range =
    meta?.start_season && meta?.end_season
      ? `${meta.start_season}–${meta.end_season}`
      : "";
  const title =
    meta?.mode === "best"
      ? `Best ${unit} campaigns ${range}`.trim()
      : `League leaders in ${unit} ${range}`.trim();
  const all = [
    ...parsed.best,
    ...parsed.seasons.flatMap((s) => s.leaders),
  ];
  const maxValue = Math.max(...all.map((l) => l.value ?? 0), 1);

  return (
    <div>
      <SectionTitle>{title || "Historical leaders"}</SectionTitle>
      {parsed.best.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {parsed.best.map((l, i) => (
            <LeaderCard
              key={`${l.player}-${l.season}-${i}`}
              leader={l}
              rank={i + 1}
              maxValue={maxValue}
              unit={unit}
            />
          ))}
        </div>
      )}
      {parsed.seasons.map((s) => (
        <div key={s.season ?? "unknown"} style={{ marginTop: 14 }}>
          <div
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: "var(--color-ink-black)",
              marginBottom: 8,
            }}
          >
            {s.season ?? "Unknown season"}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {s.leaders.map((l, i) => (
              <LeaderCard
                key={`${l.player}-${i}`}
                leader={l}
                rank={i + 1}
                maxValue={maxValue}
                unit={unit}
              />
            ))}
          </div>
        </div>
      ))}
      {(meta?.qualification || meta?.source || meta?.values) && (
        <div
          style={{
            marginTop: 10,
            display: "flex",
            flexDirection: "column",
            gap: 4,
          }}
        >
          {meta.qualification && <Caption>{meta.qualification}</Caption>}
          {meta.source && <Caption>{meta.source}</Caption>}
          {meta.values && <Caption>{meta.values}</Caption>}
        </div>
      )}
    </div>
  );
}
