type Runtime = "v1" | "v2";

export function apiRuntime(): Runtime {
  return process.env.NEXT_PUBLIC_API_RUNTIME === "v2" ? "v2" : "v1";
}

export function chatRuntime(): Runtime {
  return process.env.NEXT_PUBLIC_CHAT_RUNTIME === "v2" ? "v2" : "v1";
}
