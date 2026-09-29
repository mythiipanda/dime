// Live mini-summaries for the Explore overview index cards (redesign brief
// Phase B). Pure derivation helpers, kept separate from the component so they
// stay unit-testable. Every numeral comes from warehouse rows — nothing is
// hardcoded.





export interface LeaderLine {
  rank: number;
  name: string;
  value: string;
}

export function formatStat(v: number): string {
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}
/** Top-n leaders for a stat column, sorted by value desc. */


export function topLeaders(
  rows: Record<string, unknown>[],
  stat: string,
  n = 3,
): LeaderLine[] {
  const scored = rows
    .map((r) => {
      const name = String(r.PLAYER_NAME ?? r.PLAYER ?? r.player_name ?? "").trim();
      const raw = r[stat] ?? r[stat.toLowerCase()];
      const value = typeof raw === "number" ? raw : NaN;
      return { name, value };
    })
    .filter((r) => r.name.length > 0 && Number.isFinite(r.value));
  scored.sort((a, b) => (b.value as number) - (a.value as number));
  return scored.slice(0, n).map((r, i) => ({
    rank: i + 1,
    name: r.name,
    value: formatStat(r.value as number),
  }));
}

export interface PlayoffResult {
  champion: string;
  runnerUp: string;
  series: string;
}
/**
 * Decided Finals winner from playoffs game rows (game ids carry the round at
 * chars 6-7; "04" is the Finals). Null when no team has 4 Finals wins.
 */


export function playoffChampion(
  rows: Record<string, unknown>[],
): PlayoffResult | null {
  const finals = rows.filter(
    (r) => String(r.GAME_ID || "").slice(6, 8) === "04",
  );
  const wins: Record<string, { name: string; w: number }> = {};
  for (const r of finals) {
    const ab = String(r.TEAM_ABBREVIATION || "");
    if (!ab) continue;
    wins[ab] = wins[ab] || { name: String(r.TEAM_NAME || ab), w: 0 };
    if (String(r.WL) === "W") wins[ab].w += 1;
  }
  const teams = Object.values(wins).sort((a, b) => b.w - a.w);
  if (teams.length < 2 || teams[0].w < 4) return null;
  return {
    champion: teams[0].name,
    runnerUp: teams[1].name,
    series: `${teams[0].w}-${teams[1].w}`,
  };
}
/** Distinct playoff games in the warehouse (0 when the table is empty). */


export function countPlayoffGames(rows: Record<string, unknown>[]): number {
  return new Set(
    rows.map((r) => String(r.GAME_ID || "")).filter((id) => id.length > 0),
  ).size;
}
/** One-line card summary from combine rows; null when nothing is there. */


export function combineSummary(
  rows: Record<string, unknown>[],
  draftYear: string,
): string | null {
  if (!rows.length) return null;
  return `${rows.length} prospects · ${draftYear} class`;
}
/**
 * Shots card headline for one player: shot count from the warehouse.
 * Null when there is no name or nothing charted.
 */


export function shotsHeadline(name: string, count: number): string | null {
  const label = String(name || "").trim();
  if (!label || !Number.isFinite(count) || count <= 0) return null;
  return `${label} · ${Math.round(count)} shots charted`;
}
/** "LeBron James" -> "L. James". Shared with the Lineups panel. */


export function shortPlayerName(full: string): string {
  const p = String(full || "").trim().split(/\s+/).filter(Boolean);
  return p.length > 1 ? `${p[0][0]}. ${p.slice(-1)}` : String(full || "").trim();
}

export interface LineupHeadlineRow {
  GROUP_NAME?: unknown;
  MIN?: unknown;
}
/**
 * Lineups card headline for the default team: most-used unit and its
 * minutes. Null when no lineup rows arrived.
 */


export function lineupsHeadline(
  teamAbbr: string,
  rows: LineupHeadlineRow[],
): string | null {
  if (!teamAbbr || !rows.length) return null;
  const sorted = [...rows].sort(
    (a, b) => Number(b.MIN ?? 0) - Number(a.MIN ?? 0),
  );
  const top = sorted[0];
  const names = String(top.GROUP_NAME ?? "")
    .split(" - ")
    .map(shortPlayerName)
    .filter(Boolean)
    .join(", ");
  const min = Number(top.MIN ?? 0);
  if (!names || !Number.isFinite(min) || min <= 0) return null;
  return `${teamAbbr} · ${names} · ${min.toFixed(0)} min`;
}

export interface TradeHeadlineSide {
  team?: unknown;
  payroll?: unknown;
}

export interface TradeHeadlineVerdict {
  team_a?: TradeHeadlineSide;
  team_b?: TradeHeadlineSide;
}

function millions(n: unknown): string | null {
  if (typeof n !== "number" || !Number.isFinite(n)) return null;
  return `$${(n / 1_000_000).toFixed(1)}M`;
}
/**
 * Trade card headline from a trade/check verdict: both sides' payrolls.
 * Null when either side is missing payroll data.
 */


export function tradeHeadline(v: TradeHeadlineVerdict | null | undefined): string | null {
  const a = v?.team_a;
  const b = v?.team_b;
  const teamA = typeof a?.team === "string" ? a.team : "";
  const teamB = typeof b?.team === "string" ? b.team : "";
  const payA = millions(a?.payroll);
  const payB = millions(b?.payroll);
  if (!teamA || !teamB || !payA || !payB) return null;
  return `${teamA} ${payA} · ${teamB} ${payB}`;
}

export interface DatasetResult {
  ok: boolean;
  data?: unknown[];
}
/**
 * Deferred live summaries for the cards that need a context first
 * (Phase 3). Each callback is wired by the component to existing
 * endpoints: the Shots headline resolves the leaders' #1 scorer and
 * counts their charted shots, Trade runs the default legality check,
 * Lineups reads the default team's units. Every callback is isolated,
 * so one failure never blanks the other cards.
 */


export interface IndexExtra {
  topScorerShots?: () => Promise<{ name: string; count: number } | null>;
  tradeCheck?: () => Promise<TradeHeadlineVerdict | null>;
  defaultLineups?: () => Promise<{ team: string; rows: LineupHeadlineRow[] } | null>;
}
/**
 * Live summaries for the Explore overview index cards. Each dataset fetch is
 * isolated: Promise.allSettled + per-result ok checks, so one rejected or
 * failed request never blanks the cards whose data arrived fine. A dataset
 * that fails or returns no usable rows simply leaves its card without a
 * summary (the card degrades to its label/blurb).
 */


export async function fetchIndexSummaries(
  fetch: (name: string, params: Record<string, string>) => Promise<DatasetResult>,
  season: string,
  extra?: IndexExtra,
): Promise<Record<string, string[]>> {
  const [ld, po, cb] = await Promise.allSettled([
    fetch("leaders", { season, stat: "PTS" }),
    fetch("playoffs", { season }),
    fetch("combine", { season: "2025" }),
  ]);
  const next: Record<string, string[]> = {};

  if (ld.status === "fulfilled" && ld.value.ok) {
    const lines = topLeaders(
      (ld.value.data || []) as Record<string, unknown>[],
      "PTS",
    ).map((l) => `${l.rank}. ${l.name} — ${l.value}`);
    if (lines.length) next.leaders = lines;
  }

  if (po.status === "fulfilled" && po.value.ok) {
    const prows = (po.value.data || []) as Record<string, unknown>[];
    const champ = playoffChampion(prows);
    if (champ) {
      next.playoffs = [
        `${champ.champion} · ${champ.series} over ${champ.runnerUp}`,
      ];
    } else {
      const n = countPlayoffGames(prows);
      if (n > 0) next.playoffs = [`${n} playoff games in the warehouse`];
    }
  }

  if (cb.status === "fulfilled" && cb.value.ok) {
    const s = combineSummary(
      (cb.value.data || []) as Record<string, unknown>[],
      "2025",
    );
    if (s) next.draft = [s];
  }
  // Phase 3 context cards, staggered after the parallel batch. Each is
  // isolated: a rejection or empty result leaves that card out.



  if (extra?.topScorerShots) {
    try {
      const s = await extra.topScorerShots();
      const h = s ? shotsHeadline(s.name, s.count) : null;
      if (h) next.shots = [h];
    } catch {

    }
  }
  if (extra?.tradeCheck) {
    try {
      const h = tradeHeadline(await extra.tradeCheck());
      if (h) next.trade = [h];
    } catch {

    }
  }
  if (extra?.defaultLineups) {
    try {
      const l = await extra.defaultLineups();
      const h = l ? lineupsHeadline(l.team, l.rows) : null;
      if (h) next.lineups = [h];
    } catch {

    }
  }

  return next;
}
