// Search-first header helpers (redesign Phase 3). Pure functions kept
// separate from the component so they stay unit-testable.
//
// Result types mirror what the existing /resolve endpoint returns
// (players + teams); stat matches come from the stat categories the
// Leaders panel already offers. Matching is case-insensitive substring
// only. No regular expressions, no per-name special cases: every result
// of the same kind opens the same panel with the same context shape.

export interface PlayerResult {
  kind: "player";
  id: number;
  name: string;
}

export interface TeamResult {
  kind: "team";
  id: number;
  name: string;
  abbr: string | null;
}

export interface StatResult {
  kind: "stat";
  stat: string;
}

export type SearchResult = PlayerResult | TeamResult | StatResult;

/** Stat categories the Leaders panel can show. Mirrors DatasetPanel. */
export const STAT_CATEGORIES = ["PTS", "REB", "AST", "STL", "BLK"] as const;

export type ExplorePanelId =
  | "leaders"
  | "shots"
  | "trade"
  | "draft"
  | "lineups"
  | "playoffs";

/** Context applied when a panel expands: which panel, with what selection. */
export interface ExploreContext {
  panel: ExplorePanelId;
  playerName?: string;
  playerId?: string;
  teamAbbr?: string;
  stat?: string;
}

/**
 * Stat categories matching a query (case-insensitive substring).
 * Returns [] for queries under 2 chars. Plain includes() only.
 */
export function matchStats(query: string, stats: readonly string[] = STAT_CATEGORIES): StatResult[] {
  const needle = query.trim().toLowerCase();
  if (needle.length < 2) return [];
  return stats
    .filter((s) => s.toLowerCase().includes(needle) || needle.includes(s.toLowerCase()))
    .map((stat) => ({ kind: "stat" as const, stat }));
}

/**
 * Where a search result lands. Uniform per kind:
 * player -> Shots with that player, team -> Lineups with that team,
 * stat -> Leaders with that category.
 */
export function contextForResult(r: SearchResult): ExploreContext {
  if (r.kind === "player") {
    return { panel: "shots", playerName: r.name, playerId: String(r.id) };
  }
  if (r.kind === "team") {
    return r.abbr
      ? { panel: "lineups", teamAbbr: r.abbr }
      : { panel: "lineups" };
  }
  return { panel: "leaders", stat: r.stat };
}

/** Group header for a result kind, in display order. */
export function groupLabel(kind: SearchResult["kind"]): string {
  if (kind === "player") return "Players";
  if (kind === "team") return "Teams";
  return "Stats";
}

/** One-line description shown beside a result. Facts only. */
export function resultHint(r: SearchResult): string {
  if (r.kind === "player") return "Shots";
  if (r.kind === "team") return "Lineups";
  return "Leaders";
}
