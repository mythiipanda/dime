import { BACKEND, ModelsResponse } from "./chat";

export async function getModels(): Promise<ModelsResponse> {
  const res = await fetch(`${BACKEND}/api/v1/models`);
  if (!res.ok) throw new Error(`models failed: ${res.status}`);
  return res.json();
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
