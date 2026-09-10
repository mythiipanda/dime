"use client";

import { asList, Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface HeadToHeadGame {
  date: string;
  matchup: string;
  home: boolean;
  pts: number;
  reb: number;
  ast: number;
  wl: string;
  plusMinus: number | null;
}

export interface HeadToHeadLine {
  gp: number;
  ppg: number | null;
  rpg: number | null;
  apg: number | null;
  fgPct: number | null;
  tsPct: number | null;
  w: number | null;
  l: number | null;
}

export interface HeadToHeadRows {
  player: string;
  playerTeam: string;
  opponent: string;
  opponentName: string;
  line: HeadToHeadLine;
  baseline: HeadToHeadLine | null;
  deltas: { ppg: number | null; rpg: number | null; apg: number | null };
  teamRecord: string;
  games: HeadToHeadGame[];
  smallSample: boolean;
  note: string;
}

function parseLine(v: unknown): HeadToHeadLine | null {
  if (!isObj(v)) return null;
  const gp = num(v.gp);
  if (gp === null) return null;
  return {
    gp: Math.round(gp),
    ppg: num(v.ppg),
    rpg: num(v.rpg),
    apg: num(v.apg),
    fgPct: num(v.fg_pct),
    tsPct: num(v.ts_pct),
    w: num(v.w) === null ? null : Math.round(num(v.w) as number),
    l: num(v.l) === null ? null : Math.round(num(v.l) as number),
  };
}

function unwrap(v: unknown): unknown {
  if (isObj(v) && isObj(v.rows)) return v.rows;
  return v;
}

export function parseHeadToHead(input: unknown): HeadToHeadRows | null {
  const v = unwrap(input);
  if (!isObj(v)) return null;
  const player = str(v.player);
  const opponent = str(v.opponent);
  const vs = parseLine(v.vs_opponent);
  if (!player || !opponent || !vs) return null;
  const games: HeadToHeadGame[] = [];
  for (const g of asList(v.games)) {
    const date = str(g.date);
    const matchup = str(g.matchup);
    if (!date && !matchup) continue;
    games.push({
      date,
      matchup,
      home: g.home === true,
      pts: num(g.pts) ?? 0,
      reb: num(g.reb) ?? 0,
      ast: num(g.ast) ?? 0,
      wl: str(g.wl).toUpperCase(),
      plusMinus: num(g.plus_minus),
    });
  }
  const baseline = parseLine(v.season_baseline);
  const d = isObj(v.deltas) ? v.deltas : {};
  const w = vs.w ?? 0;
  const l = vs.l ?? 0;
  return {
    player,
    playerTeam: str(v.player_team),
    opponent,
    opponentName: str(v.opponent_name),
    line: vs,
    baseline,
    deltas: { ppg: num(d.ppg), rpg: num(d.rpg), apg: num(d.apg) },
    teamRecord: str(v.team_record) || `${w}-${l}`,
    games,
    smallSample: v.small_sample === true,
    note: str(v.note),
  };
}

function fmtDate(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function fmtDelta(n: number | null): string {
  if (n === null) return "";
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}`;
}

export default function HeadToHeadView({
  rows,
  meta,
}: {
  rows: unknown;
  meta?: { season?: string; coverage_note?: string };
}) {
  const h = parseHeadToHead(rows);
  if (!h) return null;
  const homeGames = h.games.filter((g) => g.home);
  const awayGames = h.games.filter((g) => !g.home);
  const homeW = homeGames.filter((g) => g.wl === "W").length;
  const awayW = awayGames.filter((g) => g.wl === "W").length;
  const title = h.playerTeam
    ? `${h.player} vs ${h.opponent}`
    : `${h.player} vs ${h.opponent}`;

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
        {h.smallSample && <Chip tone="accent">small sample</Chip>}
      </div>

      <div
        style={{
          background: "var(--color-pure-white)",
          border: "1px solid var(--color-stone-border)",
          borderRadius: 10,
          padding: "14px",
          marginBottom: 8,
          textAlign: "center",
        }}
      >
        <div style={{ fontSize: 11, color: "var(--color-ash-gray)", marginBottom: 4 }}>
          Series record in these games
        </div>
        <div
          style={{
            fontSize: 22,
            fontWeight: 600,
            color: "var(--color-ink-black)",
            fontVariantNumeric: "tabular-nums",
            whiteSpace: "nowrap",
          }}
        >
          {h.playerTeam || "—"} {h.line.w ?? 0} - {h.line.l ?? 0}{" "}
          {h.opponent}
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            gap: 16,
            marginTop: 8,
            flexWrap: "wrap",
            fontSize: 12,
            color: "var(--color-warm-gray)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          <span>
            Home {homeW}-{homeGames.length - homeW}
          </span>
          <span>
            Away {awayW}-{awayGames.length - awayW}
          </span>
          <span>
            {h.line.gp} game{h.line.gp === 1 ? "" : "s"}
          </span>
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            gap: 16,
            marginTop: 8,
            flexWrap: "wrap",
            fontSize: 12,
            color: "var(--color-warm-gray)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {h.line.ppg !== null && (
            <span>
              <span
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: "var(--color-cyan-edge)",
                }}
              >
                {h.line.ppg.toFixed(1)}
              </span>{" "}
              ppg{fmtDelta(h.deltas.ppg) ? ` (${fmtDelta(h.deltas.ppg)})` : ""}
            </span>
          )}
          {h.line.rpg !== null && <span>{h.line.rpg.toFixed(1)} rpg</span>}
          {h.line.apg !== null && <span>{h.line.apg.toFixed(1)} apg</span>}
        </div>
      </div>

      {h.games.length === 0 ? (
        <Caption>No meetings on record.</Caption>
      ) : (
        <div
          style={{
            background: "var(--color-pure-white)",
            border: "1px solid var(--color-stone-border)",
            borderRadius: 10,
            overflowX: "auto",
          }}
        >
          <div style={{ minWidth: 300 }}>
            {h.games.map((g, i) => (
              <div
                key={`${g.date}-${i}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "8px 14px",
                  borderTop:
                    i === 0 ? "none" : "1px solid var(--color-stone-border)",
                  fontVariantNumeric: "tabular-nums",
                  minWidth: 0,
                }}
              >
                <span
                  style={{
                    width: 56,
                    flexShrink: 0,
                    fontSize: 12,
                    color: "var(--color-warm-gray)",
                  }}
                >
                  {fmtDate(g.date)}
                </span>
                <span
                  style={{
                    flex: 1,
                    minWidth: 0,
                    fontSize: 12,
                    color: "var(--color-ink-black)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {g.matchup || (g.home ? "vs" : "@")}
                </span>
                <span
                  style={{
                    flexShrink: 0,
                    fontSize: 12,
                    color: "var(--color-warm-gray)",
                  }}
                >
                  {g.pts.toFixed(0)} pts · {g.reb.toFixed(0)} reb ·{" "}
                  {g.ast.toFixed(0)} ast
                </span>
                <span
                  style={{
                    width: 18,
                    flexShrink: 0,
                    fontSize: 11,
                    fontWeight: 600,
                    color: "var(--color-warm-gray)",
                    textAlign: "right",
                  }}
                >
                  {g.wl}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 4 }}>
        {h.note && <Caption>{h.note}</Caption>}
        <Caption>
          {h.teamRecord} across {h.line.gp} game{h.line.gp === 1 ? "" : "s"}
          {h.baseline?.ppg != null && h.line.ppg != null
            ? ` · season ${h.baseline.ppg.toFixed(1)} ppg`
            : ""}
        </Caption>
        {meta?.coverage_note && <Caption>{meta.coverage_note}</Caption>}
      </div>
    </div>
  );
}
