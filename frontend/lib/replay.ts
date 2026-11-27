import type { postChatStream } from "./api";

export function replayName(search: string, environment: string = process.env.NODE_ENV): string | null {
  const name = new URLSearchParams(search).get("replay");
  return environment === "development" && (name === "scouting" || name === "generative" || name === "worstcase") ? name : null;
}

export async function replayStream(name: string, handlers: Parameters<typeof postChatStream>[2], signal?: AbortSignal): Promise<void> {
  if (process.env.NODE_ENV !== "development" || (name !== "scouting" && name !== "generative" && name !== "worstcase")) {
    handlers.onError("Replay is unavailable.");
    return;
  }
  const events = name === "generative" ? (await import("./generative-fixture")).generativeEvents : name === "worstcase" ? (await import("./worstcase-fixture")).worstcaseEvents : (await import("./replay-fixture")).scoutingEvents;
  for (const [type, data] of events) {
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
