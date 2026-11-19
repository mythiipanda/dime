import { BACKEND } from "./chat";

export type TableDetail = { ok: true; table: string; count: number; columns: { name: string; type: string }[]; rows: Record<string, unknown>[]; seasons: string[]; last_fetch: string | null; data_through: string | null; limit: number };
export type HomeSnapshot = { date: string; schedule: { available: boolean; table: string; games: Record<string, unknown>[]; next_date: string | null; seasons: string[]; last_fetch: string | null }; snapshot: { table: string; season: string | null; rows: { TEAM_NAME: string; GP: number; NET_RATING: number | null }[]; last_fetch: string | null } };

async function read<T>(path: string): Promise<T> {
  const response = await fetch(`${BACKEND}${path}`);
  if (!response.ok) throw new Error("Could not read warehouse data");
  const result = await response.json();
  if (result.ok === false) throw new Error(result.error || "Warehouse data unavailable");
  return result as T;
}
export const getTableDetail = (table: string, season = "") => read<TableDetail>(`/api/warehouse/tables/${encodeURIComponent(table)}?season=${encodeURIComponent(season)}`);
export const getHomeSnapshot = () => read<HomeSnapshot>("/api/home");
