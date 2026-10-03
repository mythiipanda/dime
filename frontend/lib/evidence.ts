import type { AiMessage } from "./chat";

export interface EvidenceGap {
  kind?: string;
  blocks?: string[];
}

export interface OutputStatus {
  requirement_kind?: string;
  requirement_id?: string | null;
  output_id?: string;
  status?: string;
  value?: string;
  unit?: string;
  subject_type?: string;
  subject_id?: string | number | null;
}

export interface EvidenceCarry {
  run_id?: string;
  verification?: string;
  verified_claims?: number;
  output_statuses?: OutputStatus[];
  gaps?: EvidenceGap[];
}

export interface EvidenceProvenance {
  capability?: string;
  season?: string;
  as_of?: string;
  source_as_of?: string;
  fetched_at?: string;
  observed_at?: string;
}

export interface EvidenceSource {
  key: string;
  index: number;
  subject: string;
  stat: string;
  value: string;
  origin: string;
}

const CAPABILITY_LABELS: Record<string, string> = {
  get_advanced: "Advanced stats",
  get_award_race: "Award races",
  get_boxscore: "Box scores",
  get_briefing: "Briefing",
  get_cap_ledger: "Cap sheet",
  get_career_totals: "Career totals",
  get_clutch: "Clutch stats",
  get_combine: "Combine",
  get_compare: "Comparison",
  get_competitive_ratings: "Competitive ratings",
  get_comps: "Comparisons",
  get_contract_value: "Contract values",
  get_debate_card: "Debate cards",
  get_draft_board: "Draft board",
  get_draft_model: "Draft model",
  get_elo: "Elo",
  get_elo_standings: "Elo standings",
  get_finder: "Finder",
  get_four_factors: "Four factors",
  get_game_prediction: "Game predictions",
  get_games_on_date: "Games",
  get_head_to_head: "Head-to-head",
  get_historical_leaders: "All-time leaders",
  get_hustle: "Hustle stats",
  get_hustle_boards: "Hustle boards",
  get_impact_estimate: "Impact estimates",
  get_injuries: "Injuries",
  get_injury_impact: "Injury impact",
  get_last_x: "Recent games",
  get_leaderboard_deltas: "Leaderboard changes",
  get_leaders: "League leaders",
  get_lineup_leaders: "Lineup leaders",
  get_lineup_matchup_matrix: "Lineup matchups",
  get_lineup_stats: "Lineup stats",
  get_lineups: "Lineups",
  get_matchup_preview: "Matchup preview",
  get_matchup_splits: "Matchup splits",
  get_morning_briefing: "Morning briefing",
  get_on_off: "On/off",
  get_percentiles: "Percentiles",
  get_player_evaluation: "Player evaluations",
  get_player_intel: "Player intel",
  get_player_rankings: "Player rankings",
  get_player_ratings: "Player ratings",
  get_player_report: "Player reports",
  get_player_risers: "Player risers",
  get_playoff_intel: "Playoff intel",
  get_playoff_sim: "Playoff simulator",
  get_playoff_team_ratings: "Playoff team ratings",
  get_playoffs: "Playoffs",
  get_preview: "Preview",
  get_rapm: "RAPM",
  get_rapm_prior: "RAPM priors",
  get_raptor_history: "RAPTOR history",
  get_ratings: "Team ratings",
  get_recap: "Recaps",
  get_regression_check: "Regression checks",
  get_rest: "Rest",
  get_rest_advantage: "Rest advantage",
  get_risers: "Risers",
  get_rookie_leaders: "Rookie leaders",
  get_rotation_check: "Rotations",
  get_scout_pack: "Scout pack",
  get_scouting_report: "Scouting reports",
  get_season_averages: "Season averages",
  get_season_series: "Season series",
  get_shot_compare: "Shot comparison",
  get_shot_zones: "Shot zones",
  get_team_compare: "Team comparison",
  get_team_four_factors: "Four factors",
  get_team_game_log: "Game log",
  get_team_hub: "Team hub",
  get_team_leaders: "Team leaders",
  get_team_shot_zones: "Shot zones",
  get_team_splits: "Team splits",
  get_team_trajectory: "Trajectory",
  get_today: "Today's games",
  get_trade_check: "Trade checker",
  get_trade_value: "Trade values",
  get_trend: "Trends",
  get_warehouse_freshness: "Data freshness",
  get_watchlist: "Watchlist",
  get_win_prob: "Win probability",
  get_wowy: "With or without you",
  get_wpa_leaders: "WPA leaders",
  get_young_player_usage: "Young player usage",
  get_zone_deltas: "Zone changes",
  qualified_leaders: "League leaders",
  team_ratings: "Team ratings",
};

const STAT_LABELS: Record<string, string> = {
  APG: "assists per game",
  AST: "assists",
  AST_PCT: "assist %",
  BLK: "blocks",
  BPG: "blocks per game",
  DEF_RATING: "defensive rating",
  DREB: "defensive rebounds",
  DRTG: "defensive rating",
  EFG_PCT: "effective field goal %",
  ELO: "Elo",
  FG_PCT: "field goal %",
  FG3_PCT: "three-point %",
  FT_PCT: "free throw %",
  GP: "games",
  GS: "starts",
  L: "losses",
  MIN: "minutes",
  MPG: "minutes per game",
  NET_RATING: "net rating",
  NRTG: "net rating",
  OFF_RATING: "offensive rating",
  OREB: "offensive rebounds",
  ORTG: "offensive rating",
  PACE: "pace",
  PF: "fouls",
  PLAYER_NAME: "",
  PLUS_MINUS: "plus/minus",
  PPG: "points per game",
  PTS: "points",
  REB: "rebounds",
  REB_PCT: "rebound %",
  RPG: "rebounds per game",
  SPG: "steals per game",
  STL: "steals",
  TEAM_NAME: "",
  TOPG: "turnovers per game",
  TOV: "turnovers",
  TS_PCT: "true shooting %",
  USG_PCT: "usage %",
  W: "wins",
  WIN_PCT: "win %",
};

const TEAM_NAMES: Record<string, string> = {
  ATL: "Atlanta",
  BOS: "Boston",
  BKN: "Brooklyn",
  CHA: "Charlotte",
  CHI: "Chicago",
  CLE: "Cleveland",
  DAL: "Dallas",
  DEN: "Denver",
  DET: "Detroit",
  GSW: "Golden State",
  HOU: "Houston",
  IND: "Indiana",
  LAC: "LA Clippers",
  LAL: "LA Lakers",
  MEM: "Memphis",
  MIA: "Miami",
  MIL: "Milwaukee",
  MIN: "Minnesota",
  NOP: "New Orleans",
  NYK: "New York",
  OKC: "Oklahoma City",
  ORL: "Orlando",
  PHI: "Philadelphia",
  PHX: "Phoenix",
  POR: "Portland",
  SAC: "Sacramento",
  SAS: "San Antonio",
  TOR: "Toronto",
  UTA: "Utah",
  WAS: "Washington",
};

const SUPERSCRIPTS = ["¹", "²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹"];

function plainWords(token: string): string {
  return String(token || "")
    .split(/[_-]+/)
    .map((w) => w.trim())
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function sentenceCase(token: string): string {
  const words = plainWords(token).split(" ");
  if (words.length > 1 && (words[0] === "get" || words[0] === "fetch")) words.shift();
  const joined = words.join(" ");
  return joined ? joined.charAt(0).toUpperCase() + joined.slice(1) : joined;
}

export function capabilityLabel(capability: string): string {
  const key = String(capability || "");
  if (CAPABILITY_LABELS[key]) return CAPABILITY_LABELS[key];
  const words = sentenceCase(key);
  return words || "Data";
}

export function statLabel(outputId: string): string {
  const key = String(outputId || "").toUpperCase();
  if (key in STAT_LABELS) return STAT_LABELS[key];
  return sentenceCase(key);
}

export function subjectName(type: unknown, id: unknown): string {
  if (id === null || id === undefined || id === "") return "";
  const raw = String(id);
  if (typeof type === "string" && type.toLowerCase() === "team") {
    const upper = raw.toUpperCase();
    return TEAM_NAMES[upper] || raw;
  }
  if (/^\d+$/.test(raw)) return "";
  return raw;
}

export function gapMessage(kind: string): string {
  const key = String(kind || "");
  switch (key) {
    case "missing_evidence":
      return "No data covered this.";
    case "source_conflict":
      return "Sources disagreed on this.";
    case "unsupported_claim":
      return "The data did not back this.";
    case "execution_failure":
      return "The lookup failed.";
    case "synthesis_incomplete":
      return "This did not reach the answer.";
    case "judge_unavailable":
      return "Dime could not double-check this.";
    case "run_timeout":
      return "The run ran out of time.";
    case "":
      return "No reason given.";
    default:
      return sentenceCase(key) + ".";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function allTables(ai: AiMessage): unknown[] {
  const out: unknown[] = [];
  const nodes = ai.nodes || {};
  for (const node of Object.values(nodes)) {
    if (!node || !Array.isArray(node.tables)) continue;
    out.push(...node.tables);
  }
  return out;
}

function originText(provenance: unknown): string {
  if (!isRecord(provenance)) return "";
  const p = provenance as EvidenceProvenance;
  const parts: string[] = [];
  if (p.capability) parts.push(capabilityLabel(String(p.capability)));
  if (p.season) parts.push(String(p.season) + " season");
  return parts.join(", ");
}

function statText(outputId: string, unit: unknown): string {
  if (typeof unit === "string" && unit && unit !== "unitless") return plainWords(unit);
  return statLabel(outputId);
}

function displayStat(outputId: string, unit: unknown, table: Record<string, unknown>): string {
  const name = table.display_name;
  if (typeof name === "string" && name.trim()) return name.trim();
  return statText(outputId, unit);
}

function displaySubject(table: Record<string, unknown>): string {
  const name = table.subject_display_name;
  if (typeof name === "string" && name.trim()) return name.trim();
  const resolved = subjectName(table.subject_type, table.subject_id);
  if (resolved) return resolved;
  const raw = table.subject_id;
  return raw === null || raw === undefined ? "" : String(raw);
}

function tableSource(table: unknown, index: number): EvidenceSource | null {
  if (!isRecord(table)) return null;
  const t = table as Record<string, unknown>;
  if (isRecord(t.provenance) || typeof t.output_id === "string") {
    const outputId = typeof t.output_id === "string" ? t.output_id : "";
    const rawValue = t.value !== undefined ? t.value : t.input_value;
    const value = rawValue === null || rawValue === undefined ? "" : String(rawValue);
    return {
      key: "claim-" + index,
      index,
      subject: displaySubject(t),
      stat: displayStat(outputId, t.unit, t),
      value,
      origin: originText(t.provenance),
    };
  }
  if (typeof t.tool === "string") {
    return {
      key: "tool-" + index,
      index,
      subject: "",
      stat: capabilityLabel(t.tool),
      value: "",
      origin: originText(t.meta),
    };
  }
  return null;
}

export function evidenceSources(ai: AiMessage): EvidenceSource[] {
  const sources: EvidenceSource[] = [];
  allTables(ai).forEach((table, index) => {
    const source = tableSource(table, index);
    if (source) sources.push({ ...source, index: sources.length });
  });
  return sources;
}

function carryOf(ai: AiMessage): EvidenceCarry {
  return (ai.carry || {}) as EvidenceCarry;
}

function incompleteLabels(ai: AiMessage): string[] {
  const carry = carryOf(ai);
  const statuses = Array.isArray(carry.output_statuses) ? carry.output_statuses : [];
  const labels: string[] = [];
  statuses.forEach((status) => {
    if (!status || status.status === "complete") return;
    const outputId = typeof status.output_id === "string" ? status.output_id : "";
    const label = subjectName(status.subject_type, status.subject_id) || statLabel(outputId);
    labels.push(label || "a stat");
  });
  return labels;
}

function reasonText(ai: AiMessage): string {
  const carry = carryOf(ai);
  const gaps = Array.isArray(carry.gaps) ? carry.gaps : [];
  const raw = gaps.length ? gapMessage(gaps[0].kind || "") : "No reason given.";
  return raw.charAt(0).toLowerCase() + raw.slice(1);
}

export function unverifiedSummary(ai: AiMessage): string | null {
  const sources = evidenceSources(ai);
  const labels = incompleteLabels(ai);
  const carry = carryOf(ai);
  const gaps = Array.isArray(carry.gaps) ? carry.gaps : [];
  const statuses = Array.isArray(carry.output_statuses) ? carry.output_statuses : [];
  const signal = gaps.length > 0 || statuses.length > 0 || sources.length > 0;
  if (!signal) return null;
  if (labels.length === 0) {
    if (gaps.length === 0) return null;
    return "Dime couldn't check this answer — " + reasonText(ai);
  }
  const n = labels.length;
  return n === 1
    ? "1 number couldn't be traced to source data."
    : n + " numbers couldn't be traced to source data.";
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function withCitationMarkers(text: string, sources: EvidenceSource[]): string {
  if (!text || sources.length === 0) return text;
  const byValue = new Map<string, EvidenceSource[]>();
  sources.forEach((source) => {
    if (source.index >= SUPERSCRIPTS.length) return;
    if (!/^(?:\d{2,}(?:\.\d+)?|\d\.\d+)$/.test(source.value)) return;
    const list = byValue.get(source.value) || [];
    list.push(source);
    byValue.set(source.value, list);
  });
  let out = text;
  byValue.forEach((list, value) => {
    if (list.length !== 1) return;
    const rx = new RegExp("(?<![\\d.])" + escapeRegExp(value) + "(?!\\d|\\.\\d)", "g");
    const matches = out.match(rx);
    if (!matches || matches.length !== 1) return;
    const marker = "[" + SUPERSCRIPTS[list[0].index] + "](#cite-" + list[0].index + ")";
    out = out.replace(rx, value + marker);
  });
  return out;
}
