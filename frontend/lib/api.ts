import { BACKEND, ModelsResponse } from "./chat";

export const SEASON = "2025-26";

// v1-removal Step 4 (frontend cutover): the v2 router serves the same
// endpoints without the /v1 prefix (except chat, which has its own
// NEXT_PUBLIC_CHAT_RUNTIME toggle). Setting NEXT_PUBLIC_API_RUNTIME="v2"
// points every apiPath() call at the v2 router; the default stays v1 so
// this wiring is a no-op until the flag is flipped.
export function apiPath(p: string): string {
  return process.env.NEXT_PUBLIC_API_RUNTIME === "v2" ? `/api${p}` : `/api/v1${p}`;
}

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
    apiPath(`/today?season=${encodeURIComponent(season)}`),
  );
}

export function getWatchlist(season = SEASON): Promise<WatchItem[]> {
  return getEnvelope<WatchItem[]>(
    apiPath(`/watchlist?season=${encodeURIComponent(season)}`),
  );
}

export async function addWatchlist(
  entity_type: "player" | "team",
  entity_id: string,
  season = SEASON,
): Promise<boolean> {
  const res = await fetch(`${BACKEND}${apiPath("/watchlist")}`, {
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
  const res = await fetch(`${BACKEND}${apiPath(`/watchlist?${q.toString()}`)}`, {
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
    apiPath(`/movers?season=${encodeURIComponent(season)}&days=${days}`),
  );
}

export function getBriefing(season = SEASON): Promise<BriefingRows> {
  return getEnvelope<BriefingRows>(
    apiPath(`/briefing?season=${encodeURIComponent(season)}`),
  );
}

export async function getModels(): Promise<ModelsResponse> {
  const res = await fetch(`${BACKEND}${apiPath("/models")}`);
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
  const res = await fetch(`${BACKEND}${apiPath("/sql/rerun")}`, {
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

export function getClientId(): string {
  if (typeof window === "undefined") return "";
  let id = window.localStorage.getItem("dime_client");
  if (!id) {
    id = (window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`).slice(0, 64);
    window.localStorage.setItem("dime_client", id);
  }
  return id;
}

export async function postChatStream(
  q: string,
  model: string | null,
  handlers: StreamHandlers,
  signal?: AbortSignal,
  thread?: string | null,
): Promise<void> {
  // Client-side watchdogs: a stuck run must surface an error, not spin
  // "Thinking..." forever.
  //
  // - STALL_MS: no bytes at all (not even heartbeat pings) for 90s means
  //   the connection itself is dead.
  // - PROGRESS_MS: only pings and no real events for 3 minutes means the
  //   backend is alive (heartbeats flow every 15s) but the run is stuck --
  //   this is the case the old bytes-based watchdog could never catch.
  //   v1 only: v2 buffers every event until run end, so pings-only is the
  //   expected shape there and the backend's 6-minute run timeout already
  //   bounds a stuck v2 run.
  // - MAX_RUN_MS: absolute ceiling on a single chat request.
  const STALL_MS = 90_000;
  const PROGRESS_MS = 180_000;
  const MAX_RUN_MS = 480_000;
  const runtime = process.env.NEXT_PUBLIC_CHAT_RUNTIME === "v2" ? "v2" : "v1";
  const ctrl = new AbortController();
  const startedAt = Date.now();
  let lastByte = startedAt;
  let lastProgress = startedAt;
  type AbortCause = "idle" | "progress" | "ceiling" | null;
  let cause: AbortCause = null;
  const watchdog = setInterval(() => {
    const now = Date.now();
    if (now - lastByte > STALL_MS) {
      cause = "idle";
      ctrl.abort();
    } else if (runtime === "v1" && now - lastProgress > PROGRESS_MS) {
      cause = "progress";
      ctrl.abort();
    } else if (now - startedAt > MAX_RUN_MS) {
      cause = "ceiling";
      ctrl.abort();
    }
  }, 5_000);
  if (signal) {
    if (signal.aborted) ctrl.abort();
    else signal.addEventListener("abort", () => ctrl.abort(), { once: true });
  }
  function timeoutError(): string {
    if (cause === "idle") {
      return "No response from the server for 90s. The backend may be down - try again in a moment.";
    }
    if (cause === "progress") {
      return "The model stopped making progress for 3 minutes. The run was stopped - try again.";
    }
    if (cause === "ceiling") {
      return "The request timed out after 8 minutes. Try a simpler question or try again.";
    }
    return "Request cancelled.";
  }
  let res: Response;
  try {
    const endpoint = runtime === "v2" ? "/api/v2/chat/stream" : "/api/v1/chat/stream";
    res = await fetch(`${BACKEND}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q, model, thread, client: getClientId() }),
      signal: ctrl.signal,
    });
  } catch (e) {
    clearInterval(watchdog);
    if (cause || (e as Error)?.name === "AbortError") {
      handlers.onError(timeoutError());
    } else {
      handlers.onError("Could not reach the Dime backend. Check your connection and try again.");
    }
    return;
  }
  const contentType = res.headers.get("content-type") || "";
  if (!res.ok || !res.body || !contentType.includes("text/event-stream")) {
    clearInterval(watchdog);
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
  let terminal = false;
  try {
  for (;;) {
    let read: ReadableStreamReadResult<Uint8Array>;
    try {
      read = await reader.read();
    } catch (e) {
      clearInterval(watchdog);
      if (cause === "idle") {
        handlers.onError("No response from the server for 90s. The backend may be down - try again in a moment.");
      } else if (cause === "progress") {
        handlers.onError("The model stopped making progress for 3 minutes. The run was stopped - try again.");
      } else if (cause === "ceiling") {
        handlers.onError("The request timed out after 8 minutes. Try a simpler question or try again.");
      } else if ((e as Error)?.name !== "AbortError") {
        handlers.onError("Connection to the backend dropped. Try again.");
      }
      return;
    }
    const { done, value } = read;
    if (done) break;
    lastByte = Date.now();
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
        const eventType = typeLine.slice(6).trim();
        if (eventType === "graph_end") terminal = true;
        // Heartbeat pings keep the connection alive but are not progress:
        // only real events reset the progress watchdog.
        if (eventType !== "ping") lastProgress = Date.now();
        handlers.onEvent(
          eventType,
          JSON.parse(dataLines.join("\n")),
        );
      } catch {
        continue;
      }
    }
  }
  } finally {
    clearInterval(watchdog);
  }
  if (!terminal) {
    handlers.onError(
      "Connection to the backend ended before the run completed. Try again.",
    );
    return;
  }
  handlers.onDone();
}

export function datasetUrl(
  name: string,
  params: Record<string, string>,
  fmt: string,
): string {
  const q = new URLSearchParams({ ...params, fmt });
  return `${BACKEND}${apiPath(`/datasets/${name}?${q.toString()}`)}`;
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

// --- Local session persistence (QA F22) -------------------------------
// The backend session store is ephemeral container state: every deploy
// wipes it. The rail is per-browser by design, so localStorage is the
// durable source of truth for this browser's history; the server copy
// is a cache. Merge on read, write on every successful fetch.
const THREADS_KEY = () => `dime_threads_${getClientId()}`;
const RUNS_KEY = (id: string) => `dime_runs_${getClientId()}_${id}`;
const MAX_CACHED_THREADS = 50;
const MAX_CACHED_RUNS = 40;

function lsGet(key: string): unknown {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function lsSet(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage full or blocked - persistence is best-effort */
  }
}

export function loadCachedThreads(): ThreadInfo[] {
  const v = lsGet(THREADS_KEY());
  return Array.isArray(v) ? (v as ThreadInfo[]) : [];
}

function saveThreads(list: ThreadInfo[]): void {
  const sorted = [...list].sort((a, b) =>
    String(b.updated).localeCompare(String(a.updated)),
  );
  lsSet(THREADS_KEY(), sorted.slice(0, MAX_CACHED_THREADS));
}

function mergeThreads(server: ThreadInfo[]): ThreadInfo[] {
  const byId = new Map<string, ThreadInfo>();
  for (const t of loadCachedThreads()) byId.set(t.id, t);
  for (const t of server) byId.set(t.id, t); // server copy wins
  const merged = [...byId.values()];
  saveThreads(merged);
  return merged;
}

// Union the server's runs with the local cache instead of replacing it.
// The server store is wiped on every deploy, so the local cache can hold
// runs the server has never seen (appended after a wipe), and the server
// can hold runs this browser hasn't cached yet. Replacing the cache with
// the server's copy would silently drop whichever side is longer.
// Two copies of the same turn can carry different created_at stamps (the
// local write and the server write happen seconds apart), so dedupe can't
// key on the raw timestamp. Prefer a stable run id when both sides have one;
// otherwise treat same question+answer with a small timestamp skew as one
// turn. Tolerance is minutes, so a genuinely repeated question an hour later
// still renders as its own turn.
const RUN_DEDUPE_SKEW_MS = 10 * 60 * 1000;

function createdMs(v: unknown): number | null {
  const t = Date.parse(String(v));
  return Number.isFinite(t) ? t : null;
}

function isSameTurn(a: RunInfo, b: RunInfo): boolean {
  // Stable server-generated ids are exact: the same id is always the
  // same turn, even when timestamps or content drift across writes.
  if (a.id && b.id) return a.id === b.id;
  // One side id'd, the other not: never merge. Folding the authoritative
  // id'd copy into an id-less row by heuristic would resurrect the
  // repeat-question collapse this replaced.
  if (a.id || b.id) return false;
  // Legacy rows without ids (older caches, pre-id server rows): fall
  // back to question+answer with a small skew tolerance. This heuristic
  // can over-collapse genuinely repeated identical Q/A, which is why
  // every new run now carries a stable server id.
  if (a.question !== b.question || a.answer !== b.answer) return false;
  const ta = createdMs(a.created_at);
  const tb = createdMs(b.created_at);
  if (ta === null || tb === null) return a.created_at === b.created_at;
  return Math.abs(ta - tb) <= RUN_DEDUPE_SKEW_MS;
}

function mergeRuns(thread: string, serverOldestFirst: RunInfo[]): RunInfo[] {
  const merged: RunInfo[] = [];
  const push = (r: RunInfo) => {
    if (merged.some((m) => isSameTurn(m, r))) return;
    merged.push(r);
  };
  for (const r of loadCachedRuns(thread)) push(r);
  for (const r of serverOldestFirst) push(r);
  merged.sort((a, b) =>
    String(a.created_at).localeCompare(String(b.created_at)),
  );
  const out = merged.slice(-MAX_CACHED_RUNS);
  lsSet(RUNS_KEY(thread), out);
  return out;
}

export function loadCachedRuns(thread: string): RunInfo[] {
  const v = lsGet(RUNS_KEY(thread));
  const runs = Array.isArray(v) ? (v as RunInfo[]) : [];
  // Older builds cached the server's newest-first order; the load path
  // expects oldest-first. Self-heal once on read.
  if (runs.length > 1) {
    const first = runs[0]?.created_at;
    const last = runs[runs.length - 1]?.created_at;
    if (typeof first === "string" && typeof last === "string" && first > last) {
      return [...runs].reverse();
    }
  }
  return runs;
}

// Record a finished exchange locally the moment it completes. The server
// session store is ephemeral container state (every deploy wipes it), so
// without this the runs cache stays empty and a wiped server means the
// thread rail lists sessions whose clicks render an empty welcome state.
export function appendCachedRun(thread: string, run: RunInfo): void {
  const cached = loadCachedRuns(thread);
  const last = cached[cached.length - 1];
  if (last) {
    // onDone can fire again for the same run on re-renders: the stable
    // id makes that exact (same id = already recorded). A genuinely
    // re-asked question gets a new server id and is always kept.
    if (run.id && last.id === run.id) return;
    // Legacy no-id runs keep the old immediate q/a repeat guard.
    if (
      !run.id &&
      last.question === run.question &&
      last.answer === run.answer
    ) {
      return;
    }
  }
  cached.push(run);
  lsSet(RUNS_KEY(thread), cached.slice(-MAX_CACHED_RUNS));
}

export async function getThreads(): Promise<ThreadInfo[]> {
  try {
    const res = await fetch(`${BACKEND}${apiPath(`/threads?client=${encodeURIComponent(getClientId())}`)}`);
    if (!res.ok) return loadCachedThreads();
    const server = ((await res.json()).threads || []) as ThreadInfo[];
    return mergeThreads(server);
  } catch {
    return loadCachedThreads();
  }
}

export interface RunInfo {
  /** Server-assigned run id, when the backend provides one. Preferred for dedupe. */
  id?: string;
  question: string;
  answer: string;
  tables: unknown[];
  suggestions: string[];
  created_at: string;
}

export async function getRuns(thread: string): Promise<RunInfo[]> {
  try {
    const res = await fetch(
      `${BACKEND}${apiPath(`/threads/${thread}/runs?client=${encodeURIComponent(getClientId())}`)}`,
    );
    if (!res.ok) return loadCachedRuns(thread);
    const server = ((await res.json()).runs || []) as RunInfo[];
    // The server returns newest-first; the conversation load path and
    // the local cache are oldest-first, so normalize once at the edge.
    // Merge, don't replace: an empty server (deploy wipe) leaves the
    // local cache intact, and a partial server (post-wipe) can't drop
    // runs the server never saw.
    const runs = [...server].reverse();
    return mergeRuns(thread, runs);
  } catch {
    return loadCachedRuns(thread);
  }
}

export function exportUrl(thread: string): string {
  return `${BACKEND}${apiPath(`/threads/${thread}/export?client=${encodeURIComponent(getClientId())}`)}`;
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
  const res = await fetch(`${BACKEND}${apiPath(`/debate-card?${q.toString()}`)}`);
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
  return `${BACKEND}${apiPath(`/debate-card/file?name=${encodeURIComponent(pathOrUrl)}`)}`;
}

export async function resolvePlayers(q: string, limit = 4): Promise<PlayerHit[]> {
  try {
    const res = await fetch(`${BACKEND}${apiPath(`/resolve?q=${encodeURIComponent(q)}`)}`);
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
  qualification?: string;
  coverage?: string;
  warnings?: string[];
}

export function buildCitation(c: CitationInput): string {
  const bits = [
    c.title || "NBA data",
    `via ${c.source || "Dime warehouse"}`,
    c.season ? `covering ${c.season}` : "",
    c.fetchedAt ? `fetched ${String(c.fetchedAt).slice(0, 10)}` : "",
  ].filter(Boolean);
  const limitations = [c.qualification, c.coverage, ...(c.warnings ?? [])]
    .filter(Boolean);
  const suffix = limitations.length > 0
    ? `. Limits: ${limitations.join(" ")}`
    : "";
  return `${bits.join(", ")} — Dime NBA Analyst${suffix}`;
}

export function tableKind(t: { kind?: string; tool?: string }): string {
  return t.kind || t.tool || "dataset";
}
