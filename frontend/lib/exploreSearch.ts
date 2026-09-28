// Search-first header helpers (redesign Phase 3). Pure functions kept
// separate from the component so they stay unit-testable.
//
// Result types mirror what the existing /resolve endpoint returns
// (players + teams); stat matches come from the stat categories the
// Leaders panel already offers. Matching is case-insensitive substring
// only. No regular expressions, no per-name special cases: every result
// of the same kind opens the same panel with the same context shape.

import { abbrForTeamId } from "./teams";
import type { ResolvePlayerRow, ResolveTeamRow } from "./api";

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

/**
 * Entity type read off a resolve row's own response fields. Team rows
 * carry an `abbreviation` field; player rows never do. No name reading
 * of any kind: the grouping below stays correct even when a response
 * puts a row in the wrong array.
 */
export function entityKind(row: ResolvePlayerRow | ResolveTeamRow): "player" | "team" {
  return "abbreviation" in row ? "team" : "player";
}

function isUsableRow(row: ResolvePlayerRow | ResolveTeamRow): boolean {
  return (
    !!row &&
    typeof row.id === "number" &&
    typeof row.full_name === "string" &&
    row.full_name.length > 0
  );
}

/**
 * Merge raw resolve rows into grouped dropdown items. Every row is
 * classified by its own fields (see entityKind), so a team row renders
 * only under Teams and a player row only under Players — even if the
 * endpoint returns a row in the wrong array. An entity present in both
 * arrays renders once, under its data-determined group. Order is
 * stable: players, then teams, then stats.
 */
export function buildSearchItems(
  players: readonly (ResolvePlayerRow | ResolveTeamRow)[],
  teams: readonly (ResolvePlayerRow | ResolveTeamRow)[],
  stats: readonly StatResult[],
): SearchResult[] {
  const seen = new Set<string>();
  const out: SearchResult[] = [];
  const push = (r: SearchResult) => {
    const key = r.kind === "stat" ? `stat:${r.stat}` : `${r.kind}:${r.id}`;
    if (seen.has(key)) return;
    seen.add(key);
    out.push(r);
  };
  for (const row of [...players, ...teams]) {
    if (!isUsableRow(row)) continue;
    if (entityKind(row) === "team") {
      const t = row as ResolveTeamRow;
      push({
        kind: "team",
        id: t.id,
        name: t.full_name,
        abbr: t.abbreviation ?? abbrForTeamId(t.id) ?? null,
      });
    } else {
      push({ kind: "player", id: row.id, name: row.full_name });
    }
  }
  for (const s of stats) push(s);
  return out;
}

/** Viewport-anchored dropdown placement (mirrors ModelPicker's menu). */
export interface SearchMenuTrigger {
  top: number;
  bottom: number;
  left: number;
  width: number;
}

export interface SearchMenuPlacement {
  above: boolean;
  top?: number;
  bottom?: number;
  left: number;
  width: number;
  maxHeight: number;
}

export const SEARCH_MENU_MAX_H = 340;

/**
 * Place the suggestion dropdown against the search field: below it when
 * there is room, above it when space is tight. Always returns a
 * placement — scrolling repositions the open dropdown, never closes it.
 */
export function placeSearchMenu(
  trigger: SearchMenuTrigger,
  viewport: { width: number; height: number },
  maxH: number = SEARCH_MENU_MAX_H,
): SearchMenuPlacement {
  const menuH = Math.min(maxH, viewport.height - 24);
  const aboveH = trigger.top - 8;
  const belowH = viewport.height - trigger.bottom - 8;
  const openAbove = aboveH >= Math.min(menuH, 200) || aboveH >= belowH;
  const width = Math.max(0, Math.min(trigger.width, viewport.width - 16));
  const left = Math.max(8, Math.min(trigger.left, viewport.width - 8 - width));
  if (openAbove) {
    return {
      above: true,
      left,
      width,
      bottom: Math.max(8, viewport.height - trigger.top + 6),
      maxHeight: Math.min(menuH, aboveH),
    };
  }
  return {
    above: false,
    left,
    width,
    top: trigger.bottom + 6,
    maxHeight: Math.min(menuH, belowH),
  };
}
