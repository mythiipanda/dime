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
