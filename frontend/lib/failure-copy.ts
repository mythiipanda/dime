const BROWSER_FETCH_FAILURES = new Set([
  "failed to fetch",
  "networkerror when attempting to fetch resource.",
  "load failed",
]);

const CONNECTION_COPY = "The network connection dropped before the run finished.";

export function normalizeFailureCopy(message: string): string {
  if (BROWSER_FETCH_FAILURES.has(message.trim().toLowerCase())) return CONNECTION_COPY;
  return message;
}
