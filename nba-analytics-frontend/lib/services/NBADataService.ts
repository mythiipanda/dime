/**
 * Comprehensive NBA Data Service
 * Provides a unified interface for fetching NBA data with advanced metrics
 * Follows the hierarchy: League → Teams → Players to minimize API calls
 */

import { fetchFromAPI } from '@/lib/api/fetch';

// ============================================================================
// TYPES & INTERFACES
// ============================================================================

export interface TeamStanding {
  TeamID: number;
  TeamName: string;
  Conference: string;
  Division: string;
  WINS: number;
  LOSSES: number;
  WinPct: number;
  PlayoffRank: number;
  GB: number;
  L10: string;
  STRK: string;
  HOME: string;
  ROAD: string;
  ConferenceRecord: string;
  DivisionRecord: string;
}

export interface AdvancedTeamStats {
  TEAM_ID: number;
  TEAM_NAME: string;
  GP: number;
  W: number;
  L: number;
  W_PCT: number;
  MIN: number;
  OFF_RATING: number;
  DEF_RATING: number;
  NET_RATING: number;
  AST_PCT: number;
  AST_TO: number;
  AST_RATIO: number;
  OREB_PCT: number;
  DREB_PCT: number;
  REB_PCT: number;
  TM_TOV_PCT: number;
  EFG_PCT: number;
  TS_PCT: number;
  PACE: number;
  PIE: number;
}

export interface PlayerStats {
  PLAYER_ID: number;
  PLAYER_NAME: string;
  TEAM_ID: number;
  TEAM_ABBREVIATION: string;
  AGE: number;
  GP: number;
  W: number;
  L: number;
  W_PCT: number;
  MIN: number;
  PTS: number;
  REB: number;
  AST: number;
  FG_PCT: number;
  FG3_PCT: number;
  FT_PCT: number;
  STL: number;
  BLK: number;
  TOV: number;
  PF: number;
  EFF: number;
  AST_TOV: number;
  STL_TOV: number;
}

export interface EnhancedTeam {
  id: string;
  name: string;
  abbreviation: string;
  conference: 'East' | 'West';
  division: string;
  logo: string;
  primaryColor: string;
  secondaryColor: string;

  // Basic Stats
  record: {
    wins: number;
    losses: number;
    winPct: number;
  };

  // Advanced Metrics
  offensiveRating: number;
  defensiveRating: number;
  netRating: number;
  pace: number;
  trueShootingPct: number;
  effectiveFgPct: number;
  turnoverRate: number;
  reboundRate: number;

  // Contextual Data
  streak: {
    type: 'W' | 'L';
    count: number;
  };
  playoffOdds: number;
  strengthOfSchedule: number;

  // Rankings
  rankings: {
    overall: number;
    conference: number;
    division: number;
    offense: number;
    defense: number;
  };
}

export interface EnhancedPlayer {
  id: string;
  name: string;
  teamId: string;
  teamAbbreviation: string;
  position: string;
  age: number;

  // Basic Stats
  stats: {
    gamesPlayed: number;
    minutes: number;
    points: number;
    rebounds: number;
    assists: number;
    steals: number;
    blocks: number;
    turnovers: number;
  };

  // Shooting
  shooting: {
    fgPct: number;
    fg3Pct: number;
    ftPct: number;
    trueShootingPct: number;
    effectiveFgPct: number;
  };

  // Advanced Metrics
  advanced: {
    per: number;
    bpm: number;
    vorp: number;
    winShares: number;
    usageRate: number;
    assistTurnoverRatio: number;
  };

  // Grades (A+ to F)
  grades: {
    overall: string;
    offense: string;
    defense: string;
    shooting: string;
    playmaking: string;
    rebounding: string;
  };
}

// ============================================================================
// TEAM COLORS & BRANDING
// ============================================================================

export const TEAM_COLORS: Record<string, {
  primary: string;
  secondary: string;
  logo: string;
  abbreviation: string;
  name: string;
  city: string;
}> = {
  '1610612737': { // Atlanta Hawks
    primary: '#E03A3E',
    secondary: '#C1D32F',
    logo: 'https://cdn.nba.com/logos/nba/1610612737/primary/L/logo.svg',
    abbreviation: 'ATL',
    name: 'Atlanta Hawks',
    city: 'Atlanta'
  },
  '1610612738': { // Boston Celtics
    primary: '#007A33',
    secondary: '#BA9653',
    logo: 'https://cdn.nba.com/logos/nba/1610612738/primary/L/logo.svg',
    abbreviation: 'BOS',
    name: 'Boston Celtics',
    city: 'Boston'
  },
  '1610612751': { // Brooklyn Nets
    primary: '#000000',
    secondary: '#FFFFFF',
    logo: 'https://cdn.nba.com/logos/nba/1610612751/primary/L/logo.svg',
    abbreviation: 'BKN',
    name: 'Brooklyn Nets',
    city: 'Brooklyn'
  },
  '1610612766': { // Charlotte Hornets
    primary: '#1D1160',
    secondary: '#00788C',
    logo: 'https://cdn.nba.com/logos/nba/1610612766/primary/L/logo.svg',
    abbreviation: 'CHA',
    name: 'Charlotte Hornets',
    city: 'Charlotte'
  },
  '1610612741': { // Chicago Bulls
    primary: '#CE1141',
    secondary: '#000000',
    logo: 'https://cdn.nba.com/logos/nba/1610612741/primary/L/logo.svg',
    abbreviation: 'CHI',
    name: 'Chicago Bulls',
    city: 'Chicago'
  },
  '1610612739': { // Cleveland Cavaliers
    primary: '#860038',
    secondary: '#FDBB30',
    logo: 'https://cdn.nba.com/logos/nba/1610612739/primary/L/logo.svg',
    abbreviation: 'CLE',
    name: 'Cleveland Cavaliers',
    city: 'Cleveland'
  },
  '1610612742': { // Dallas Mavericks
    primary: '#00538C',
    secondary: '#002B5E',
    logo: 'https://cdn.nba.com/logos/nba/1610612742/primary/L/logo.svg',
    abbreviation: 'DAL',
    name: 'Dallas Mavericks',
    city: 'Dallas'
  },
  '1610612743': { // Denver Nuggets
    primary: '#0E2240',
    secondary: '#FEC524',
    logo: 'https://cdn.nba.com/logos/nba/1610612743/primary/L/logo.svg',
    abbreviation: 'DEN',
    name: 'Denver Nuggets',
    city: 'Denver'
  },
  '1610612765': { // Detroit Pistons
    primary: '#C8102E',
    secondary: '#1D42BA',
    logo: 'https://cdn.nba.com/logos/nba/1610612765/primary/L/logo.svg',
    abbreviation: 'DET',
    name: 'Detroit Pistons',
    city: 'Detroit'
  },
  '1610612744': { // Golden State Warriors
    primary: '#1D428A',
    secondary: '#FFC72C',
    logo: 'https://cdn.nba.com/logos/nba/1610612744/primary/L/logo.svg',
    abbreviation: 'GSW',
    name: 'Golden State Warriors',
    city: 'Golden State'
  },
  '1610612745': { // Houston Rockets
    primary: '#CE1141',
    secondary: '#000000',
    logo: 'https://cdn.nba.com/logos/nba/1610612745/primary/L/logo.svg',
    abbreviation: 'HOU',
    name: 'Houston Rockets',
    city: 'Houston'
  },
  '1610612754': { // Indiana Pacers
    primary: '#002D62',
    secondary: '#FDBB30',
    logo: 'https://cdn.nba.com/logos/nba/1610612754/primary/L/logo.svg',
    abbreviation: 'IND',
    name: 'Indiana Pacers',
    city: 'Indiana'
  },
  '1610612746': { // LA Clippers
    primary: '#C8102E',
    secondary: '#1D428A',
    logo: 'https://cdn.nba.com/logos/nba/1610612746/primary/L/logo.svg',
    abbreviation: 'LAC',
    name: 'LA Clippers',
    city: 'Los Angeles'
  },
  '1610612747': { // Los Angeles Lakers
    primary: '#552583',
    secondary: '#FDB927',
    logo: 'https://cdn.nba.com/logos/nba/1610612747/primary/L/logo.svg',
    abbreviation: 'LAL',
    name: 'Los Angeles Lakers',
    city: 'Los Angeles'
  },
  '1610612763': { // Memphis Grizzlies
    primary: '#5D76A9',
    secondary: '#12173F',
    logo: 'https://cdn.nba.com/logos/nba/1610612763/primary/L/logo.svg',
    abbreviation: 'MEM',
    name: 'Memphis Grizzlies',
    city: 'Memphis'
  },
  '1610612748': { // Miami Heat
    primary: '#98002E',
    secondary: '#F9A01B',
    logo: 'https://cdn.nba.com/logos/nba/1610612748/primary/L/logo.svg',
    abbreviation: 'MIA',
    name: 'Miami Heat',
    city: 'Miami'
  },
  '1610612749': { // Milwaukee Bucks
    primary: '#00471B',
    secondary: '#EEE1C6',
    logo: 'https://cdn.nba.com/logos/nba/1610612749/primary/L/logo.svg',
    abbreviation: 'MIL',
    name: 'Milwaukee Bucks',
    city: 'Milwaukee'
  },
  '1610612750': { // Minnesota Timberwolves
    primary: '#0C2340',
    secondary: '#236192',
    logo: 'https://cdn.nba.com/logos/nba/1610612750/primary/L/logo.svg',
    abbreviation: 'MIN',
    name: 'Minnesota Timberwolves',
    city: 'Minnesota'
  },
  '1610612740': { // New Orleans Pelicans
    primary: '#0C2340',
    secondary: '#C8102E',
    logo: 'https://cdn.nba.com/logos/nba/1610612740/primary/L/logo.svg',
    abbreviation: 'NOP',
    name: 'New Orleans Pelicans',
    city: 'New Orleans'
  },
  '1610612752': { // New York Knicks
    primary: '#006BB6',
    secondary: '#F58426',
    logo: 'https://cdn.nba.com/logos/nba/1610612752/primary/L/logo.svg',
    abbreviation: 'NYK',
    name: 'New York Knicks',
    city: 'New York'
  },
  '1610612760': { // Oklahoma City Thunder
    primary: '#007AC1',
    secondary: '#EF3B24',
    logo: 'https://cdn.nba.com/logos/nba/1610612760/primary/L/logo.svg',
    abbreviation: 'OKC',
    name: 'Oklahoma City Thunder',
    city: 'Oklahoma City'
  },
  '1610612753': { // Orlando Magic
    primary: '#0077C0',
    secondary: '#C4CED4',
    logo: 'https://cdn.nba.com/logos/nba/1610612753/primary/L/logo.svg',
    abbreviation: 'ORL',
    name: 'Orlando Magic',
    city: 'Orlando'
  },
  '1610612755': { // Philadelphia 76ers
    primary: '#006BB6',
    secondary: '#ED174C',
    logo: 'https://cdn.nba.com/logos/nba/1610612755/primary/L/logo.svg',
    abbreviation: 'PHI',
    name: 'Philadelphia 76ers',
    city: 'Philadelphia'
  },
  '1610612756': { // Phoenix Suns
    primary: '#1D1160',
    secondary: '#E56020',
    logo: 'https://cdn.nba.com/logos/nba/1610612756/primary/L/logo.svg',
    abbreviation: 'PHX',
    name: 'Phoenix Suns',
    city: 'Phoenix'
  },
  '1610612757': { // Portland Trail Blazers
    primary: '#E03A3E',
    secondary: '#000000',
    logo: 'https://cdn.nba.com/logos/nba/1610612757/primary/L/logo.svg',
    abbreviation: 'POR',
    name: 'Portland Trail Blazers',
    city: 'Portland'
  },
  '1610612758': { // Sacramento Kings
    primary: '#5A2D81',
    secondary: '#63727A',
    logo: 'https://cdn.nba.com/logos/nba/1610612758/primary/L/logo.svg',
    abbreviation: 'SAC',
    name: 'Sacramento Kings',
    city: 'Sacramento'
  },
  '1610612759': { // San Antonio Spurs
    primary: '#C4CED4',
    secondary: '#000000',
    logo: 'https://cdn.nba.com/logos/nba/1610612759/primary/L/logo.svg',
    abbreviation: 'SAS',
    name: 'San Antonio Spurs',
    city: 'San Antonio'
  },
  '1610612761': { // Toronto Raptors
    primary: '#CE1141',
    secondary: '#000000',
    logo: 'https://cdn.nba.com/logos/nba/1610612761/primary/L/logo.svg',
    abbreviation: 'TOR',
    name: 'Toronto Raptors',
    city: 'Toronto'
  },
  '1610612762': { // Utah Jazz
    primary: '#002B5C',
    secondary: '#00471B',
    logo: 'https://cdn.nba.com/logos/nba/1610612762/primary/L/logo.svg',
    abbreviation: 'UTA',
    name: 'Utah Jazz',
    city: 'Utah'
  },
  '1610612764': { // Washington Wizards
    primary: '#002B5C',
    secondary: '#E31837',
    logo: 'https://cdn.nba.com/logos/nba/1610612764/primary/L/logo.svg',
    abbreviation: 'WAS',
    name: 'Washington Wizards',
    city: 'Washington'
  }
};

// ============================================================================
// CORE DATA SERVICE CLASS
// ============================================================================

export class NBADataService {
  private static instance: NBADataService;
  private cache: Map<string, { data: any; timestamp: number; ttl: number }> = new Map();

  private constructor() {}

  public static getInstance(): NBADataService {
    if (!NBADataService.instance) {
      NBADataService.instance = new NBADataService();
    }
    return NBADataService.instance;
  }

  // ============================================================================
  // CACHE MANAGEMENT
  // ============================================================================

  private getCacheKey(endpoint: string, params: Record<string, any> = {}): string {
    const sortedParams = Object.keys(params)
      .sort()
      .map(key => `${key}=${params[key]}`)
      .join('&');
    return `${endpoint}?${sortedParams}`;
  }

  private isValidCache(cacheEntry: { timestamp: number; ttl: number }): boolean {
    return Date.now() - cacheEntry.timestamp < cacheEntry.ttl;
  }

  private setCache(key: string, data: any, ttlMinutes: number = 5): void {
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl: ttlMinutes * 60 * 1000
    });
  }

  private getCache(key: string): any | null {
    const entry = this.cache.get(key);
    if (entry && this.isValidCache(entry)) {
      return entry.data;
    }
    if (entry) {
      this.cache.delete(key);
    }
    return null;
  }

  // ============================================================================
  // TEAM INFO UTILITIES
  // ============================================================================

  /**
   * Get team information by team ID
   */
  getTeamInfo(teamId: string) {
    return TEAM_COLORS[teamId] || null;
  }

  // ============================================================================
  // LEAGUE-WIDE DATA FETCHING
  // ============================================================================

  /**
   * Fetch league standings - the foundation for all team data
   */
  async getLeagueStandings(season: string = '2024-25'): Promise<TeamStanding[]> {
    const cacheKey = this.getCacheKey('/league/standings', { season });
    const cached = this.getCache(cacheKey);
    if (cached) return cached;

    try {
      const response = await fetchFromAPI<{ standings: TeamStanding[] }>(`/league/standings?season=${season}`);
      const standings = response.standings || [];
      this.setCache(cacheKey, standings, 10); // Cache for 10 minutes
      return standings;
    } catch (error) {
      console.error('Error fetching league standings:', error);
      throw error;
    }
  }

  /**
   * Fetch advanced team statistics for all teams
   */
  async getLeagueTeamStats(season: string = '2024-25', measureType: string = 'Advanced'): Promise<AdvancedTeamStats[]> {
    const cacheKey = this.getCacheKey('/league/team-stats', { season, measureType });
    const cached = this.getCache(cacheKey);
    if (cached) return cached;

    try {
      const response = await fetchFromAPI<{ data_sets: { LeagueDashTeamStats: AdvancedTeamStats[] } }>(
        `/league/team-stats?season=${season}&measure_type=${measureType}&per_mode=PerGame`
      );
      const teamStats = response.data_sets?.LeagueDashTeamStats || [];
      this.setCache(cacheKey, teamStats, 15); // Cache for 15 minutes
      return teamStats;
    } catch (error) {
      console.error('Error fetching league team stats:', error);
      throw error;
    }
  }

  /**
   * Fetch league-wide player statistics
   */
  async getLeaguePlayerStats(season: string = '2024-25', measureType: string = 'Base'): Promise<PlayerStats[]> {
    const cacheKey = this.getCacheKey('/league/player-stats', { season, measureType });
    const cached = this.getCache(cacheKey);
    if (cached) return cached;

    try {
      const response = await fetchFromAPI<{ data_sets: { LeagueDashPlayerStats: PlayerStats[] } }>(
        `/league/player-stats?season=${season}&measure_type=${measureType}&per_mode=PerGame`
      );
      const playerStats = response.data_sets?.LeagueDashPlayerStats || [];
      this.setCache(cacheKey, playerStats, 15); // Cache for 15 minutes
      return playerStats;
    } catch (error) {
      console.error('Error fetching league player stats:', error);
      // Return empty array instead of throwing to prevent UI crashes
      return [];
    }
  }

  /**
   * Fetch scoreboard data for a specific date
   */
  async getScoreboard(gameDate: string): Promise<any[]> {
    const cacheKey = this.getCacheKey('/scoreboard', { gameDate });
    const cached = this.getCache(cacheKey);
    if (cached) return cached;

    try {
      const response = await fetchFromAPI<{ scoreboard: any[] }>(`/scoreboard?game_date=${gameDate}`);
      const scoreboard = response.scoreboard || [];
      this.setCache(cacheKey, scoreboard, 5); // Cache for 5 minutes (live data)
      return scoreboard;
    } catch (error) {
      console.error('Error fetching scoreboard:', error);
      return [];
    }
  }

  // ============================================================================
  // ADVANCED METRICS CALCULATIONS
  // ============================================================================

  /**
   * Calculate advanced team metrics and rankings
   */
  private calculateTeamAdvancedMetrics(
    standings: TeamStanding[],
    teamStats: AdvancedTeamStats[]
  ): EnhancedTeam[] {
    // Create lookup maps
    const statsMap = new Map<number, AdvancedTeamStats>();
    teamStats.forEach(stat => statsMap.set(stat.TEAM_ID, stat));

    // Calculate league averages for context
    const leagueAvg = {
      offRating: teamStats.reduce((sum, t) => sum + t.OFF_RATING, 0) / teamStats.length,
      defRating: teamStats.reduce((sum, t) => sum + t.DEF_RATING, 0) / teamStats.length,
      pace: teamStats.reduce((sum, t) => sum + t.PACE, 0) / teamStats.length,
      tsPercent: teamStats.reduce((sum, t) => sum + t.TS_PCT, 0) / teamStats.length,
    };

    return standings.map((standing, index) => {
      const teamId = standing.TeamID.toString();
      const teamColors = TEAM_COLORS[teamId] || {
        primary: '#000000',
        secondary: '#FFFFFF',
        logo: `https://cdn.nba.com/logos/nba/${teamId}/primary/L/logo.svg`,
        abbreviation: standing.TeamName.split(' ').pop()?.substring(0, 3).toUpperCase() || 'TM',
        name: standing.TeamName,
        city: standing.TeamName.split(' ')[0]
      };

      const stats = statsMap.get(standing.TeamID);

      // Calculate advanced metrics with fallbacks
      const offensiveRating = stats?.OFF_RATING || this.estimateOffensiveRating(standing.WinPct, leagueAvg.offRating);
      const defensiveRating = stats?.DEF_RATING || this.estimateDefensiveRating(standing.WinPct, leagueAvg.defRating);
      const netRating = offensiveRating - defensiveRating;
      const pace = stats?.PACE || leagueAvg.pace;
      const trueShootingPct = stats?.TS_PCT || leagueAvg.tsPercent;
      const effectiveFgPct = stats?.EFG_PCT || 0.5;
      const turnoverRate = stats?.TM_TOV_PCT || 0.14;
      const reboundRate = stats?.REB_PCT || 0.5;

      // Calculate playoff odds based on current standing and performance
      const playoffOdds = this.calculatePlayoffOdds(standing.WinPct, standing.Conference, standing.PlayoffRank);

      // Parse streak with improved error handling
      let streakType: 'W' | 'L' = 'W';
      let streakCount = 1;

      if (standing.STRK) {
        // Debug: Log the actual streak format
        console.log(`Team ${standing.TeamName} streak data:`, standing.STRK);
        // Try multiple patterns to handle different streak formats
        const patterns = [
          /([WL])(\d+)/,           // W5, L3
          /(\d+)([WL])/,           // 5W, 3L
          /([WL])-(\d+)/,          // W-5, L-3
          /(\d+)-([WL])/           // 5-W, 3-L
        ];

        for (const pattern of patterns) {
          const match = standing.STRK.match(pattern);
          if (match) {
            if (pattern.source.includes('([WL])(\\d+)') || pattern.source.includes('([WL])-(\\d+)')) {
              streakType = match[1] as 'W' | 'L';
              streakCount = parseInt(match[2]) || 1;
            } else {
              streakCount = parseInt(match[1]) || 1;
              streakType = match[2] as 'W' | 'L';
            }
            break;
          }
        }

        // Fallback: if no pattern matches, try to extract W/L and number separately
        if (!patterns.some(p => standing.STRK.match(p))) {
          const hasW = standing.STRK.includes('W');
          const hasL = standing.STRK.includes('L');
          const numbers = standing.STRK.match(/\d+/);

          if (hasW || hasL) {
            streakType = hasW ? 'W' : 'L';
            streakCount = numbers ? parseInt(numbers[0]) : 1;
          }
        }
      }

      // Calculate rankings
      const conferenceTeams = standings.filter(s => s.Conference === standing.Conference);
      const conferenceRank = conferenceTeams.findIndex(s => s.TeamID === standing.TeamID) + 1;

      const divisionTeams = standings.filter(s => s.Division === standing.Division);
      const divisionRank = divisionTeams.findIndex(s => s.TeamID === standing.TeamID) + 1;

      return {
        id: teamId,
        name: standing.TeamName,
        abbreviation: teamColors.abbreviation,
        conference: standing.Conference as 'East' | 'West',
        division: standing.Division,
        logo: teamColors.logo,
        primaryColor: teamColors.primary,
        secondaryColor: teamColors.secondary,

        record: {
          wins: standing.WINS,
          losses: standing.LOSSES,
          winPct: standing.WinPct
        },

        offensiveRating: Math.round(offensiveRating * 10) / 10,
        defensiveRating: Math.round(defensiveRating * 10) / 10,
        netRating: Math.round(netRating * 10) / 10,
        pace: Math.round(pace * 10) / 10,
        trueShootingPct: Math.round(trueShootingPct * 1000) / 10, // Convert to percentage
        effectiveFgPct: Math.round(effectiveFgPct * 1000) / 10,
        turnoverRate: Math.round(turnoverRate * 1000) / 10,
        reboundRate: Math.round(reboundRate * 1000) / 10,

        streak: {
          type: streakType,
          count: streakCount
        },
        playoffOdds: Math.round(playoffOdds),
        strengthOfSchedule: 0, // TODO: Calculate based on opponent strength

        rankings: {
          overall: index + 1,
          conference: conferenceRank,
          division: divisionRank,
          offense: this.calculateOffenseRank(offensiveRating, teamStats),
          defense: this.calculateDefenseRank(defensiveRating, teamStats)
        }
      };
    });
  }

  /**
   * Estimate offensive rating based on win percentage when actual data unavailable
   */
  private estimateOffensiveRating(winPct: number, leagueAvg: number): number {
    // Linear relationship: better teams tend to have higher offensive ratings
    const deviation = (winPct - 0.5) * 15; // ±7.5 points from league average
    return leagueAvg + deviation;
  }

  /**
   * Estimate defensive rating based on win percentage when actual data unavailable
   */
  private estimateDefensiveRating(winPct: number, leagueAvg: number): number {
    // Inverse relationship: better teams tend to have lower defensive ratings
    const deviation = (0.5 - winPct) * 15; // ±7.5 points from league average
    return leagueAvg + deviation;
  }

  /**
   * Calculate playoff odds based on current performance and historical data
   */
  private calculatePlayoffOdds(winPct: number, conference: string, rank: number): number {
    // Simplified playoff odds calculation
    // In reality, this would use more sophisticated models

    if (rank <= 6) {
      // Top 6 teams have very high odds
      return Math.min(95, winPct * 100 + 25);
    } else if (rank <= 10) {
      // Play-in tournament range
      return Math.min(80, winPct * 100 + 15);
    } else {
      // Bottom teams
      return Math.max(5, winPct * 100 - 15);
    }
  }

  /**
   * Calculate team's offensive ranking among all teams
   */
  private calculateOffenseRank(offRating: number, allTeamStats: AdvancedTeamStats[]): number {
    const sortedByOffense = allTeamStats
      .map(t => t.OFF_RATING)
      .sort((a, b) => b - a); // Higher is better

    return sortedByOffense.findIndex(rating => rating <= offRating) + 1;
  }

  /**
   * Calculate team's defensive ranking among all teams
   */
  private calculateDefenseRank(defRating: number, allTeamStats: AdvancedTeamStats[]): number {
    const sortedByDefense = allTeamStats
      .map(t => t.DEF_RATING)
      .sort((a, b) => a - b); // Lower is better

    return sortedByDefense.findIndex(rating => rating >= defRating) + 1;
  }

  // ============================================================================
  // PUBLIC API METHODS
  // ============================================================================

  /**
   * Get comprehensive team data with advanced metrics
   * This is the main method for the teams dashboard
   */
  async getEnhancedTeams(season: string = '2024-25'): Promise<EnhancedTeam[]> {
    try {
      // Fetch all required data in parallel for efficiency
      const [standings, teamStats] = await Promise.all([
        this.getLeagueStandings(season),
        this.getLeagueTeamStats(season, 'Advanced')
      ]);

      // Calculate and return enhanced team data
      return this.calculateTeamAdvancedMetrics(standings, teamStats);
    } catch (error) {
      console.error('Error getting enhanced teams:', error);
      throw error;
    }
  }

  /**
   * Get specific team data by ID
   */
  async getTeamById(teamId: string, season: string = '2024-25'): Promise<EnhancedTeam | null> {
    const teams = await this.getEnhancedTeams(season);
    return teams.find(team => team.id === teamId) || null;
  }

  /**
   * Get teams filtered by conference
   */
  async getTeamsByConference(conference: 'East' | 'West', season: string = '2024-25'): Promise<EnhancedTeam[]> {
    const teams = await this.getEnhancedTeams(season);
    return teams.filter(team => team.conference === conference);
  }

  /**
   * Get teams filtered by division
   */
  async getTeamsByDivision(division: string, season: string = '2024-25'): Promise<EnhancedTeam[]> {
    const teams = await this.getEnhancedTeams(season);
    return teams.filter(team => team.division === division);
  }

  /**
   * Get league leaders in various categories
   */
  async getLeagueLeaders(season: string = '2024-25'): Promise<{
    offense: EnhancedTeam[];
    defense: EnhancedTeam[];
    netRating: EnhancedTeam[];
    pace: EnhancedTeam[];
    efficiency: EnhancedTeam[];
  }> {
    const teams = await this.getEnhancedTeams(season);

    return {
      offense: [...teams].sort((a, b) => b.offensiveRating - a.offensiveRating).slice(0, 10),
      defense: [...teams].sort((a, b) => a.defensiveRating - b.defensiveRating).slice(0, 10),
      netRating: [...teams].sort((a, b) => b.netRating - a.netRating).slice(0, 10),
      pace: [...teams].sort((a, b) => b.pace - a.pace).slice(0, 10),
      efficiency: [...teams].sort((a, b) => b.trueShootingPct - a.trueShootingPct).slice(0, 10)
    };
  }

  /**
   * Get playoff picture with current standings and projections
   */
  async getPlayoffPicture(season: string = '2024-25'): Promise<{
    eastern: {
      guaranteed: EnhancedTeam[];
      playIn: EnhancedTeam[];
      bubble: EnhancedTeam[];
      eliminated: EnhancedTeam[];
    };
    western: {
      guaranteed: EnhancedTeam[];
      playIn: EnhancedTeam[];
      bubble: EnhancedTeam[];
      eliminated: EnhancedTeam[];
    };
  }> {
    const teams = await this.getEnhancedTeams(season);

    const categorizeTeams = (conferenceTeams: EnhancedTeam[]) => {
      const sorted = conferenceTeams.sort((a, b) => b.record.winPct - a.record.winPct);

      return {
        guaranteed: sorted.slice(0, 6), // Top 6 avoid play-in
        playIn: sorted.slice(6, 10), // 7-10 seeds in play-in
        bubble: sorted.slice(10, 13), // Teams still with a chance
        eliminated: sorted.slice(13) // Bottom teams
      };
    };

    const easternTeams = teams.filter(t => t.conference === 'East');
    const westernTeams = teams.filter(t => t.conference === 'West');

    return {
      eastern: categorizeTeams(easternTeams),
      western: categorizeTeams(westernTeams)
    };
  }

  /**
   * Search teams by name or abbreviation
   */
  async searchTeams(query: string, season: string = '2024-25'): Promise<EnhancedTeam[]> {
    const teams = await this.getEnhancedTeams(season);
    const lowerQuery = query.toLowerCase();

    return teams.filter(team =>
      team.name.toLowerCase().includes(lowerQuery) ||
      team.abbreviation.toLowerCase().includes(lowerQuery) ||
      TEAM_COLORS[team.id]?.city.toLowerCase().includes(lowerQuery)
    );
  }

  /**
   * Get team comparison data for multiple teams
   */
  async compareTeams(teamIds: string[], season: string = '2024-25'): Promise<{
    teams: EnhancedTeam[];
    comparison: {
      metric: string;
      values: { teamId: string; value: number; rank: number }[];
    }[];
  }> {
    const allTeams = await this.getEnhancedTeams(season);
    const teams = allTeams.filter(team => teamIds.includes(team.id));

    const metrics = [
      'offensiveRating',
      'defensiveRating',
      'netRating',
      'pace',
      'trueShootingPct',
      'effectiveFgPct',
      'turnoverRate',
      'reboundRate'
    ];

    const comparison = metrics.map(metric => {
      const values = teams.map(team => ({
        teamId: team.id,
        value: team[metric as keyof EnhancedTeam] as number,
        rank: allTeams
          .sort((a, b) => {
            const aVal = a[metric as keyof EnhancedTeam] as number;
            const bVal = b[metric as keyof EnhancedTeam] as number;
            return metric === 'defensiveRating' || metric === 'turnoverRate'
              ? aVal - bVal  // Lower is better
              : bVal - aVal; // Higher is better
          })
          .findIndex(t => t.id === team.id) + 1
      }));

      return { metric, values };
    });

    return { teams, comparison };
  }
}

// Export singleton instance
export const nbaDataService = NBADataService.getInstance();
