// Player Statistics Models
export interface BasicPlayerStats {
  games_played: number;
  minutes_per_game: number;
  points_per_game: number;
  rebounds_per_game: number;
  assists_per_game: number;
  steals_per_game: number;
  blocks_per_game: number;
  turnovers_per_game: number;
  field_goal_percentage: number;
  three_point_percentage: number;
  free_throw_percentage: number;
  field_goals_made: number;
  field_goals_attempted: number;
  three_pointers_made: number;
  three_pointers_attempted: number;
  free_throws_made: number;
  free_throws_attempted: number;
}

export interface AdvancedPlayerStats {
  player_efficiency_rating: number;
  true_shooting_percentage: number;
  effective_field_goal_percentage: number;
  usage_rate: number;
  assist_percentage: number;
  rebound_percentage: number;
  steal_percentage: number;
  block_percentage: number;
  turnover_percentage: number;
  offensive_rating: number;
  defensive_rating: number;
  net_rating: number;
  box_plus_minus: number;
  value_over_replacement: number;
  win_shares: number;
  win_shares_per_48: number;
}

export interface ShootingStats {
  restricted_area_fg_pct: number;
  in_paint_non_ra_fg_pct: number;
  mid_range_fg_pct: number;
  left_corner_3_fg_pct: number;
  right_corner_3_fg_pct: number;
  above_break_3_fg_pct: number;
  backcourt_fg_pct: number;
  shot_chart_data: ShotChartPoint[];
}

export interface ShotChartPoint {
  x: number;
  y: number;
  made: boolean;
  shot_type: string;
  distance: number;
  quarter: number;
  time_remaining: string;
  game_date: string;
  opponent: string;
}

export interface DefensiveStats {
  defensive_field_goal_percentage: number;
  defensive_rebounds_per_game: number;
  defensive_rating: number;
  steals_per_game: number;
  blocks_per_game: number;
  deflections_per_game: number;
  loose_balls_recovered: number;
  charges_drawn: number;
  contested_shots: number;
  contested_2pt_shots: number;
  contested_3pt_shots: number;
}

export interface PlaymakingStats {
  assists_per_game: number;
  potential_assists: number;
  assist_percentage: number;
  assist_to_turnover_ratio: number;
  secondary_assists: number;
  passes_made: number;
  passes_received: number;
  screen_assists: number;
  screen_assist_points: number;
}

export interface ReboundingStats {
  total_rebounds_per_game: number;
  offensive_rebounds_per_game: number;
  defensive_rebounds_per_game: number;
  rebound_percentage: number;
  offensive_rebound_percentage: number;
  defensive_rebound_percentage: number;
  contested_rebounds: number;
  uncontested_rebounds: number;
  rebound_chances: number;
}

export interface PlayerBioInfo {
  player_id: number;
  player_name: string;
  first_name: string;
  last_name: string;
  display_first_last: string;
  display_last_comma_first: string;
  display_fi_last: string;
  birthdate: string;
  school: string;
  country: string;
  last_affiliation: string;
  height: string;
  weight: string;
  season_exp: number;
  jersey: string;
  position: string;
  rosterstatus: string;
  team_id: number;
  team_name: string;
  team_abbreviation: string;
  team_code: string;
  team_city: string;
  playercode: string;
  from_year: number;
  to_year: number;
  dleague_flag: string;
  nba_flag: string;
  games_played_flag: string;
  draft_year: string;
  draft_round: string;
  draft_number: string;
}

export interface PlayerProfile {
  bio: PlayerBioInfo;
  basic_stats: BasicPlayerStats;
  advanced_stats: AdvancedPlayerStats;
  shooting_stats: ShootingStats;
  defensive_stats: DefensiveStats;
  playmaking_stats: PlaymakingStats;
  rebounding_stats: ReboundingStats;
  season: string;
  last_updated: string;
}

export interface PlayerComparison {
  players: PlayerProfile[];
  comparison_metrics: {
    [key: string]: {
      values: number[];
      percentiles: number[];
      league_average: number;
      league_rank: number[];
    };
  };
}

export interface PlayerGameLog {
  game_id: string;
  game_date: string;
  matchup: string;
  wl: 'W' | 'L';
  min: number;
  pts: number;
  reb: number;
  ast: number;
  stl: number;
  blk: number;
  tov: number;
  fg_pct: number;
  fg3_pct: number;
  ft_pct: number;
  plus_minus: number;
  video_available: boolean;
}

export interface PlayerSeasonSplits {
  overall: BasicPlayerStats & AdvancedPlayerStats;
  home_away: {
    home: BasicPlayerStats;
    away: BasicPlayerStats;
  };
  by_month: {
    [month: string]: BasicPlayerStats;
  };
  vs_conference: {
    eastern: BasicPlayerStats;
    western: BasicPlayerStats;
  };
  vs_division: {
    [division: string]: BasicPlayerStats;
  };
  clutch_time: BasicPlayerStats;
  by_quarter: {
    q1: BasicPlayerStats;
    q2: BasicPlayerStats;
    q3: BasicPlayerStats;
    q4: BasicPlayerStats;
    ot: BasicPlayerStats;
  };
}

// Utility types for player rankings and awards
export interface PlayerRanking {
  player_id: number;
  player_name: string;
  team_abbreviation: string;
  rank: number;
  value: number;
  percentile: number;
}

export interface PlayerAward {
  season: string;
  award_type: string;
  award_name: string;
  description: string;
  date_awarded: string;
}

export interface PlayerInjury {
  injury_id: string;
  player_id: number;
  injury_type: string;
  body_part: string;
  description: string;
  date_injured: string;
  expected_return: string;
  status: 'Day-to-Day' | 'Week-to-Week' | 'Month-to-Month' | 'Out for Season' | 'Probable' | 'Questionable' | 'Doubtful' | 'Out';
  games_missed: number;
}

// Player performance trends
export interface PlayerTrend {
  metric: string;
  current_value: number;
  previous_value: number;
  change_percentage: number;
  trend_direction: 'up' | 'down' | 'stable';
  games_sample: number;
  significance: 'high' | 'medium' | 'low';
}

export interface PlayerProjection {
  season: string;
  projected_games: number;
  projected_stats: BasicPlayerStats & AdvancedPlayerStats;
  confidence_interval: {
    low: BasicPlayerStats;
    high: BasicPlayerStats;
  };
  factors: string[];
  last_updated: string;
}
