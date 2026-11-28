import type { ScenarioMove } from "./capsheet-fixture";
import type { MoveGroupsMap } from "./move-groups";

const KEY = "dime_cap_handoff_v1";

export interface CapHandoff {
  team: string;
  season: string;
  moves: ScenarioMove[];
  source: string;
  groups?: MoveGroupsMap;
}

function validMove(move: unknown): move is ScenarioMove {
  if (!move || typeof move !== "object") return false;
  const candidate = move as Record<string, unknown>;
  return typeof candidate.kind === "string" && ["signing", "trade_in", "trade_out", "waive", "option_decision"].includes(candidate.kind);
}

export function writeCapHandoff(handoff: CapHandoff) {
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(handoff));
  } catch {}
}

export function consumeCapHandoff(): CapHandoff | null {
  try {
    const raw = window.sessionStorage.getItem(KEY);
    if (!raw) return null;
    window.sessionStorage.removeItem(KEY);
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    const candidate = parsed as Record<string, unknown>;
    if (typeof candidate.team !== "string" || typeof candidate.season !== "string" || !Array.isArray(candidate.moves) || candidate.moves.length === 0 || !candidate.moves.every(validMove)) return null;
    return { team: candidate.team, season: candidate.season, moves: candidate.moves, source: typeof candidate.source === "string" ? candidate.source : "", ...(candidate.groups && typeof candidate.groups === "object" ? { groups: candidate.groups as MoveGroupsMap } : {}) };
  } catch {
    return null;
  }
}

export function navigateToCap() {
  window.dispatchEvent(new CustomEvent("dime:navigate", { detail: { tab: "cap" } }));
}
