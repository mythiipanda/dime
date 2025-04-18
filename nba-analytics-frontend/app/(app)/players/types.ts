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

export interface PlayerData {
  player_info: PlayerInfo | null;
  career_totals_regular_season: CareerOrSeasonStat | null;
  season_totals_regular_season: CareerOrSeasonStat[] | null;
  career_totals_post_season: CareerOrSeasonStat | null; 
  season_totals_post_season: CareerOrSeasonStat[] | null;
  career_highs: CareerHighs | null;
}

export interface Suggestion {
    id: number;
    full_name: string;
    is_active: boolean;
} 