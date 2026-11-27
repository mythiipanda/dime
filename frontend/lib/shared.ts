import { cache } from "react";
import type { ScenarioMove, ScenarioResponse } from "./capsheet-fixture";
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

export type SharedScenarioState =
  | { status: "ok"; object: SharedObject; evaluation: ScenarioResponse | null }
  | { status: "archived"; object: SharedObject }
  | { status: "not_found" }
  | { status: "invalid" }
  | { status: "unsupported"; kind: string }
  | { status: "unavailable" };

export type SharedBoardObject = {
  kind: "board";
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

export type SharedBoardState =
  | { status: "ok"; object: SharedBoardObject; board: Board | null; metrics: BoardMetric[] }
  | { status: "archived"; object: SharedBoardObject }
  | { status: "not_found" }
  | { status: "invalid" }
  | { status: "unavailable" };

function isSharedObject(value: unknown): value is SharedObject {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  const payload = candidate.payload as Record<string, unknown> | undefined;
  return (
    typeof candidate.kind === "string"
    && typeof candidate.title === "string"
    && typeof candidate.updated_at === "string"
    && typeof candidate.archived === "boolean"
    && !!payload
    && typeof payload.team === "string"
    && typeof payload.season === "string"
    && Array.isArray(payload.moves)
  );
}

type RawShared = { status: number; body: unknown };

const fetchSharedRaw = cache(async function fetchSharedRaw(backend: string, token: string, fetchImpl: typeof fetch = fetch): Promise<RawShared | null> {
  try {
    const response = await fetchImpl(`${backend}/s/${encodeURIComponent(token)}`);
    if (response.status === 404) return { status: 404, body: null };
    if (response.status === 422) return { status: 422, body: null };
    if (!response.ok) return { status: response.status, body: null };
    return { status: 200, body: await response.json() };
  } catch {
    return null;
  }
});

function isSharedBoardObject(value: unknown): value is SharedBoardObject {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  const payload = candidate.payload as Record<string, unknown> | undefined;
  return (
    candidate.kind === "board"
    && typeof candidate.title === "string"
    && typeof candidate.updated_at === "string"
    && typeof candidate.archived === "boolean"
    && !!payload
    && typeof payload.season === "string"
    && Array.isArray(payload.rows)
    && payload.rows.every((row) => row && typeof row === "object" && typeof (row as Record<string, unknown>).player_id === "number")
    && Array.isArray(payload.columns)
    && payload.columns.every((column) => column && typeof column === "object" && typeof (column as Record<string, unknown>).metric_id === "string")
  );
}

function isScenarioResponse(value: unknown): value is ScenarioResponse {
  return !!value && typeof value === "object" && Array.isArray((value as Record<string, unknown>).errors);
}

export const loadSharedScenario = cache(async function loadSharedScenario(
  backend: string,
  token: string,
  fetchImpl: typeof fetch = fetch,
): Promise<SharedScenarioState> {
  const raw = await fetchSharedRaw(backend, token, fetchImpl);
  if (!raw) return { status: "unavailable" };
  if (raw.status === 404) return { status: "not_found" };
  if (raw.status === 422) return { status: "invalid" };
  if (raw.status !== 200) return { status: "unavailable" };
  const envelope = raw.body as Record<string, unknown> | null;
  if (envelope && typeof envelope.kind === "string" && envelope.kind !== "cap_scenario") return { status: "unsupported", kind: envelope.kind };
  if (!isSharedObject(raw.body)) return { status: "unavailable" };
  const object: SharedObject = raw.body;
  if (object.archived) return { status: "archived", object };

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

function isBoardFill(value: unknown): value is BoardFill {
  return !!value && typeof value === "object" && (value as Record<string, unknown>).ok === true
    && !!(value as Record<string, unknown>).cells && !!(value as Record<string, unknown>).players;
}

function isMetricList(value: unknown): value is { ok: true; metrics: BoardMetric[] } {
  return !!value && typeof value === "object" && Array.isArray((value as Record<string, unknown>).metrics);
}

export const loadSharedBoard = cache(async function loadSharedBoard(
  backend: string,
  token: string,
  fetchImpl: typeof fetch = fetch,
): Promise<SharedBoardState> {
  const raw = await fetchSharedRaw(backend, token, fetchImpl);
  if (!raw) return { status: "unavailable" };
  if (raw.status === 404) return { status: "not_found" };
  if (raw.status === 422) return { status: "invalid" };
  if (raw.status !== 200) return { status: "unavailable" };
  if (!isSharedBoardObject(raw.body)) return { status: "unavailable" };
  const object: SharedBoardObject = raw.body;
  if (object.archived) return { status: "archived", object };

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
      const now = object.updated_at;
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
        created_at: now,
        updated_at: now,
        ...(object.payload.template_id ? { template_id: object.payload.template_id } : {}),
      };
    }
  } catch {
    board = null;
  }
  return { status: "ok", object, board, metrics };
});
