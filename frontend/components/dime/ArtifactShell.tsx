"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Copy } from "iconoir-react";
import { Button } from "@/components/ds/Button";
import { Surface } from "@/components/ds/Panel";

const SOURCE_LABELS: Record<string, string> = {
  silver_boxscores: "Player game logs",
  silver_schedule: "League schedule",
  silver_lineups: "Lineup data",
  silver_team_ratings: "Team ratings",
  silver_players: "Player profiles",
  tracking_feed: "Tracking feed",
  silver_rapm: "RAPM ratings",
  silver_rapm_prior: "RAPM priors",
  silver_bbref_awards: "NBA awards",
  silver_combine: "Draft combine",
  silver_rosters: "Team rosters",
  silver_stints: "Lineup stints",
  silver_playoff_gamelogs: "Playoff logs",
  silver_gamelogs: "Game logs",
  get_rapm: "RAPM model",
  get_game_prediction: "Game simulation",
  get_wpa_leaders: "WPA leaderboard",
  get_comps: "Player comps",
  get_lineup_stats: "Lineup ratings",
  get_lineup_on_off: "Unit on/off splits",
  get_win_prob: "Win probability",
  get_on_off: "On/off splits",
  get_shot_zones: "Shot zones",
  get_four_factors: "Four factors",
  get_clutch_stats: "Clutch stats",
  get_competitive_ratings: "Competitive ratings",
  get_hustle: "Hustle stats",
  get_injuries: "Injury report",
  get_award_results: "Award voting",
  get_award_race: "Award races",
  get_last_x: "Recent games",
  get_player_report: "Player report",
  get_team_hub: "Team hub",
  get_briefing: "League briefing",
  get_watchlist: "Watchlist",
  get_standings: "Standings",
  get_rest: "Rest splits",
  get_team_trajectory: "Team trajectory",
  get_ratings: "Team ratings",
  get_rookie_leaders: "Rookie leaderboard",
  get_cap_ledger: "Salary cap & apron",
  get_leaders: "Statistical leaders",
  get_lineup_leaders: "Lineup net rating",
  get_playoffs: "Playoff results",
  get_team_leaders: "Team leaders",
  get_team_compare: "Team compare",
  get_elo_standings: "ELO standings",
  get_draft_board: "Draft board",
  get_combine: "Combine testing",
  get_young_player_usage: "Young player usage",
  get_contract_value: "Contract value",
  get_salary_history: "Salary history",
  get_trade_check: "Trade check",
  get_trade_value: "Trade value",
  get_situational_splits: "Situational splits",
  get_playoff_sim: "Playoff simulation",
  get_playoff_team_ratings: "Playoff ratings",
  get_player_risers: "Player form trends",
  get_standings_deep: "Deep standings",
  get_warehouse_freshness: "Warehouse freshness",
  get_finder: "Historical finder",
  get_draft_model: "Draft model",
  get_leaderboard_deltas: "Leaderboard deltas",
  get_player_ratings: "Player ratings",
  get_risers: "Team risers",
  get_team_four_factors: "Team four factors",
  get_streaks: "Streaks",
  get_playtype_profile: "Synergy Play Types",
  get_defensive_matchups: "Defensive Tracking",
  get_head_to_head: "Head-to-head",
  get_lineup_matchup_matrix: "Lineup matrix",
  get_transactions: "Transactions",
  get_wowy: "WOWY splits",
  get_shot_compare: "Shot compare",
  get_raptor_history: "RAPTOR history",
  get_season_series: "Season series",
  get_team_game_log: "Team game log",
  get_zone_deltas: "Zone deltas",
  search_shots: "Shot search",
  get_stint_timeline: "Stint timeline",
  get_possession_log: "Possession log",
  get_elo: "ELO ratings",
  get_team_shot_zones: "Team shot zones",
  get_historical_leaders: "Historical leaders",
  get_today: "Today slate",
  get_morning_briefing: "Morning briefing",
  get_tracking_profile: "Tracking profile",
  get_rest_advantage: "Rest advantage",
  get_rapm_prior: "RAPM prior",
  search_game_logs: "Game log search",
  get_dataset: "Data engine",
  get_dataset_freshness: "Data freshness",
  get_career_arc: "Career arc",
  run_python: "Python execution",
  get_matchup_preview: "Matchup preview",
  get_matchup_splits: "Matchup splits",
  get_regression_check: "Regression check",
  get_scout_pack: "Scout pack",
  get_rotation_check: "Rotation check",
  get_injury_impact: "Injury impact",
  get_matchup_brief: "Matchup brief",
  get_games_on_date: "Games on date",
  get_boxscore: "Box score",
  get_lineups: "Team lineups",
  get_splits: "Player splits",
  get_recap: "Game recap",
  get_scouting_report: "Scouting report",
};

function sourceLabel(source?: string) {
  if (!source || source === "source not declared") return null;
  const head = source.split("·")[0].trim();
  return SOURCE_LABELS[head] ?? source.trim();
}

export default function ArtifactShell({
  title,
  source,
  copyText,
  actions,
  children,
}: {
  title: string;
  source?: string;
  copyText?: string;
  actions?: React.ReactNode;
  delay?: number;
  children: React.ReactNode;
}) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  const label = sourceLabel(source);

  const copy = async () => {
    setError(false);
    setCopied(false);
    try {
      await navigator.clipboard.writeText(copyText ?? title);
    } catch {
      setError(true);
      return;
    }
    setCopied(true);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopied(false), 1600);
  };

  return (
    <Surface className="artifact-enter relative min-w-0 overflow-hidden">
      <header className="flex flex-wrap items-start justify-between gap-2 border-b border-line px-4 py-3">
        <div className="min-w-0 flex-1"><h3 className="break-words text-[15px] font-medium tracking-tight text-ink">{title}</h3>{label && <p className="mt-1 break-words text-xs text-ink-3">{label}</p>}</div>
        <div className="flex items-center gap-1">{actions}<Button size="icon" variant="quiet" aria-label={copied ? "Copied" : copyText ? "Copy data" : "Copy"} title={copied ? "Copied" : copyText ? "Copy data" : "Copy"} onClick={copy}>{copied ? <Check width={14} height={14} aria-hidden="true" /> : <Copy width={14} height={14} aria-hidden="true" />}</Button></div>
      </header>
      <div className="min-w-0">{children}</div>
      <p role="status" className={error ? "px-4 pb-3 text-xs text-red" : "sr-only"}>{error ? "Could not copy. Select the visible data and copy it manually." : copied ? "Data copied." : ""}</p>
    </Surface>
  );
}
