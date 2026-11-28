import { asNumber, asRecord, asString, type ToolActivityStatus } from "./types";

type ToolNarration = { running: string; done: string };

const TOOL_LABELS: Record<string, ToolNarration> = {
  entity_resolution: { running: "Resolving players and teams", done: "Resolved players and teams" },
  warehouse_freshness: { running: "Checking data freshness", done: "Checked data freshness" },
  standings: { running: "Pulling standings", done: "Pulled standings" },
  team_trajectory: { running: "Charting team trajectory", done: "Charted team trajectory" },
  team_totals: { running: "Pulling team totals", done: "Pulled team totals" },
  qualified_leaders: { running: "Pulling league leaders", done: "Pulled league leaders" },
  team_splits: { running: "Pulling team splits", done: "Pulled team splits" },
  injury_impact: { running: "Checking injury impact", done: "Checked injury impact" },
  lineup_matchups: { running: "Building lineup matchups", done: "Built lineup matchups" },
  competitive_ratings: { running: "Computing competitive ratings", done: "Computed competitive ratings" },
  injuries: { running: "Checking injuries", done: "Checked injuries" },
  team_shot_zones: { running: "Mapping team shot zones", done: "Mapped team shot zones" },
  player_shot_zones: { running: "Mapping shot zones", done: "Mapped shot zones" },
  rest_splits: { running: "Pulling rest splits", done: "Pulled rest splits" },
  rookie_leaders: { running: "Pulling rookie leaders", done: "Pulled rookie leaders" },
  team_ratings: { running: "Pulling team ratings", done: "Pulled team ratings" },
  shots: { running: "Pulling shot data", done: "Pulled shot data" },
  shooting_efficiency: { running: "Computing shooting efficiency", done: "Computed shooting efficiency" },
  on_off: { running: "Computing on/off numbers", done: "Computed on/off numbers" },
  lineups: { running: "Pulling lineup data", done: "Pulled lineup data" },
  clutch: { running: "Pulling clutch numbers", done: "Pulled clutch numbers" },
  player_ratings: { running: "Pulling player ratings", done: "Pulled player ratings" },
  playoff_team_ratings: { running: "Pulling playoff ratings", done: "Pulled playoff ratings" },
  game_prediction: { running: "Running game prediction", done: "Ran game prediction" },
  get_rapm: { running: "Computing RAPM ratings", done: "Computed RAPM ratings" },
  get_game_prediction: { running: "Simulating game matchup", done: "Simulated game matchup" },
  get_wpa_leaders: { running: "Pulling WPA leaders", done: "Pulled WPA leaders" },
  get_comps: { running: "Finding player comps", done: "Found player comps" },
  get_lineup_stats: { running: "Analyzing lineup ratings", done: "Analyzed lineup ratings" },
  get_lineup_on_off: { running: "Comparing unit on/off splits", done: "Compared unit on/off splits" },
  get_win_prob: { running: "Computing ELO win probabilities\u2026", done: "Computed ELO win probabilities" },
  get_on_off: { running: "Calculating on/off net ratings\u2026", done: "Calculated on/off net ratings" },
  get_shot_zones: { running: "Analyzing shot distribution zones\u2026", done: "Analyzed shot distribution zones" },
  get_four_factors: { running: "Analyzing four factors", done: "Analyzed four factors" },
  get_clutch_stats: { running: "Pulling clutch statistics", done: "Pulled clutch statistics" },
  get_competitive_ratings: { running: "Calculating competitive ratings", done: "Calculated competitive ratings" },
  get_hustle: { running: "Analyzing hustle stats", done: "Analyzed hustle stats" },
  get_injuries: { running: "Checking injury report", done: "Checked injury report" },
  get_award_results: { running: "Looking up award voting results", done: "Looked up award voting results" },
  get_award_race: { running: "Ranking the award race", done: "Ranked the award race" },
  get_last_x: { running: "Pulling recent game logs", done: "Pulled recent game logs" },
  get_player_report: { running: "Building the player report", done: "Built the player report" },
  get_team_hub: { running: "Building the team hub", done: "Built the team hub" },
  get_lineups: { running: "Pulling team lineups", done: "Pulled team lineups" },
  get_splits: { running: "Splitting player game logs", done: "Split player game logs" },
  get_recap: { running: "Pulling the game recap", done: "Pulled the game recap" },
  get_scouting_report: { running: "Building the scouting report", done: "Built the scouting report" },
  get_briefing: { running: "Pulling morning briefing and scores", done: "Pulled morning briefing and scores" },
  get_standings: { running: "Fetching league standings", done: "Fetched league standings" },
  get_rest: { running: "Analyzing rest and back-to-back splits", done: "Analyzed rest and back-to-back splits" },
  get_team_trajectory: { running: "Evaluating team multi-season trajectory", done: "Evaluated team multi-season trajectory" },
  get_ratings: { running: "Fetching team ratings and pace", done: "Fetched team ratings and pace" },
  get_rookie_leaders: { running: "Analyzing rookie leaderboard", done: "Analyzed rookie leaderboard" },
  get_cap_ledger: { running: "Checking salary cap and apron room", done: "Checked salary cap and apron room" },
  get_cap_table: { running: "Checking the league cap table", done: "Checked the league cap table" },
  get_leaders: { running: "Fetching league statistical leaders", done: "Fetched league statistical leaders" },
  get_lineup_leaders: { running: "Evaluating 5-man lineup net ratings", done: "Evaluated 5-man lineup net ratings" },
  get_playoffs: { running: "Reviewing playoff series and championship", done: "Reviewed playoff series and championship" },
  get_team_leaders: { running: "Fetching team counting stat leaders", done: "Fetched team counting stat leaders" },
  get_team_compare: { running: "Comparing team statistical profiles and records", done: "Compared team statistical profiles and records" },
  get_elo_standings: { running: "Evaluating ELO power ratings and spreads", done: "Evaluated ELO power ratings and spreads" },
  get_draft_board: { running: "Evaluating draft board rankings and prospects", done: "Evaluated draft board rankings and prospects" },
  get_combine: { running: "Reviewing draft combine anthropometrics and athletic testing", done: "Reviewed draft combine anthropometrics and athletic testing" },
  get_young_player_usage: { running: "Analyzing young player usage rates and thresholds", done: "Analyzed young player usage rates and thresholds" },
  get_salary_history: { running: "Pulling salary history and cap context", done: "Pulled salary history and cap context" },
  get_contract_value: { running: "Evaluating contract surplus and value residuals", done: "Evaluated contract surplus and value residuals" },
  get_trade_check: { running: "Verifying trade legality and CBA matching rules", done: "Verified trade legality and CBA matching rules" },
  get_trade_value: { running: "Grading trade value and player equity", done: "Graded trade value and player equity" },
  get_situational_splits: { running: "Analyzing clutch situational splits", done: "Analyzed clutch situational splits" },
  get_playoff_sim: { running: "Simulating playoff bracket and championship odds", done: "Simulated playoff bracket and championship odds" },
  get_playoff_team_ratings: { running: "Analyzing postseason offensive and defensive ratings", done: "Analyzed postseason offensive and defensive ratings" },
  get_player_risers: { running: "Evaluating player scoring and efficiency form trends", done: "Evaluated player scoring and efficiency form trends" },
  get_standings_deep: { running: "Analyzing situational standings, clutch records, and comebacks", done: "Analyzed situational standings, clutch records, and comebacks" },
  get_warehouse_freshness: { running: "Inspecting warehouse tables and data freshness", done: "Inspected warehouse tables and data freshness" },
  get_finder: { running: "Searching historical streaks and matchups", done: "Searched historical streaks and matchups" },
  get_draft_model: { running: "Computing draft prospect star probabilities", done: "Computed draft prospect star probabilities" },
  get_leaderboard_deltas: { running: "Tracking leaderboard rank and scoring movements", done: "Tracked leaderboard rank and scoring movements" },
  get_player_ratings: { running: "Pulling qualified player on-court ratings", done: "Pulled qualified player on-court ratings" },
  get_risers: { running: "Calculating team win percentage trends and movers", done: "Calculated team win percentage trends and movers" },
  get_team_four_factors: { running: "Analyzing team four factors and efficiency profiles", done: "Analyzed team four factors and efficiency profiles" },
  get_streaks: { running: "Scanning streak leaderboards", done: "Scanned streak leaderboards" },
  get_playtype_profile: { running: "Analyzing Synergy play types", done: "Analyzed Synergy play types" },
  get_defensive_matchups: { running: "Evaluating defensive shot tracking", done: "Evaluated defensive shot tracking" },
  get_head_to_head: { running: "Pulling head-to-head matchup history", done: "Pulled head-to-head matchup history" },
  get_lineup_matchup_matrix: { running: "Building lineup matchup matrix", done: "Built lineup matchup matrix" },
  get_transactions: { running: "Fetching front-office transactions", done: "Fetched front-office transactions" },
  get_wowy: { running: "Computing WOWY lineup splits", done: "Computed WOWY lineup splits" },
  get_shot_compare: { running: "Comparing shot-diet distributions", done: "Compared shot-diet distributions" },
  get_raptor_history: { running: "Loading RAPTOR career history", done: "Loaded RAPTOR career history" },
  get_season_series: { running: "Fetching season series meetings", done: "Fetched season series meetings" },
  get_team_game_log: { running: "Pulling team game log", done: "Pulled team game log" },
  get_zone_deltas: { running: "Calculating shooting zone deltas", done: "Calculated shooting zone deltas" },
  search_shots: { running: "Searching shot log", done: "Searched shot log" },
  get_stint_timeline: { running: "Building stint timeline", done: "Built stint timeline" },
  get_possession_log: { running: "Pulling possession log", done: "Pulled possession log" },
  get_elo: { running: "Calculating ELO ratings", done: "Calculated ELO ratings" },
  get_team_shot_zones: { running: "Computing team shot zones", done: "Computed team shot zones" },
  get_historical_leaders: { running: "Fetching historical leaders", done: "Fetched historical leaders" },
  get_today: { running: "Pulling today scoreboard", done: "Pulled today scoreboard" },
  get_morning_briefing: { running: "Compiling morning briefing", done: "Compiled morning briefing" },
  get_tracking_profile: { running: "Querying player tracking profile", done: "Queried player tracking profile" },
  get_rest_advantage: { running: "Computing rest advantage and schedule fatigue", done: "Computed rest advantage and schedule fatigue" },
  get_rapm_prior: { running: "Blending RAPM priors and multi-season weights", done: "Blended RAPM priors and multi-season weights" },
  search_game_logs: { running: "Filtering historical game logs", done: "Filtered historical game logs" },
  four_factors: { running: "Computing four factors", done: "Computed four factors" },
  team_four_factors: { running: "Computing team four factors", done: "Computed team four factors" },
  matchup_brief: { running: "Building matchup brief", done: "Built matchup brief" },
  season_series: { running: "Pulling season series", done: "Pulled season series" },
  head_to_head: { running: "Pulling head-to-head", done: "Pulled head-to-head" },
  matchup_splits: { running: "Pulling matchup splits", done: "Pulled matchup splits" },
  today: { running: "Checking today's games", done: "Checked today's games" },
  morning_briefing: { running: "Building the morning briefing", done: "Built the morning briefing" },
  award_results: { running: "Pulling award results", done: "Pulled award results" },
  player_comparison: { running: "Comparing players", done: "Compared players" },
  sql_exec: { running: "Querying warehouse", done: "Queried warehouse" },
  web_search: { running: "Searching the web", done: "Searched the web" },
  web_fetch: { running: "Reading a web page", done: "Read a web page" },
  tool: { running: "Running a tool", done: "Ran a tool" },
};

export const TOOL_NARRATION = TOOL_LABELS;

export function toolLabelFor(
  name: unknown,
  status: ToolActivityStatus = "running",
): string {
  const key = typeof name === "string" ? name : "";
  const narration = TOOL_LABELS[key] ?? TOOL_LABELS.tool;
  return status === "running" ? narration.running : narration.done;
}

function argumentLine(name: string, value: unknown): string {
  if (typeof value === "string") return `${name}=${value}`;
  return `${name}=${JSON.stringify(value)}`;
}

export function publishableArgumentLines(data: unknown): string[] | undefined {
  const call = asRecord(data);
  const declared = Array.isArray(call.arguments) ? call.arguments : [];
  const lines: string[] = [];
  for (const item of declared) {
    const argument = asRecord(item);
    const name = asString(argument.name);
    if (!name) continue;
    lines.push(argumentLine(name, argument.value));
  }
  const unknown = asNumber(call.unknown_argument_count) ?? 0;
  if (unknown > 0) {
    lines.push(`+${unknown} more not shown`);
  }
  return lines.length ? lines : undefined;
}

const NODE_LABELS: Record<string, string> = {
  entry: "Understanding your question",
  data_retrieval: "Planning the analysis",
  tools: "Gathering the numbers",
  analytics: "Checking the numbers",
  presentation: "Writing the answer",
};

export function thinkingLabelFor(node: unknown): string {
  const key = typeof node === "string" ? node : "";
  return NODE_LABELS[key] ?? "Working";
}

const FAILURE_COPY: Record<string, { title: string; body: string }> = {
  timeout: {
    title: "This took too long",
    body: "The analysis ran past the time limit. Try a narrower question or try again.",
  },
  quota: {
    title: "The model is out of quota",
    body: "Dime's model hit its usage limit. Your question is fine; try again in a little while.",
  },
  rate_limited: {
    title: "Too many requests",
    body: "Slow down a touch and try again in a minute.",
  },
  execution_failure: {
    title: "Some data was unavailable",
    body: "Dime couldn't pull everything this question needed. Try again or narrow the question.",
  },
  provider_error: {
    title: "The analyst is down",
    body: "Dime's model provider didn't respond. Nothing is wrong with your question; try again shortly.",
  },
  connection: {
    title: "Couldn't reach Dime",
    body: "The connection to the backend dropped. Check your connection and try again.",
  },
  startup: {
    title: "Couldn't start this run",
    body: "Dime couldn't start the analysis. Try again in a moment.",
  },
};

export function failureCopy(kind: string): { title: string; body: string } {
  return (
    FAILURE_COPY[kind] ?? {
      title: "Something went wrong",
      body: "Dime hit an unexpected problem. Try again in a moment.",
    }
  );
}
