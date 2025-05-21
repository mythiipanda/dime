export interface Shot {
  x: number;
  y: number;
  made: boolean;
  value: number;
  shot_type?: string;
  shot_zone?: string;
  distance?: number;
  game_date?: string;
  period?: number;
}

export interface ZoneData {
  zone: string;
  attempts: number;
  made: number;
  percentage: number;
  leaguePercentage: number;
  relativePercentage: number;
} 