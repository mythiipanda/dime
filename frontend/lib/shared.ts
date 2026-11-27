import { cache } from "react";
import type { ScenarioMove, ScenarioResponse } from "./capsheet-fixture";

export type SharedObject = {
  kind: string;
  title: string;
  payload: {
    team: string;
    season: string;
    waiver_date?: string;
    moves: ScenarioMove[];
  };
  schema_version: number;
  updated_at: string;
  archived: boolean;
};

export type SharedTradeLeg = {
  from: string;
  to: string;
  players?: string | string[];
  picks?: Record<string, unknown>[];
};

export type SharedTradeObject = {
  kind: string;
  title: string;
  payload: {
    legs: SharedTradeLeg[];
    season: string;
  };
  schema_version: number;
  updated_at: string;
  archived: boolean;
};

export type TradeLegTeamRow = {
  team: string;
  incoming?: number;
  outgoing?: number;
  matching_ok?: boolean;
  match_rule?: string;
  allowed_incoming?: number;
  over_apron1?: boolean;
  over_apron2?: boolean;
  hard_cap?: string | null;
  issues?: string[];
};

export type TradeLegsEvaluation = {
  rows?: TradeLegTeamRow[];
  meta?: { disclaimer?: string; salary_date?: string };
  ok?: boolean;
  error?: string;
};

export type SharedScenarioState =
  | { status: "ok"; object: SharedObject; evaluation: ScenarioResponse | null }
  | { status: "ok-trade"; object: SharedTradeObject; evaluation: TradeLegsEvaluation | null }
  | { status: "archived"; object: { kind: string; title: string } }
  | { status: "not_found" }
  | { status: "invalid" }
  | { status: "unsupported"; kind: string }
  | { status: "unavailable" };

function isEnvelope(value: unknown): value is { kind: string; title: string; payload: Record<string, unknown>; updated_at: string; archived: boolean } {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.kind === "string"
    && typeof candidate.title === "string"
    && typeof candidate.updated_at === "string"
    && typeof candidate.archived === "boolean"
    && !!candidate.payload
    && typeof candidate.payload === "object"
  );
}

function isCapObject(value: { payload: Record<string, unknown> }): value is SharedObject {
  const payload = value.payload;
  return (
    typeof payload.team === "string"
    && typeof payload.season === "string"
    && Array.isArray(payload.moves)
  );
}

function isTradeLeg(value: unknown): value is SharedTradeLeg {
  if (!value || typeof value !== "object") return false;
  const leg = value as Record<string, unknown>;
  return typeof leg.from === "string" && typeof leg.to === "string";
}

function isTradeObject(value: { payload: Record<string, unknown> }): value is SharedTradeObject {
  const payload = value.payload;
  return (
    typeof payload.season === "string"
    && Array.isArray(payload.legs)
    && payload.legs.every(isTradeLeg)
  );
}

function isTradeEvaluation(value: unknown): value is TradeLegsEvaluation {
  return !!value && typeof value === "object" && (Array.isArray((value as Record<string, unknown>).rows) || typeof (value as Record<string, unknown>).error === "string");
}

function isScenarioResponse(value: unknown): value is ScenarioResponse {
  return !!value && typeof value === "object" && Array.isArray((value as Record<string, unknown>).errors);
}

export const loadSharedScenario = cache(async function loadSharedScenario(
  backend: string,
  token: string,
  fetchImpl: typeof fetch = fetch,
): Promise<SharedScenarioState> {
  let envelope: { kind: string; title: string; payload: Record<string, unknown>; updated_at: string; archived: boolean };
  try {
    const response = await fetchImpl(`${backend}/s/${encodeURIComponent(token)}`);
    if (response.status === 404) return { status: "not_found" };
    if (response.status === 422) return { status: "invalid" };
    if (!response.ok) return { status: "unavailable" };
    const body: unknown = await response.json();
    if (!isEnvelope(body)) return { status: "unavailable" };
    envelope = body;
  } catch {
    return { status: "unavailable" };
  }
  if (envelope.archived) return { status: "archived", object: envelope };

  if (envelope.kind === "trade_scenario") {
    if (!isTradeObject(envelope)) return { status: "unavailable" };
    const object = envelope;
    let evaluation: TradeLegsEvaluation | null = null;
    try {
      const response = await fetchImpl(`${backend}/api/trade/legs`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ legs: object.payload.legs, season: object.payload.season }),
        cache: "no-store",
      });
      const body: unknown = await response.json().catch(() => null);
      if (isTradeEvaluation(body)) evaluation = body;
    } catch {
      evaluation = null;
    }
    return { status: "ok-trade", object, evaluation };
  }

  if (envelope.kind !== "cap_scenario") return { status: "unsupported", kind: envelope.kind };
  if (!isCapObject(envelope)) return { status: "unavailable" };
  const object = envelope;

  let evaluation: ScenarioResponse | null = null;
  try {
    const response = await fetchImpl(`${backend}/api/cap/scenario`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        team: object.payload.team,
        season: object.payload.season,
        waiver_date: object.payload.waiver_date ?? "",
        moves: object.payload.moves,
      }),
      cache: "no-store",
    });
    const body: unknown = await response.json().catch(() => null);
    if (isScenarioResponse(body)) evaluation = body;
  } catch {
    evaluation = null;
  }
  return { status: "ok", object, evaluation };
});
