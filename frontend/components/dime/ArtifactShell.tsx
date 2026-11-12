"use client";

import { useState } from "react";

function Ico({ d, size = 14 }: { d: React.ReactNode; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" aria-hidden>{d}</svg>
  );
}

const iconBtn =
  "flex size-7 items-center justify-center rounded-[6px] text-ink-3 transition-[background-color,color,transform] duration-150 hover:bg-hover hover:text-ink active:scale-[0.94]";

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
};

function sourceLabel(source?: string) {
  if (!source) return null;
  const head = source.split("·")[0].trim();
  return SOURCE_LABELS[head] ?? source.trim();
}

export default function ArtifactShell({
  title,
  source,
  copyText,
  delay = 0,
  children,
}: {
  title: string;
  source?: string;
  copyText?: string;
  delay?: number;
  children: React.ReactNode;
}) {
  const [tall, setTall] = useState(false);
  const [copied, setCopied] = useState(false);
  const label = sourceLabel(source);

  const copy = async () => {
    const text = copyText ?? title;
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      try {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      } catch {
        return;
      }
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };

  return (
    <div
      className="overflow-hidden rounded-card bg-surface shadow-hairline"
      style={{ animation: "fade-up 280ms cubic-bezier(0.23,1,0.32,1) both", animationDelay: `${delay}ms` }}
    >
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-line pl-4 pr-2">
        <span className="truncate text-[13px] font-semibold text-ink">{title}</span>
        <div className="flex shrink-0 items-center gap-0.5">
          {label && (
            <span className="mr-1.5 truncate text-[11px] text-ink-3">{label}</span>
          )}
          <button type="button" aria-label={tall ? "Collapse" : "Expand"} title={tall ? "Collapse" : "Expand"}
            onClick={() => setTall((v) => !v)} className={iconBtn}>
            <Ico d={tall
              ? <><polyline points="4 14 10 14 10 20" /><polyline points="20 10 14 10 14 4" /><line x1="14" y1="10" x2="21" y2="3" /><line x1="3" y1="21" x2="10" y2="14" /></>
              : <><polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" /><line x1="21" y1="3" x2="14" y2="10" /><line x1="3" y1="21" x2="10" y2="14" /></>} />
          </button>
          <button type="button" aria-label={copied ? "Copied" : copyText ? "Copy data" : "Copy"} title={copied ? "Copied" : copyText ? "Copy data" : "Copy"}
            onClick={copy} className={iconBtn}>
            <Ico d={copied
              ? <path d="M20 6 9 17l-5-5" />
              : <><rect x="9" y="9" width="12" height="12" rx="2.5" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></>} />
          </button>
        </div>
      </div>
      <div
        key={String(tall)}
        className={tall ? "overscroll-contain" : "max-h-[420px] overflow-y-auto overscroll-contain"}
        style={{ animation: "fade-up 160ms cubic-bezier(0.23,1,0.32,1) both" }}
      >{children}</div>
    </div>
  );
}
