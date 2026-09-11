"use client";

import { asList, Bar, Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface WpaLeader {
  rank: number | null;
  player: string;
  playerId: number | null;
  team: string;
  wpa: number | null;
  events: number | null;
  plusEvents: number | null;
  minusEvents: number | null;
  games: number | null;
}

export interface WpaMeta {
  season?: number;
  seasonLabel?: string;
  limit?: number;
  minEvents?: number;
  players?: number;
  games?: number;
  model?: string;
  source?: string;
  values?: string;
}

function parseLeader(r: Record<string, unknown>): WpaLeader | null {
  const player = str(r.player);
  const wpa = num(r.wpa);
  if (!player || wpa === null) return null;
  return {
    rank: num(r.rank),
    player,
    playerId: num(r.player_id),
    team: str(r.team),
    wpa,
    events: num(r.events),
    plusEvents: num(r.plus_events),
    minusEvents: num(r.minus_events),
    games: num(r.games),
  };
}

export function parseWpaLeaders(rows: unknown): { leaders: WpaLeader[] } | null {
  if (!isObj(rows)) return null;
  const leaders = asList(rows.leaders)
    .map(parseLeader)
    .filter((l): l is WpaLeader => l !== null);
  if (!leaders.length) return null;
  return { leaders };
}

function fmtWpa(v: number | null): string {
  if (v === null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(2)}`;
}

function WpaCard({
  leader,
  rank,
  maxWpa,
}: {
  leader: WpaLeader;
  rank: number;
  maxWpa: number;
}) {
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
            {[leader.team, leader.games !== null ? `${leader.games} games` : ""]
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
          {fmtWpa(leader.wpa)}
        </span>
      </div>
      <Bar pct={((leader.wpa ?? 0) / Math.max(maxWpa, 0.01)) * 100} />
      <div
        style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}
      >
        <Chip tone="accent">WPA {fmtWpa(leader.wpa)}</Chip>
        {leader.events !== null && <Chip>{leader.events} plays</Chip>}
        {leader.plusEvents !== null && leader.minusEvents !== null && (
          <Chip>
            +{leader.plusEvents} / -{leader.minusEvents}
          </Chip>
        )}
      </div>
    </div>
  );
}

export default function WpaView({
  rows,
  meta,
}: {
  rows: unknown;
  meta?: WpaMeta;
}) {
  const parsed = parseWpaLeaders(rows);
  if (!parsed) return null;
  const title = meta?.seasonLabel
    ? `WPA leaders ${meta.seasonLabel}`.trim()
    : "WPA leaders";
  const maxWpa = Math.max(...parsed.leaders.map((l) => l.wpa ?? 0), 0.01);

  return (
    <div>
      <SectionTitle>{title}</SectionTitle>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {parsed.leaders.map((l, i) => (
          <WpaCard
            key={`${l.playerId ?? l.player}-${i}`}
            leader={l}
            rank={l.rank ?? i + 1}
            maxWpa={maxWpa}
          />
        ))}
      </div>
      {(meta?.minEvents !== undefined ||
        meta?.model ||
        meta?.source ||
        meta?.values) && (
        <div
          style={{
            marginTop: 10,
            display: "flex",
            flexDirection: "column",
            gap: 4,
          }}
        >
          {meta?.minEvents !== undefined && (
            <Caption>Minimum {meta.minEvents} plays to qualify.</Caption>
          )}
          {meta?.model && <Caption>{meta.model}</Caption>}
          {meta?.source && <Caption>{meta.source}</Caption>}
          {meta?.values && <Caption>{meta.values}</Caption>}
        </div>
      )}
    </div>
  );
}
