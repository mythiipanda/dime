








const PANEL_PARAM_KEYS: Record<string, string[]> = {
  leaders: ["leaders_stat", "leaders_sort", "leaders_q", "leaders_pct", "standings_season", "lb_season", "lb_mode", "lb_q", "lb_sort", "lb_dir", "adv_tab", "adv_season", "adv_minposs", "adv_sort", "adv_dir", "adv_q"],
  shots: ["shots_player", "shots_season", "gamelog_player", "gamelog_sort", "gamelog_q", "zone_player", "zone_pname", "zone_season"],
  trade: ["trade_a", "trade_pa", "trade_b", "trade_pb"],
  draft: ["draft_year", "draft_sort", "draft_q"],
  lineups: ["lineups_team", "lineups_tab", "wowy_a", "wowy_b"],
  playoffs: [],
};



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



export function encodeParams(params: Record<string, string>): string {
  return Object.entries(params)
    .filter(([, v]) => v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join("&");
}



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
