import type { postChatStream } from "./api";

export function replayName(search: string, environment: string = process.env.NODE_ENV): string | null {
  return environment === "development" && new URLSearchParams(search).get("replay") === "scouting" ? "scouting" : null;
}

export async function replayStream(name: string, handlers: Parameters<typeof postChatStream>[2], signal?: AbortSignal): Promise<void> {
  if (process.env.NODE_ENV !== "development" || name !== "scouting") {
    handlers.onError("Replay is unavailable.");
    return;
  }
  const { scoutingEvents } = await import("./replay-fixture");
  for (const [type, data] of scoutingEvents) {
    if (signal?.aborted) return;
    handlers.onEvent(type, data);
    await new Promise<void>(resolve => {
      const done = () => { clearTimeout(timer); signal?.removeEventListener("abort", done); resolve(); };
      const timer = setTimeout(done, 80);
      signal?.addEventListener("abort", done, { once: true });
    });
  }
  if (!signal?.aborted) handlers.onDone();
}
