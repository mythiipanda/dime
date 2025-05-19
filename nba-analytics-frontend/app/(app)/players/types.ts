// --- Interfaces based on PlayerProfileV2 structure ---
export interface PlayerInfo {
  PERSON_ID: number;
  DISPLAY_FIRST_LAST: string;
  TEAM_ABBREVIATION?: string;
  TEAM_CITY?: string;
  POSITION?: string;
  HEIGHT?: string;
  WEIGHT?: string;
  JERSEY?: string;
  FROM_YEAR?: number;
  TO_YEAR?: number;
  PLAYER_SLUG?: string;
  COUNTRY?: string;
  SCHOOL?: string;
  BIRTHDATE?: string;
  SEASON_EXP?: number;
}

export interface CareerOrSeasonStat {
  PLAYER_ID: number;
  SEASON_ID?: string; // Only for season stats
  LEAGUE_ID?: string; // Optional
  TEAM_ID?: number; // Optional
  TEAM_ABBREVIATION?: string;
  PLAYER_AGE?: number;
  GP?: number;
  GS?: number;
  MIN?: number;
  FGM?: number;
  FGA?: number;
  FG_PCT?: number;
  FG3M?: number;
  FG3A?: number;
  FG3_PCT?: number;
  FTM?: number;
  FTA?: number;
  FT_PCT?: number;
  OREB?: number;
  DREB?: number;
  REB?: number;
  AST?: number;
  STL?: number;
  BLK?: number;
  TOV?: number;
  PF?: number;
  PTS?: number;
}

export interface CareerHighs {
    PLAYER_ID?: number;
    PLAYER_NAME?: string;
    TimeFrame?: string;
    PTS_HIGH?: number;
    REB_HIGH?: number;
    AST_HIGH?: number;
    STL_HIGH?: number;
    BLK_HIGH?: number;
}

// Advanced metrics interfaces
export interface AdvancedMetrics {
  // Our RAPTOR-style metrics
  RAPTOR_TOTAL?: number;
  RAPTOR_OFFENSE?: number;
  RAPTOR_DEFENSE?: number;
  WAR?: number; // Wins Above Replacement

  // ELO Rating system
  ELO_RATING?: number;
  ELO_CURRENT?: number;
  ELO_HISTORICAL?: number;

  // NBA API metrics
  ORTG?: number; // Offensive Rating
  DRTG?: number; // Defensive Rating
  NETRTG?: number; // Net Rating
  AST_PCT?: number; // Assist Percentage
  REB_PCT?: number; // Rebound Percentage
  OREB_PCT?: number; // Offensive Rebound Percentage
  DREB_PCT?: number; // Defensive Rebound Percentage
  PIE?: number; // Player Impact Estimate

  // Traditional advanced metrics
  BPM?: number; // Box Plus-Minus
  VORP?: number; // Value Over Replacement Player
  WS?: number; // Win Shares
  PER?: number; // Player Efficiency Rating
  TS_PCT?: number; // True Shooting Percentage
  USG_PCT?: number; // Usage Percentage

  // Legacy metrics (keeping for backward compatibility)
  NBA_PLUS?: number;
  NBA_PLUS_OFF?: number;
  NBA_PLUS_DEF?: number;
  PLAYER_VALUE?: number;
  EPM?: number;
  EPM_OFF?: number;
  EPM_DEF?: number;
  RAPTOR?: number;
  RAPTOR_OFF?: number;
  RAPTOR_DEF?: number;
  DARKO_DPM?: number;
  DARKO_ODPM?: number;
  DARKO_DDPM?: number;
  LEBRON?: number;
  LEBRON_OFF?: number;
  LEBRON_DEF?: number;
}

export interface SkillGrades {
  perimeter_shooting?: string; // A+, A, A-, B+, B, B-, C+, C, C-, D+, D, D-, F
  interior_scoring?: string;
  playmaking?: string;
  perimeter_defense?: string;
  interior_defense?: string;
  rebounding?: string;
  off_ball_movement?: string;
  hustle?: string;
  versatility?: string;
}

export interface PlayerData {
  player_id: number;  // Added player_id at the top level
  player_name: string; // Added player_name at the top level
  player_info: PlayerInfo | null;
  career_totals_regular_season: CareerOrSeasonStat | null;
  season_totals_regular_season: CareerOrSeasonStat[] | null;
  career_totals_post_season: CareerOrSeasonStat | null;
  season_totals_post_season: CareerOrSeasonStat[] | null;
  career_highs: CareerHighs | null;
  advanced_metrics?: AdvancedMetrics | null;
  skill_grades?: SkillGrades | null;
  similar_players?: {player_id: number, player_name: string, similarity_score: number}[] | null;
}

export interface Suggestion {
    id: number;
    full_name: string;
    is_active: boolean;
}