import { cache } from "react";
import type { ScenarioMove } from "./capsheet-fixture";
import type { ProjectionResponse } from "./planner";
import type { Board, BoardMetric, BoardFill } from "./boards";

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
    tpes?: { team: string; amount: number; kind?: string; origin_year?: number; exactness?: string }[];
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

export type SharedBoardPin = {
  kind: string;
  object_id: string;
  note?: string;
  status: "ok" | "missing" | "archived";
  title?: string;
  payload?: Record<string, unknown>;
  artifact?: Record<string, unknown> | null;
  artifact_unavailable?: boolean;
  capEvaluation?: ProjectionResponse | null;
  tradeEvaluation?: TradeLegsEvaluation | null;
};

export type SharedBoardObject = {
  kind: string;
  title: string;
  payload: {
    season: string;
    rows: { player_id: number }[];
    columns: { metric_id: string }[];
    template_id?: string;
  };
  schema_version: number;
  updated_at: string;
  archived: boolean;
};

function isBoardObject(value: { payload: Record<string, unknown> }): value is SharedBoardObject {
  const payload = value.payload;
  return (
    typeof payload.season === "string"
    && Array.isArray(payload.rows) && payload.rows.length > 0
    && payload.rows.every((row) => row && typeof row === "object" && typeof (row as Record<string, unknown>).player_id === "number")
    && Array.isArray(payload.columns) && payload.columns.length > 0
    && payload.columns.every((column) => column && typeof column === "object" && typeof (column as Record<string, unknown>).metric_id === "string")
  );
}

function isBoardFill(value: unknown): value is BoardFill {
  return !!value && typeof value === "object" && (value as Record<string, unknown>).ok === true
    && !!(value as Record<string, unknown>).cells && !!(value as Record<string, unknown>).players;
}

function isMetricList(value: unknown): value is { ok: true; metrics: BoardMetric[] } {
  return !!value && typeof value === "object" && Array.isArray((value as Record<string, unknown>).metrics);
}

export type SharedScenarioState =
  | { status: "ok"; object: SharedObject; evaluation: ProjectionResponse | null }
  | { status: "ok-trade"; object: SharedTradeObject; evaluation: TradeLegsEvaluation | null }
  | { status: "ok-thread"; object: SharedThreadObject; transcript: TranscriptEntry[] }
  | { status: "ok-board"; object: SharedBoardObject; board: Board | null; metrics: BoardMetric[]; pins: SharedBoardPin[] }
  | { status: "ok-artifact"; object: SharedArtifactObject; artifact: Record<string, unknown> | null; evidence: SharedArtifactEvidence[]; captured_at: string | null; unavailable: boolean }
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

export type SharedArtifactEvidence = {
  ref: string;
  tool?: string;
  meta?: Record<string, unknown> | null;
  rows?: Record<string, unknown>[];
  missing?: boolean;
};

export type SharedArtifactObject = {
  kind: string;
  title: string;
  schema_version: number;
  updated_at: string;
  archived: boolean;
};

export type TranscriptEntry = {
  question: string;
  answer: string;
  tables: { tool?: string; meta?: { source?: string; season?: string; fetched_at?: string } }[];
  created_at: string;
};

export type SharedThreadObject = {
  kind: string;
  title: string;
  schema_version: number;
  updated_at: string;
  archived: boolean;
};

function isTranscriptEntry(value: unknown): value is TranscriptEntry {
  if (!value || typeof value !== "object") return false;
  const entry = value as Record<string, unknown>;
  return typeof entry.question === "string" && typeof entry.answer === "string";
}

function isProjectionResponse(value: unknown): value is ProjectionResponse {
  return !!value && typeof value === "object" && Array.isArray((value as Record<string, unknown>).seasons);
}

export const loadSharedScenario = cache(async function loadSharedScenario(
  backend: string,
  token: string,
  fetchImpl: typeof fetch = fetch,
): Promise<SharedScenarioState> {
  let envelope: { kind: string; title: string; payload: Record<string, unknown>; updated_at: string; archived: boolean };
  try {
    const response = await fetchImpl(`${backend}/s/${encodeURIComponent(token)}`, { cache: "no-store" });
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
        body: JSON.stringify({ legs: object.payload.legs, season: object.payload.season, tpes: object.payload.tpes }),
        cache: "no-store",
      });
      const body: unknown = await response.json().catch(() => null);
      if (isTradeEvaluation(body)) evaluation = body;
    } catch {
      evaluation = null;
    }
    return { status: "ok-trade", object, evaluation };
  }

  if (envelope.kind === "thread_grant") {
    const body2 = envelope as unknown as Record<string, unknown>;
    const transcript = Array.isArray(body2.transcript) ? body2.transcript.filter(isTranscriptEntry) : [];
    const object: SharedThreadObject = {
      kind: envelope.kind,
      title: envelope.title,
      schema_version: typeof body2.schema_version === "number" ? body2.schema_version : 1,
      updated_at: envelope.updated_at,
      archived: envelope.archived,
    };
    return { status: "ok-thread", object, transcript };
  }

  if (envelope.kind === "board") {
    if (!isBoardObject(envelope)) return { status: "unavailable" };
    const object = envelope;
    let board: Board | null = null;
    let metrics: BoardMetric[] = [];
    try {
      const [fillResponse, metricsResponse] = await Promise.all([
        fetchImpl(`${backend}/api/boards/fill`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            season: object.payload.season,
            player_ids: object.payload.rows.map((row) => row.player_id),
            metric_ids: object.payload.columns.map((column) => column.metric_id),
          }),
          cache: "no-store",
        }),
        fetchImpl(`${backend}/api/boards/metrics`, { cache: "no-store" }),
      ]);
      const fillBody: unknown = await fillResponse.json().catch(() => null);
      const metricsBody: unknown = await metricsResponse.json().catch(() => null);
      if (isMetricList(metricsBody)) metrics = metricsBody.metrics;
      if (isBoardFill(fillBody)) {
        board = {
          id: "shared",
          title: object.title,
          season: object.payload.season,
          rows: object.payload.rows.map((row) => ({
            player_id: row.player_id,
            name: fillBody.players[String(row.player_id)]?.name || `Player ${row.player_id}`,
            team: fillBody.players[String(row.player_id)]?.team || "",
          })),
          columns: object.payload.columns.map((column) => ({ metric_id: column.metric_id })),
          cells: fillBody.cells,
          created_at: object.updated_at,
          updated_at: object.updated_at,
          ...(object.payload.template_id ? { template_id: object.payload.template_id } : {}),
        };
      }
    } catch {
      board = null;
    }
    const rawPins = Array.isArray((envelope as unknown as Record<string, unknown>).pins) ? (envelope as unknown as Record<string, unknown>).pins as Record<string, unknown>[] : [];
    const pins: SharedBoardPin[] = await Promise.all(rawPins.map(async raw => {
      const pin: SharedBoardPin = {
        kind: typeof raw.kind === "string" ? raw.kind : "",
        object_id: typeof raw.object_id === "string" ? raw.object_id : "",
        ...(typeof raw.note === "string" ? { note: raw.note } : {}),
        status: raw.status === "ok" ? "ok" : raw.status === "archived" ? "archived" : "missing",
        ...(typeof raw.title === "string" ? { title: raw.title } : {}),
        ...(raw.payload && typeof raw.payload === "object" ? { payload: raw.payload as Record<string, unknown> } : {}),
      };
      if (pin.kind === "artifact_ref") {
        pin.artifact = raw.artifact && typeof raw.artifact === "object" ? raw.artifact as Record<string, unknown> : null;
        pin.artifact_unavailable = raw.artifact_unavailable === true || !pin.artifact;
      }
      if (pin.status !== "ok" || !pin.payload) return pin;
      if (pin.kind === "cap_scenario") {
        try {
          const response = await fetchImpl(`${backend}/api/cap/projection`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
              team: pin.payload.team,
              season: pin.payload.season,
              moves: pin.payload.moves,
              tpes: (pin.payload as { tpes?: unknown[] }).tpes,
            }),
            cache: "no-store",
          });
          const body: unknown = await response.json().catch(() => null);
          pin.capEvaluation = isProjectionResponse(body) ? body : null;
        } catch {
          pin.capEvaluation = null;
        }
      }
      if (pin.kind === "trade_scenario") {
        try {
          const response = await fetchImpl(`${backend}/api/trade/legs`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ legs: pin.payload.legs, season: pin.payload.season }),
            cache: "no-store",
          });
          const body: unknown = await response.json().catch(() => null);
          pin.tradeEvaluation = isTradeEvaluation(body) ? body : null;
        } catch {
          pin.tradeEvaluation = null;
        }
      }
      return pin;
    }));
    return { status: "ok-board", object, board, metrics, pins };
  }

  if (envelope.kind === "artifact_ref") {
    const body3 = envelope as unknown as Record<string, unknown>;
    const artifact = body3.artifact && typeof body3.artifact === "object" ? body3.artifact as Record<string, unknown> : null;
    const evidence = Array.isArray(body3.evidence) ? body3.evidence.filter((row): row is SharedArtifactEvidence => !!row && typeof row === "object") : [];
    const object: SharedArtifactObject = {
      kind: envelope.kind,
      title: envelope.title,
      schema_version: typeof body3.schema_version === "number" ? body3.schema_version : 1,
      updated_at: envelope.updated_at,
      archived: envelope.archived,
    };
    return {
      status: "ok-artifact",
      object,
      artifact,
      evidence,
      captured_at: typeof body3.captured_at === "string" ? body3.captured_at : null,
      unavailable: body3.unavailable === true || artifact === null,
    };
  }

  if (envelope.kind !== "cap_scenario") return { status: "unsupported", kind: envelope.kind };
  if (!isCapObject(envelope)) return { status: "unavailable" };
  const object = envelope;

  let evaluation: ProjectionResponse | null = null;
  try {
    const response = await fetchImpl(`${backend}/api/cap/projection`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        team: object.payload.team,
        season: object.payload.season,
        moves: object.payload.moves,
        tpes: (object.payload as { tpes?: unknown[] }).tpes,
      }),
      cache: "no-store",
    });
    const body: unknown = await response.json().catch(() => null);
    if (isProjectionResponse(body)) evaluation = body;
  } catch {
    evaluation = null;
  }
  return { status: "ok", object, evaluation };
});
