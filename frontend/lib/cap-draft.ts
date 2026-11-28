import type { ScenarioMove } from "./capsheet-fixture";
import type { MoveGroupsMap } from "./move-groups";
import { mintObject, updateObject, fetchOwnedObject } from "./objects-client";

const mappingKey = (team: string, season: string) => `dime_cap_draft:${team}:${season}`;

function draftMapping(team: string, season: string): string | null {
  try {
    return window.localStorage.getItem(mappingKey(team, season));
  } catch {
    return null;
  }
}

function retainMapping(team: string, season: string, objectId: string) {
  try {
    window.localStorage.setItem(mappingKey(team, season), objectId);
  } catch {}
}

function clearMapping(team: string, season: string) {
  try {
    window.localStorage.removeItem(mappingKey(team, season));
  } catch {}
}

function payloadFor(team: string, season: string, moves: ScenarioMove[], groups?: MoveGroupsMap) {
  return { team, season, moves, ...(groups && Object.keys(groups).length > 0 ? { groups } : {}) };
}

export async function syncCapDraft(team: string, season: string, moves: ScenarioMove[], groups?: MoveGroupsMap): Promise<boolean> {
  const existing = draftMapping(team, season);
  if (moves.length === 0) {
    if (existing) {
      const archived = await updateObject(existing, { archived: true });
      if (!archived) return false;
      clearMapping(team, season);
    }
    return true;
  }
  const payload = payloadFor(team, season, moves, groups);
  if (existing) {
    const updated = await updateObject(existing, { payload });
    if (updated) return true;
    clearMapping(team, season);
  }
  try {
    const minted = await mintObject("cap_scenario", `${team} working scenario · ${season}`, payload);
    retainMapping(team, season, minted.object_id);
    return true;
  } catch {
    return false;
  }
}

export async function loadCapDraft(team: string, season: string): Promise<{ moves: ScenarioMove[]; groups?: MoveGroupsMap } | null> {
  const objectId = draftMapping(team, season);
  if (!objectId) return null;
  const owned = await fetchOwnedObject(objectId);
  const payload = owned && typeof owned === "object" ? (owned as Record<string, unknown>).payload as Record<string, unknown> | undefined : undefined;
  if (!payload || !Array.isArray(payload.moves) || payload.moves.length === 0) return null;
  if ((owned as Record<string, unknown>).archived === true) return null;
  return { moves: payload.moves as ScenarioMove[], ...(payload.groups && typeof payload.groups === "object" ? { groups: payload.groups as MoveGroupsMap } : {}) };
}
