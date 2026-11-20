import { BACKEND } from "./chat";
import type { BoardFill, BoardMetric, BoardSeed, BoardTemplate } from "./boards";

async function boardsRequest<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${BACKEND}/api/boards/${path}`, {
    method: body === undefined ? "GET" : "POST", signal,
    ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || data?.ok !== true) throw new Error(typeof data?.detail === "string" ? data.detail : `Boards request failed (${response.status}).`);
  return data as T;
}
export async function getBoardMetrics(signal?: AbortSignal): Promise<BoardMetric[]> { return (await boardsRequest<{ ok: true; metrics: BoardMetric[] }>("metrics", undefined, signal)).metrics; }
export function fillBoardCells(season: string, player_ids: number[], metric_ids: string[], signal?: AbortSignal): Promise<BoardFill> { return boardsRequest("fill", { season, player_ids, metric_ids }, signal); }
export function seedBoardRows(season: string, seed: NonNullable<BoardTemplate["seed"]>, signal?: AbortSignal): Promise<BoardSeed> { return boardsRequest("seed", { season, ...seed }, signal); }
