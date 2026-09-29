
















import { abbrForTeamId } from "./teams";
import type { ResolvePlayerRow, ResolveTeamRow } from "./api";

interface PlayerResult {
  kind: "player";
  id: number;
  name: string;
}

interface TeamResult {
  kind: "team";
  id: number;
  name: string;
  abbr: string | null;
}

interface StatResult {
  kind: "stat";
  stat: string;
}

export type SearchResult = PlayerResult | TeamResult | StatResult;



export const STAT_CATEGORIES = ["PTS", "REB", "AST", "STL", "BLK"] as const;

export type ExplorePanelId =
  | "leaders"
  | "shots"
  | "trade"
  | "draft"
  | "lineups"
  | "playoffs";



export interface ExploreContext {
  panel: ExplorePanelId;
  playerName?: string;
  playerId?: string;
  teamAbbr?: string;
  stat?: string;
}






export function matchStats(query: string, stats: readonly string[] = STAT_CATEGORIES): StatResult[] {
  const needle = query.trim().toLowerCase();
  if (needle.length < 2) return [];
  return stats
    .filter((s) => s.toLowerCase().includes(needle) || needle.includes(s.toLowerCase()))
    .map((stat) => ({ kind: "stat" as const, stat }));
}







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



export function groupLabel(kind: SearchResult["kind"]): string {
  if (kind === "player") return "Players";
  if (kind === "team") return "Teams";
  return "Stats";
}



export function resultHint(r: SearchResult): string {
  if (r.kind === "player") return "Shots";
  if (r.kind === "team") return "Lineups";
  return "Leaders";
}








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



interface SearchMenuTrigger {
  top: number;
  bottom: number;
  left: number;
  width: number;
}

interface SearchMenuPlacement {
  above: boolean;
  top?: number;
  bottom?: number;
  left: number;
  width: number;
  maxHeight: number;
}

const SEARCH_MENU_MAX_H = 340;







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
