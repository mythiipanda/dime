// Interfaces related to the Games/Scoreboard Page

export interface Team {
  teamId: number;
  teamTricode: string;
  score: number;
  wins?: number;
  losses?: number;
}

export interface Game {
  gameId: string;
  gameStatus: number;
  gameStatusText: string;
  period?: number;
  gameClock?: string;
  homeTeam: Team;
  awayTeam: Team;
  gameEt: string;
}

export interface ScoreboardData {
  gameDate: string;
  games: Game[];
}

// Interface for Play-by-Play data
export interface Play {
  event_num: number;
  clock: string;
  score?: string | null;
  margin?: string | null;
  team: "home" | "away" | "neutral";
  home_description?: string | null;
  away_description?: string | null;
  neutral_description?: string | null;
  description?: string | null;
  event_type: string;
}

export interface PbpPeriod {
  period: number;
  plays: Play[];
}

export interface PbpData {
  game_id: string;
  has_video: boolean;
  filtered_periods?: { start: number; end: number } | null;
  periods: PbpPeriod[];
  source: 'live' | 'historical';
} 