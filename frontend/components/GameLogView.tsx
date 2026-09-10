"use client";

import { asList, Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface GameLogMatch {
  date: string;
  opponent: string;
  matchup: string;
  home: boolean;
  pts: number;
  reb: number;
  ast: number;
  stl: number;
  blk: number;
  pra: number;
  plusMinus: number | null;
  wl: string;
  tripleDouble: boolean;
}

export interface GameLogGames {
  kind: "games";
  player: string;
  scope: string;
  filters: string[];
  total: number | null;
  capped: boolean;
  matches: GameLogMatch[];
}

export interface GameLogLeader {
  label: string;
  count: number;
}

export interface GameLogLeaders {
  kind: "leaders";
  wide: "league" | "team";
  scope: string;
  filters: string[];
  total: number | null;
  capped: boolean;
  leaders: GameLogLeader[];
}

export type GameLogRows = GameLogGames | GameLogLeaders;

function splitFilters(v: unknown): string[] {
  const s = str(v);
  if (!s || s === "all games") return [];
  return s
    .split(",")
    .map((b) => b.trim())
    .filter(Boolean);
}

function ddCount(pts: number, reb: number, ast: number, stl: number, blk: number): number {
  return [pts, reb, ast, stl, blk].filter((x) => x >= 10).length;
}

function parseMatch(m: Record<string, unknown>): GameLogMatch | null {
  const date = str(m.date);
  if (!date) return null;
  const pts = num(m.pts) ?? 0;
  const reb = num(m.reb) ?? 0;
  const ast = num(m.ast) ?? 0;
  const stl = num(m.stl) ?? 0;
  const blk = num(m.blk) ?? 0;
  return {
    date,
    opponent: str(m.opponent),
    matchup: str(m.matchup),
    home: m.home === true,
    pts,
    reb,
    ast,
    stl,
    blk,
    pra: pts + reb + ast,
    plusMinus: num(m.plus_minus),
    wl: str(m.wl).toUpperCase(),
    tripleDouble: ddCount(pts, reb, ast, stl, blk) >= 3,
  };
}

/** Thresholds recovered from the backend's filter description string. */
function parseThresholds(filters: string[]): { minPts: number | null; minPra: number | null; tdOnly: boolean } {
  let minPts: number | null = null;
  let minPra: number | null = null;
  let tdOnly = false;
  for (const f of filters) {
    const pra = f.match(/([\d.]+)\+\s*points\s*\+\s*rebounds\s*\+\s*assists/i);
    if (pra) {
      minPra = parseFloat(pra[1]);
      continue;
    }
    const pts = f.match(/([\d.]+)\+\s*points/i);
    if (pts) minPts = parseFloat(pts[1]);
    if (/triple-doubles?/i.test(f)) tdOnly = true;
  }
  return { minPts, minPra, tdOnly };
}

export function parseGameLogs(rows: unknown): GameLogRows | null {
  if (!isObj(rows)) return null;
  const scope = str(rows.scope) || "regular";
  const filters = splitFilters(rows.filters);
  const capped = rows.capped === true;
  if (rows.league_wide === true) {
    const leaders: GameLogLeader[] = [];
    for (const l of asList(rows.leaders)) {
      const label = str(l.player);
      const count = num(l.count);
      if (!label || count === null) return null;
      leaders.push({ label, count: Math.round(count) });
    }
    if (!leaders.length) return null;
    return {
      kind: "leaders",
      wide: "league",
      scope,
      filters,
      total: num(rows.total_players),
      capped,
      leaders,
    };
  }
  if (rows.team_wide === true) {
    const leaders: GameLogLeader[] = [];
    for (const l of asList(rows.leaders)) {
      const label = str(l.team_abbr) || str(l.team);
      const count = num(l.count);
      if (!label || count === null) return null;
      leaders.push({ label, count: Math.round(count) });
    }
    if (!leaders.length) return null;
    return {
      kind: "leaders",
      wide: "team",
      scope,
      filters,
      total: num(rows.total_teams),
      capped,
      leaders,
    };
  }
  if (!Array.isArray(rows.matches)) return null;
  const player = str(rows.player);
  if (!player && num(rows.player_id) === null) return null;
  const matches: GameLogMatch[] = [];
  for (const m of asList(rows.matches)) {
    const g = parseMatch(m);
    if (g) matches.push(g);
  }
  return {
    kind: "games",
    player,
    scope,
    filters,
    total: num(rows.total),
    capped,
    matches,
  };
}

function fmtDate(iso: string, withYear = false): string {
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    ...(withYear ? { year: "numeric" as const } : {}),
  });
}

function LeadersBody({ g }: { g: GameLogLeaders }) {
  const max = Math.max(1, ...g.leaders.map((l) => l.count));
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      {g.leaders.map((l, i) => (
        <div
          key={`${l.label}-${i}`}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "8px 14px",
            borderTop: i === 0 ? "none" : "1px solid var(--color-stone-border)",
          }}
        >
          <span
            style={{
              width: 22,
              fontSize: 11,
              color: "var(--color-ash-gray)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {i + 1}
          </span>
          <span
            style={{ flex: 1, fontSize: 13, fontWeight: 500, color: "var(--color-ink-black)" }}
          >
            {l.label}
          </span>
          <span
            style={{
              width: 72,
              height: 6,
              background: "var(--color-stone-border)",
              borderRadius: 3,
              overflow: "hidden",
            }}
          >
            <span
              style={{
                display: "block",
                width: `${(l.count / max) * 100}%`,
                height: "100%",
                background: "var(--color-cyan-signal)",
                borderRadius: 3,
              }}
            />
          </span>
          <span
            style={{
              width: 52,
              textAlign: "right",
              fontSize: 13,
              fontWeight: 600,
              color: "var(--color-cyan-edge)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {l.count}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function GameLogView({
  rows,
  meta,
}: {
  rows: unknown;
  meta?: { season?: string; coverage_note?: string };
}) {
  const g = parseGameLogs(rows);
  if (!g) return null;
  const { minPts, minPra, tdOnly } = parseThresholds(g.filters);
  const showPra = minPra !== null;
  const title =
    g.kind === "games"
      ? g.player
        ? `${g.player} game log`
        : "Game log"
      : g.wide === "league"
        ? "League leaders by game count"
        : "Teams by game count";

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
        {g.scope === "playoffs" && <Chip tone="accent">playoffs</Chip>}
        {g.filters.map((f, i) => (
          <Chip key={i} tone={i === 0 ? "accent" : "neutral"}>
            {f}
          </Chip>
        ))}
        {meta?.season && <Chip>{meta.season}</Chip>}
      </div>

      {g.kind === "games" ? (
        g.matches.length === 0 ? (
          <Caption>No games match these filters.</Caption>
        ) : (
          <>
            {(minPts !== null || minPra !== null || tdOnly) && (
              <Caption>cyan = cleared the filter</Caption>
            )}
          <div
            style={{
              background: "var(--color-pure-white)",
              border: "1px solid var(--color-stone-border)",
              borderRadius: 10,
              marginTop: 8,
            }}
          >
            {g.matches.map((m, i) => {
              const keyNum = showPra ? m.pra : m.pts;
              const keyTh = showPra ? minPra : minPts;
              const hit = keyTh === null || keyNum >= keyTh;
              return (
                <div
                  key={`${m.date}-${i}`}
                  className="gamelog-row"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "8px 14px",
                    borderTop: i === 0 ? "none" : "1px solid var(--color-stone-border)",
                    fontVariantNumeric: "tabular-nums",
                    opacity: hit ? 1 : 0.55,
                  }}
                >
                  <span style={{ width: 56, fontSize: 12, color: "var(--color-warm-gray)" }}>
                    {fmtDate(m.date, !!meta?.season)}
                  </span>
                  <span style={{ width: 64, fontSize: 12, color: "var(--color-ink-black)" }}>
                    {m.home ? "vs " : "@ "}
                    {m.opponent || "—"}
                  </span>
                  <span
                    style={{
                      width: 18,
                      fontSize: 11,
                      fontWeight: 600,
                      color: "var(--color-warm-gray)",
                    }}
                  >
                    {m.wl || ""}
                  </span>
                  <span
                    style={{
                      fontSize: 14,
                      fontWeight: 600,
                      color: hit ? "var(--color-cyan-edge)" : "var(--color-ink-black)",
                    }}
                  >
                    {showPra ? m.pra.toFixed(0) : m.pts.toFixed(0)}
                  </span>
                  <span style={{ fontSize: 11, color: "var(--color-ash-gray)" }}>
                    {showPra ? "PRA" : "PTS"}
                  </span>
                  <span
                    className="gamelog-details"
                    style={{ flex: 1, minWidth: 0, fontSize: 12, color: "var(--color-warm-gray)" }}
                  >
                    {m.pts.toFixed(0)} pts · {m.reb.toFixed(0)} reb · {m.ast.toFixed(0)} ast ·{" "}
                    {m.stl.toFixed(0)} stl · {m.blk.toFixed(0)} blk
                    {m.plusMinus !== null &&
                      ` · ${m.plusMinus >= 0 ? "+" : ""}${m.plusMinus.toFixed(0)} +/-`}
                  </span>
                  {(m.tripleDouble || tdOnly) && m.tripleDouble && (
                    <Chip tone="accent" title="Triple-double">
                      TD
                    </Chip>
                  )}
                </div>
              );
            })}
          </div>
          </>
        )
      ) : (
        <div
          style={{
            background: "var(--color-pure-white)",
            border: "1px solid var(--color-stone-border)",
            borderRadius: 10,
          }}
        >
          <LeadersBody g={g} />
        </div>
      )}

      <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 4 }}>
        {g.total !== null && (
          <Caption>
            {(() => {
              const shown = g.kind === "games" ? g.matches.length : g.leaders.length;
              return (
                <>
                  {g.total !== shown ? `showing ${shown} of ${g.total} ` : `${g.total} `}
                  {g.kind === "games" ? (g.total === 1 ? "game" : "games") : "entries"}
                  {g.capped ? " (capped at limit)" : ""}
                </>
              );
            })()}
          </Caption>
        )}
        {meta?.coverage_note && <Caption>{meta.coverage_note}</Caption>}
      </div>
    </div>
  );
}
