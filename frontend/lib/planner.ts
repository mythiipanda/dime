import { apiPath } from "./api";
import { BACKEND } from "./chat";
import type { ScenarioMove } from "./capsheet-fixture";

export type ProjectionEffect = {
  move: number;
  kind: string;
  detail: string;
  delta: number;
  exactness: "exact" | "derived" | "proxy" | "unresolved" | "unvalidated" | string;
  disclosure?: string;
  exception?: string;
};

export type ProjectionPlayer = { player: string; salary: number; option?: string };

export type ProjectionCapHold = {
  player: string;
  amount: number | null;
  fa_type: string;
};

export type ProjectionException = {
  exception: string;
  amount: number;
  used: number;
  remaining: number;
  hard_caps: boolean;
  exceeds: number | null;
  unavailable: boolean;
};

export type ProjectionSeason = {
  season: string;
  pay_before: number;
  pay_after: number;
  cap_room: number;
  players: ProjectionPlayer[];
  roster_before: number;
  roster_after: number;
  roster_issues: string[];
  hard_cap: string;
  hard_cap_violation: string;
  exception_usage: string[];
  trade_exceptions?: { amount: number; kind: string; exactness: string; status: string; note: string }[];
  effects: ProjectionEffect[];
  moves_in_season: number;
  ordering_notes: string[];
  lines: { cap: number; tax: number; apron1: number; apron2: number };
  lines_projected: boolean;
  exceptions?: ProjectionException[];
  cap_holds?: number;
  cap_holds_exactness?: string;
  cap_hold_details?: ProjectionCapHold[];
};

export type ProjectionResponse = {
  ok: boolean;
  error?: string;
  team?: string;
  base_season?: string;
  seasons: ProjectionSeason[];
  errors: { move: string; error: string }[];
  warnings: string[];
  disclosures: string[];
};

export async function fetchProjection(team: string, season: string, moves: ScenarioMove[], tpes?: unknown[]): Promise<ProjectionResponse | null> {
  try {
    const response = await fetch(`${BACKEND}${apiPath("/cap/projection")}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ team, season, moves, tpes }),
    });
    const body: unknown = await response.json().catch(() => null);
    if (!body || typeof body !== "object" || (body as ProjectionResponse).ok !== true) return null;
    return body as ProjectionResponse;
  } catch {
    return null;
  }
}

export function formatMoney(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value}`;
}
