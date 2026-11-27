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

export type SharedScenarioState =
  | { status: "ok"; object: SharedObject; evaluation: ScenarioResponse | null }
  | { status: "archived"; object: SharedObject }
  | { status: "not_found" }
  | { status: "invalid" }
  | { status: "unsupported"; kind: string }
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

function isScenarioResponse(value: unknown): value is ScenarioResponse {
  return !!value && typeof value === "object" && Array.isArray((value as Record<string, unknown>).errors);
}

export async function loadSharedScenario(
  backend: string,
  token: string,
  fetchImpl: typeof fetch = fetch,
): Promise<SharedScenarioState> {
  let object: SharedObject;
  try {
    const response = await fetchImpl(`${backend}/s/${encodeURIComponent(token)}`);
    if (response.status === 404) return { status: "not_found" };
    if (response.status === 422) return { status: "invalid" };
    if (!response.ok) return { status: "unavailable" };
    const body: unknown = await response.json();
    if (!isSharedObject(body)) return { status: "unavailable" };
    object = body;
  } catch {
    return { status: "unavailable" };
  }
  if (object.archived) return { status: "archived", object };
  if (object.kind !== "cap_scenario") return { status: "unsupported", kind: object.kind };

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
}
