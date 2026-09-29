// Shareable panel URLs (redesign Phase 3, PBPStats style). Pure helpers:
// given the current query string, keep only the params that belong to one
// panel so "Copy link" copies a URL that reproduces that panel's view.
// Panel param names match what each panel already reads/writes.





export const PANEL_PARAM_KEYS: Record<string, string[]> = {
  leaders: ["leaders_stat", "leaders_sort", "leaders_q", "leaders_pct", "standings_season"],
  shots: ["shots_player", "shots_season", "gamelog_player", "gamelog_sort", "gamelog_q"],
  trade: ["trade_a", "trade_pa", "trade_b", "trade_pb"],
  draft: ["draft_year", "draft_sort", "draft_q"],
  lineups: ["lineups_team", "lineups_tab", "wowy_a", "wowy_b"],
  playoffs: [],
};
/** Parse "?a=1&b=2" (or "a=1&b=2") into a plain object. */


export function decodeParams(qs: string): Record<string, string> {
  const out: Record<string, string> = {};
  const clean = qs.startsWith("?") ? qs.slice(1) : qs;
  if (!clean) return out;
  for (const part of clean.split("&")) {
    const eq = part.indexOf("=");
    if (eq < 0) continue;
    const k = decodeURIComponent(part.slice(0, eq).replace(/\+/g, " "));
    const v = decodeURIComponent(part.slice(eq + 1).replace(/\+/g, " "));
    if (k) out[k] = v;
  }
  return out;
}
/** Encode a plain object as a query string (no leading "?"). */


export function encodeParams(params: Record<string, string>): string {
  return Object.entries(params)
    .filter(([, v]) => v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join("&");
}
/** Keep only the entries whose key is in `keys`. */


export function pickParams(
  params: Record<string, string>,
  keys: string[],
): Record<string, string> {
  const keep = new Set(keys);
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(params)) {
    if (keep.has(k) && v !== "") out[k] = v;
  }
  return out;
}
/**
 * Shareable URL for one panel: origin + path, the panel anchor as hash,
 * and only that panel's params plus the panel id. Reading the URL back
 * (panel id + params) reproduces the view.
 */


export function panelShareUrl(
  origin: string,
  path: string,
  currentQs: string,
  panel: string,
  anchor?: string,
): string {
  const keys = PANEL_PARAM_KEYS[panel] ?? [];
  const kept = pickParams(decodeParams(currentQs), keys);
  kept.panel = panel;
  const qs = encodeParams(kept);
  return `${origin}${path}${qs ? `?${qs}` : ""}#explore-${anchor ?? panel}`;
}
