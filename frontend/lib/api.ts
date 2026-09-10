import { BACKEND, ModelsResponse } from "./chat";

const SEASON = "2025-26";

export interface GameRow {
  HOME_TEAM_ABBREVIATION?: string;
  VISITOR_TEAM_ABBREVIATION?: string;
  HOME_TEAM_PTS?: number | null;
  VISITOR_TEAM_PTS?: number | null;
  GAME_STATUS_TEXT?: string;
}

export interface TodayMover {
  PLAYER?: string;
  TEAM?: string;
  RANK_CHANGE?: string;
  PTS_CHANGE?: number;
  note?: string;
}

export interface TeamStreak {
  TEAM?: string;
  W?: number;
  L?: number;
  STREAK?: string;
  GAMES?: number;
}

export interface TodayRows {
  last_night: GameRow[];
  tonight: GameRow[];
  movers: TodayMover[];
  streaks: TeamStreak[];
}

export interface WatchSnapshot {
  found?: boolean;
  player?: string;
  team?: string;
  name?: string;
  gp?: number;
  ppg?: number | null;
  rpg?: number | null;
  apg?: number | null;
  wins?: number;
  losses?: number;
  record?: string | null;
}

export interface WatchItem {
  entity_type: "player" | "team";
  entity_id: string;
  added_at?: string;
  snapshot: WatchSnapshot;
}

export interface Mover {
  player?: string;
  team?: string;
  rank_base?: number;
  rank_now?: number;
  rank_change?: number;
  pts_base?: number;
  pts_now?: number;
  pts_change?: number;
}

export interface NewEntry {
  player?: string;
  team?: string;
  pts?: number;
  rank?: number;
}

export interface MoversRows {
  climbers: Mover[];
  fallers: Mover[];
  new_entries: NewEntry[];
}

export interface BriefingRows {
  today?: TodayRows;
  watchlist?: WatchItem[];
  movers?: MoversRows;
}

async function getEnvelope<T>(path: string): Promise<T> {
  const res = await fetch(`${BACKEND}${path}`);
  if (!res.ok) throw new Error(`request failed: ${res.status}`);
  const data = (await res.json()) as {
    ok?: boolean;
    rows?: T;
    error?: string;
  };
  if (data && data.ok === false) throw new Error(data.error || "request failed");
  return (data.rows ?? []) as T;
}

export function getToday(season = SEASON): Promise<TodayRows> {
  return getEnvelope<TodayRows>(
    `/api/v1/today?season=${encodeURIComponent(season)}`,
  );
}

export function getWatchlist(season = SEASON): Promise<WatchItem[]> {
  return getEnvelope<WatchItem[]>(
    `/api/v1/watchlist?season=${encodeURIComponent(season)}`,
  );
}

export async function addWatchlist(
  entity_type: "player" | "team",
  entity_id: string,
  season = SEASON,
): Promise<boolean> {
  const res = await fetch(`${BACKEND}/api/v1/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ entity_type, entity_id, season }),
  });
  if (!res.ok) throw new Error(`add failed: ${res.status}`);
  const data = (await res.json()) as {
    ok?: boolean;
    rows?: { added?: boolean };
    error?: string;
  };
  if (data && data.ok === false) throw new Error(data.error || "add failed");
  return Boolean(data.rows?.added);
}

export async function removeWatchlist(
  entity_type: "player" | "team",
  entity_id: string,
): Promise<boolean> {
  const q = new URLSearchParams({ entity_type, entity_id });
  const res = await fetch(`${BACKEND}/api/v1/watchlist?${q.toString()}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`remove failed: ${res.status}`);
  const data = (await res.json()) as {
    ok?: boolean;
    rows?: { removed?: boolean };
    error?: string;
  };
  if (data && data.ok === false) throw new Error(data.error || "remove failed");
  return Boolean(data.rows?.removed);
}

export function getMovers(season = SEASON, days = 7): Promise<MoversRows> {
  return getEnvelope<MoversRows>(
    `/api/v1/movers?season=${encodeURIComponent(season)}&days=${days}`,
  );
}

export function getBriefing(season = SEASON): Promise<BriefingRows> {
  return getEnvelope<BriefingRows>(
    `/api/v1/briefing?season=${encodeURIComponent(season)}`,
  );
}

export async function getModels(): Promise<ModelsResponse> {
  const res = await fetch(`${BACKEND}/api/v1/models`);
  if (!res.ok) throw new Error(`models failed: ${res.status}`);
  return res.json();
}

export interface SqlRerunRows {
  columns: string[];
  rows: Record<string, unknown>[];
  ms: number;
  capped: boolean;
}

export async function rerunSql(sql: string): Promise<SqlRerunRows> {
  const res = await fetch(`${BACKEND}/api/v1/sql/rerun`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql }),
  });
  if (!res.ok) throw new Error(`re-run failed: ${res.status}`);
  const data = (await res.json()) as {
    ok?: boolean;
    rows?: SqlRerunRows;
    error?: string;
  };
  if (data && data.ok === false) throw new Error(data.error || "re-run failed");
  return (data.rows ?? { columns: [], rows: [], ms: 0, capped: false }) as SqlRerunRows;
}

export interface StreamHandlers {
  onEvent: (type: string, data: unknown) => void;
  onDone: () => void;
  onError: (message: string) => void;
}

export async function postChatStream(
  q: string,
  model: string | null,
  handlers: StreamHandlers,
  signal?: AbortSignal,
  thread?: string | null,
): Promise<void> {
  const res = await fetch(`${BACKEND}/api/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ q, model, thread }),
    signal,
  });
  const contentType = res.headers.get("content-type") || "";
  if (!res.ok || !res.body || !contentType.includes("text/event-stream")) {
    if (res.status === 429) {
      handlers.onError("Too many requests. Wait a minute and try again.");
    } else {
      handlers.onError(`Chat failed with status ${res.status}. Try again.`);
    }
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() || "";
    for (const part of parts) {
      const typeLine = part.split("\n").find((l) => l.startsWith("event:"));
      const dataLines = part
        .split("\n")
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trim());
      if (!typeLine || !dataLines.length) continue;
      try {
        handlers.onEvent(
          typeLine.slice(6).trim(),
          JSON.parse(dataLines.join("\n")),
        );
      } catch {
        continue;
      }
    }
  }
  handlers.onDone();
}

export function datasetUrl(
  name: string,
  params: Record<string, string>,
  fmt: string,
): string {
  const q = new URLSearchParams({ ...params, fmt });
  return `${BACKEND}/api/v1/datasets/${name}?${q.toString()}`;
}

export async function getDatasetJson(
  name: string,
  params: Record<string, string>,
): Promise<{ ok: boolean; data?: unknown[]; meta?: Record<string, unknown>; error?: string }> {
  const res = await fetch(datasetUrl(name, params, "json"));
  return res.json();
}

export interface ThreadInfo {
  id: string;
  title: string;
  updated: string;
  turns: number;
}

export async function getThreads(): Promise<ThreadInfo[]> {
  const res = await fetch(`${BACKEND}/api/v1/threads`);
  if (!res.ok) return [];
  return ((await res.json()).threads || []) as ThreadInfo[];
}

export interface RunInfo {
  question: string;
  answer: string;
  tables: unknown[];
  suggestions: string[];
  created_at: string;
}

export async function getRuns(thread: string): Promise<RunInfo[]> {
  const res = await fetch(`${BACKEND}/api/v1/threads/${thread}/runs`);
  if (!res.ok) return [];
  return ((await res.json()).runs || []) as RunInfo[];
}

export function exportUrl(thread: string): string {
  return `${BACKEND}/api/v1/threads/${thread}/export`;
}

export interface PlayerHit {
  id: number;
  name: string;
}

export interface DebateCardRows {
  path: string;
  players: string[];
  url: string;
}

export async function getDebateCard(
  a: string,
  b: string,
  season = SEASON,
  topic?: string,
): Promise<DebateCardRows> {
  const q = new URLSearchParams({ a, b, season });
  if (topic) q.set("topic", topic);
  const res = await fetch(`${BACKEND}/api/v1/debate-card?${q.toString()}`);
  if (!res.ok) throw new Error(`debate card failed: ${res.status}`);
  const data = (await res.json()) as {
    ok?: boolean;
    rows?: DebateCardRows;
    error?: string;
  };
  if (data.ok === false || !data.rows)
    throw new Error(data.error || "debate card failed");
  return data.rows;
}

export function debateFileUrl(pathOrUrl: string): string {
  if (pathOrUrl.startsWith("http")) return pathOrUrl;
  if (pathOrUrl.startsWith("/")) return `${BACKEND}${pathOrUrl}`;
  return `${BACKEND}/api/v1/debate-card/file?name=${encodeURIComponent(pathOrUrl)}`;
}

export async function resolvePlayers(q: string, limit = 4): Promise<PlayerHit[]> {
  try {
    const res = await fetch(`${BACKEND}/api/v1/resolve?q=${encodeURIComponent(q)}`);
    const data = (await res.json()) as unknown;
    if (typeof data !== "object" || data === null || !("rows" in data)) return [];
    const players = (data as { rows: { players?: { id: number; full_name: string }[] } }).rows.players;
    return (players || []).slice(0, limit).map((v) => ({ id: v.id, name: v.full_name }));
  } catch {
    return [];
  }
}

export async function resolveFirstPlayerId(q: string): Promise<number | null> {
  const hit = (await resolvePlayers(q, 1))[0];
  return hit ? hit.id : null;
}

export function getQueryParam(key: string): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get(key);
}

export function setQueryParam(key: string, value: string, push = false) {
  if (typeof window === "undefined") return;
  const sp = new URLSearchParams(window.location.search);
  if (value) sp.set(key, value);
  else sp.delete(key);
  const qs = sp.toString();
  const url = window.location.pathname + (qs ? `?${qs}` : "");
  const cur = window.location.pathname + window.location.search;
  if (url === cur) return;
  window.history[push ? "pushState" : "replaceState"](null, "", url);
}

export interface CitationInput {
  title?: string;
  source?: string;
  fetchedAt?: string;
  season?: string;
}

export function buildCitation(c: CitationInput): string {
  const bits = [
    c.title || "NBA data",
    `via ${c.source || "Dime warehouse"}`,
    c.season ? `covering ${c.season}` : "",
    c.fetchedAt ? `fetched ${String(c.fetchedAt).slice(0, 10)}` : "",
  ].filter(Boolean);
  return `${bits.join(", ")} — Dime NBA Analyst`;
}

export function tableKind(t: { kind?: string; tool?: string }): string {
  return t.kind || t.tool || "dataset";
}
