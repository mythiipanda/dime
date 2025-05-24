// Team Statistics Models
export interface TeamBasicStats {
  games_played: number;
  wins: number;
  losses: number;
  win_percentage: number;
  points_per_game: number;
  opponent_points_per_game: number;
  point_differential: number;
  field_goal_percentage: number;
  three_point_percentage: number;
  free_throw_percentage: number;
  rebounds_per_game: number;
  assists_per_game: number;
  steals_per_game: number;
  blocks_per_game: number;
  turnovers_per_game: number;
  fouls_per_game: number;
}

export interface TeamAdvancedStats {
  offensive_rating: number;
  defensive_rating: number;
  net_rating: number;
  pace: number;
  effective_field_goal_percentage: number;
  true_shooting_percentage: number;
  turnover_percentage: number;
  offensive_rebound_percentage: number;
  defensive_rebound_percentage: number;
  free_throw_rate: number;
  opponent_effective_field_goal_percentage: number;
  opponent_turnover_percentage: number;
  opponent_offensive_rebound_percentage: number;
  opponent_free_throw_rate: number;
  four_factors_rank: number;
}

export interface TeamShootingStats {
  field_goals_made: number;
  field_goals_attempted: number;
  field_goal_percentage: number;
  three_pointers_made: number;
  three_pointers_attempted: number;
  three_point_percentage: number;
  free_throws_made: number;
  free_throws_attempted: number;
  free_throw_percentage: number;
  points_in_paint: number;
  points_in_paint_percentage: number;
  points_from_mid_range: number;
  points_from_three: number;
  fast_break_points: number;
  second_chance_points: number;
  bench_points: number;
}

export interface TeamDefensiveStats {
  opponent_field_goal_percentage: number;
  opponent_three_point_percentage: number;
  opponent_free_throw_percentage: number;
  opponent_points_in_paint: number;
  opponent_fast_break_points: number;
  opponent_second_chance_points: number;
  steals_per_game: number;
  blocks_per_game: number;
  defensive_rebounds_per_game: number;
  forced_turnovers_per_game: number;
  points_off_turnovers: number;
  defensive_rating: number;
  contested_shots_per_game: number;
  deflections_per_game: number;
}

export interface TeamClutchStats {
  games_played: number;
  wins: number;
  losses: number;
  win_percentage: number;
  points_per_game: number;
  opponent_points_per_game: number;
  field_goal_percentage: number;
  three_point_percentage: number;
  free_throw_percentage: number;
  offensive_rating: number;
  defensive_rating: number;
  net_rating: number;
}

export interface TeamLineupStats {
  lineup_id: string;
  group_name: string;
  players: string[];
  minutes_played: number;
  games_played: number;
  plus_minus: number;
  offensive_rating: number;
  defensive_rating: number;
  net_rating: number;
  pace: number;
  field_goal_percentage: number;
  three_point_percentage: number;
  free_throw_percentage: number;
  effective_field_goal_percentage: number;
  true_shooting_percentage: number;
  usage_percentage: number;
}

export interface TeamRankings {
  offensive_rating_rank: number;
  defensive_rating_rank: number;
  net_rating_rank: number;
  pace_rank: number;
  field_goal_percentage_rank: number;
  three_point_percentage_rank: number;
  free_throw_percentage_rank: number;
  rebounds_per_game_rank: number;
  assists_per_game_rank: number;
  steals_per_game_rank: number;
  blocks_per_game_rank: number;
  turnovers_per_game_rank: number;
  points_per_game_rank: number;
  opponent_points_per_game_rank: number;
}

export interface TeamScheduleStrength {
  overall_sos: number;
  remaining_sos: number;
  home_sos: number;
  away_sos: number;
  conference_sos: number;
  division_sos: number;
  back_to_back_games: number;
  rest_advantage_games: number;
  rest_disadvantage_games: number;
}

export interface TeamInjuryReport {
  total_games_missed: number;
  salary_cap_impact: number;
  key_players_injured: number;
  current_injuries: Array<{
    player_name: string;
    injury_type: string;
    status: string;
    games_missed: number;
    expected_return: string;
  }>;
  injury_history: Array<{
    player_name: string;
    injury_type: string;
    games_missed: number;
    date_injured: string;
    date_returned: string;
  }>;
}

export interface TeamChemistry {
  team_chemistry_score: number;
  ball_movement_rating: number;
  assist_to_turnover_ratio: number;
  unselfish_play_rating: number;
  team_first_rating: number;
  leadership_rating: number;
  veteran_presence_score: number;
  rookie_integration_score: number;
  coaching_impact_score: number;
}

export interface TeamSalaryInfo {
  total_payroll: number;
  luxury_tax_bill: number;
  cap_space: number;
  cap_room: number;
  hard_cap_room: number;
  projected_tax_bill: number;
  repeater_tax_status: boolean;
  trade_exceptions: Array<{
    amount: number;
    expiration_date: string;
    source: string;
  }>;
  contract_breakdown: Array<{
    player_name: string;
    salary: number;
    contract_years_remaining: number;
    player_option: boolean;
    team_option: boolean;
    guaranteed_money: number;
  }>;
}

export interface TeamProfile {
  team_id: number;
  team_name: string;
  team_city: string;
  team_abbreviation: string;
  conference: string;
  division: string;
  founded_year: number;
  arena: string;
  arena_capacity: number;
  head_coach: string;
  general_manager: string;
  owner: string;
  championships: number;
  playoff_appearances: number;
  division_titles: number;
  conference_titles: number;
  retired_numbers: string[];
  team_colors: {
    primary: string;
    secondary: string;
    accent?: string;
  };
  logo_url: string;
  social_media: {
    twitter?: string;
    instagram?: string;
    facebook?: string;
    website?: string;
  };
}

export interface TeamSeasonSummary {
  profile: TeamProfile;
  basic_stats: TeamBasicStats;
  advanced_stats: TeamAdvancedStats;
  shooting_stats: TeamShootingStats;
  defensive_stats: TeamDefensiveStats;
  clutch_stats: TeamClutchStats;
  rankings: TeamRankings;
  schedule_strength: TeamScheduleStrength;
  injury_report: TeamInjuryReport;
  chemistry: TeamChemistry;
  salary_info: TeamSalaryInfo;
  season: string;
  last_updated: string;
}

export interface TeamComparison {
  teams: TeamSeasonSummary[];
  head_to_head_record?: {
    team1_wins: number;
    team2_wins: number;
    last_meeting: string;
    next_meeting: string;
    season_series: Array<{
      date: string;
      winner: string;
      score: string;
      location: string;
    }>;
  };
  comparison_metrics: {
    [key: string]: {
      values: number[];
      ranks: number[];
      league_average: number;
      advantage: string; // which team has advantage
    };
  };
}

export interface TeamTrends {
  last_10_games: TeamBasicStats;
  last_20_games: TeamBasicStats;
  home_record: { wins: number; losses: number };
  away_record: { wins: number; losses: number };
  conference_record: { wins: number; losses: number };
  division_record: { wins: number; losses: number };
  vs_above_500: { wins: number; losses: number };
  vs_below_500: { wins: number; losses: number };
  in_clutch_games: TeamClutchStats;
  streak: {
    type: 'W' | 'L';
    count: number;
    games: Array<{
      date: string;
      opponent: string;
      result: 'W' | 'L';
      score: string;
    }>;
  };
}

export interface PlayoffProjection {
  playoff_probability: number;
  championship_probability: number;
  conference_finals_probability: number;
  division_title_probability: number;
  projected_wins: number;
  projected_seed: number;
  strength_of_schedule_remaining: number;
  key_factors: string[];
  simulation_results: {
    playoff_appearances: number;
    championship_wins: number;
    total_simulations: number;
  };
}
