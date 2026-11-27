import type { DimeArtifact } from "@/lib/dime-stream";

export const NBA_TEAM_ABBRS = [
  "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
  "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
  "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
] as const;

const CAP_TOOLS = new Set(["get_cap_table", "get_cap_ledger", "get_cap_scenario"]);
const TRADE_TOOLS = new Set(["get_trade_check", "get_trade_value", "get_trade_legality"]);

export type ViewTarget = { tab: "cap" | "trades"; team?: string };

function sourceTool(source?: string): string {
  if (!source) return "";
  return source.split("·")[0].trim();
}

function scanTeams(text: string): string[] {
  const found: string[] = [];
  for (const abbr of NBA_TEAM_ABBRS) {
    if (new RegExp(`\\b${abbr}\\b`).test(text)) found.push(abbr);
  }
  return found;
}

function artifactTeam(artifact: DimeArtifact): string | undefined {
  if (artifact.kind === "team_card") {
    const hit = scanTeams(artifact.teamName);
    if (hit.length) return hit[0];
  }
  const titleHit = scanTeams(artifact.title ?? "");
  if (titleHit.length) return titleHit[0];
  if (artifact.kind === "table") {
    const body = artifact.rows.slice(0, 8).map(row => row.join(" ")).join(" ");
    const rowHit = scanTeams(body);
    if (rowHit.length) return rowHit[0];
  }
  return undefined;
}

export function viewTargetForArtifact(artifact: DimeArtifact): ViewTarget | null {
  const tool = sourceTool(artifact.source);
  if (CAP_TOOLS.has(tool)) return { tab: "cap", team: artifactTeam(artifact) };
  if (TRADE_TOOLS.has(tool)) return { tab: "trades", team: artifactTeam(artifact) };
  return null;
}

export function viewHref(target: ViewTarget): string {
  const url = new URL(window.location.href);
  url.searchParams.set("tab", target.tab);
  if (target.team) url.searchParams.set("team", target.team);
  else url.searchParams.delete("team");
  return `${url.pathname}${url.search}${url.hash}`;
}

export function navigateToView(target: ViewTarget): void {
  const url = new URL(window.location.href);
  url.searchParams.set("tab", target.tab);
  if (target.team) url.searchParams.set("team", target.team);
  else url.searchParams.delete("team");
  window.history.pushState({}, "", url);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function initialTeamParam(): string | null {
  if (typeof window === "undefined") return null;
  const value = new URLSearchParams(window.location.search).get("team");
  if (value && (NBA_TEAM_ABBRS as readonly string[]).includes(value)) return value;
  return null;
}
