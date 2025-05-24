/**
 * Teams Data Service
 * Implements data hierarchy: League → Team → Player
 * Follows clean architecture and SRP principles
 */

import { 
  getLeagueStandings, 
  getLeagueTeamStats, 
  getAllTeamsEstimatedMetrics,
  getTeamDetails,
  getTeamStats,
  type EnhancedTeam,
  type TeamStanding,
  TEAM_COLORS 
} from '@/lib/api/teams';
import { 
  getComprehensiveLeagueData,
  getEnhancedTeamsWithComprehensiveAnalytics,
  type EnhancedTeamWithAnalytics 
} from '@/lib/api/comprehensive-analytics';

/**
 * Service for managing teams data with proper hierarchy
 * Implements rate limit avoidance through data hierarchy
 */
export class TeamsDataService {
  private static instance: TeamsDataService;
  private leagueDataCache: Map<string, any> = new Map();
  private teamDataCache: Map<string, any> = new Map();

  private constructor() {}

  static getInstance(): TeamsDataService {
    if (!TeamsDataService.instance) {
      TeamsDataService.instance = new TeamsDataService();
    }
    return TeamsDataService.instance;
  }

  /**
   * Level 1: League-wide data (most efficient, least API calls)
   */
  async getLeagueData(season: string) {
    const cacheKey = `league-${season}`;
    if (this.leagueDataCache.has(cacheKey)) {
      return this.leagueDataCache.get(cacheKey);
    }

    try {
      const [standings, teamStats, estimatedMetrics] = await Promise.all([
        getLeagueStandings(season),
        getLeagueTeamStats(season),
        getAllTeamsEstimatedMetrics(season).catch(() => null) // Fallback if not available
      ]);

      const leagueData = {
        standings: standings.standings,
        teamStats,
        estimatedMetrics,
        timestamp: Date.now()
      };

      this.leagueDataCache.set(cacheKey, leagueData);
      return leagueData;
    } catch (error) {
      console.error('Error fetching league data:', error);
      throw error;
    }
  }

  /**
   * Level 2: Team-specific data (fallback when league data insufficient)
   */
  async getTeamSpecificData(teamId: string, season: string) {
    const cacheKey = `team-${teamId}-${season}`;
    if (this.teamDataCache.has(cacheKey)) {
      return this.teamDataCache.get(cacheKey);
    }

    try {
      const [details, stats] = await Promise.all([
        getTeamDetails(teamId, season),
        getTeamStats(teamId, season)
      ]);

      const teamData = {
        details,
        stats,
        timestamp: Date.now()
      };

      this.teamDataCache.set(cacheKey, teamData);
      return teamData;
    } catch (error) {
      console.error(`Error fetching team data for ${teamId}:`, error);
      throw error;
    }
  }

  /**
   * Enhanced teams with comprehensive analytics
   * Uses league data first, falls back to team-specific data
   */
  async getEnhancedTeams(season: string): Promise<EnhancedTeam[]> {
    try {
      // Try comprehensive analytics first (most efficient)
      const comprehensiveTeams = await getEnhancedTeamsWithComprehensiveAnalytics(season);
      return this.transformToEnhancedTeams(comprehensiveTeams);
    } catch (error) {
      console.warn('Comprehensive analytics failed, falling back to league data:', error);
      
      // Fallback to league-level data
      const leagueData = await this.getLeagueData(season);
      return this.buildEnhancedTeamsFromLeague(leagueData, season);
    }
  }

  /**
   * Enhanced teams with full statistics
   * Implements the data hierarchy approach
   */
  async getEnhancedTeamsWithStats(season: string): Promise<EnhancedTeam[]> {
    try {
      // Level 1: Try league-wide data first
      const leagueData = await this.getLeagueData(season);
      const enhancedTeams = this.buildEnhancedTeamsFromLeague(leagueData, season);
      
      // If we have sufficient data, return it
      if (enhancedTeams.length > 0) {
        return enhancedTeams;
      }
    } catch (error) {
      console.warn('League data fetch failed, trying team-specific approach:', error);
    }

    // Level 2: Fallback to team-specific data (more API calls but more reliable)
    return this.getEnhancedTeamsTeamByTeam(season);
  }

  /**
   * Build enhanced teams from league data
   */
  private buildEnhancedTeamsFromLeague(leagueData: any, season: string): EnhancedTeam[] {
    const { standings, teamStats } = leagueData;
    
    return standings.map((standing: TeamStanding) => {
      const teamStat = teamStats?.data_sets?.LeagueDashTeamStats?.find(
        (stat: any) => stat.TEAM_ID === standing.TeamID
      );

      const teamColors = TEAM_COLORS[standing.TeamID] || {
        primary: '#000000',
        secondary: '#FFFFFF'
      };

      return {
        id: standing.TeamID.toString(),
        name: standing.TeamName,
        abbreviation: this.extractAbbreviation(standing.TeamName),
        conference: standing.Conference as 'East' | 'West',
        division: standing.Division,
        logo: `https://cdn.nba.com/logos/nba/${standing.TeamID}/primary/L/logo.svg`,
        primaryColor: teamColors.primary,
        secondaryColor: teamColors.secondary,
        record: {
          wins: standing.WINS,
          losses: standing.LOSSES
        },
        streak: this.parseStreak(standing.STRK),
        lastGame: {
          opponent: 'TBD',
          result: 'W' as 'W' | 'L',
          score: '0-0'
        },
        nextGame: {
          opponent: 'TBD',
          date: new Date().toISOString().split('T')[0],
          home: true
        },
        offensiveRating: teamStat?.OFF_RATING || 0,
        defensiveRating: teamStat?.DEF_RATING || 0,
        pace: teamStat?.PACE || 0,
        playoffOdds: this.calculatePlayoffOdds(standing.WinPct),
        keyPlayers: [],
        injuries: [],
        recentTrades: [],
        capSpace: 0,
        status: this.determineTeamStatus(standing.WinPct)
      };
    });
  }

  /**
   * Team-by-team approach (Level 3: Player-specific would be here)
   */
  private async getEnhancedTeamsTeamByTeam(season: string): Promise<EnhancedTeam[]> {
    // This would be implemented if league-level data is insufficient
    // For now, return empty array to avoid excessive API calls
    console.warn('Team-by-team approach not implemented to avoid rate limits');
    return [];
  }

  /**
   * Transform comprehensive analytics to enhanced teams
   */
  private transformToEnhancedTeams(teams: EnhancedTeamWithAnalytics[]): EnhancedTeam[] {
    return teams.map(team => ({
      id: team.id,
      name: team.name,
      abbreviation: team.abbreviation,
      conference: team.conference as 'East' | 'West',
      division: team.division,
      logo: team.logo,
      primaryColor: team.primaryColor,
      secondaryColor: team.secondaryColor,
      record: team.record,
      streak: { type: 'W', count: 1 }, // Default, would parse from recentForm
      lastGame: { opponent: 'TBD', result: 'W', score: '0-0' },
      nextGame: { opponent: 'TBD', date: new Date().toISOString().split('T')[0], home: true },
      offensiveRating: team.offensiveRating,
      defensiveRating: team.defensiveRating,
      pace: team.pace,
      playoffOdds: team.playoffOdds || 0,
      keyPlayers: team.topPlayers.map(p => p.name),
      injuries: team.injuries,
      recentTrades: [],
      capSpace: 0,
      status: team.status as 'contender' | 'playoff-push' | 'rebuilding'
    }));
  }

  // Utility methods
  private extractAbbreviation(teamName: string): string {
    const abbreviations: Record<string, string> = {
      'Atlanta Hawks': 'ATL',
      'Boston Celtics': 'BOS',
      'Brooklyn Nets': 'BKN',
      'Charlotte Hornets': 'CHA',
      'Chicago Bulls': 'CHI',
      'Cleveland Cavaliers': 'CLE',
      'Dallas Mavericks': 'DAL',
      'Denver Nuggets': 'DEN',
      'Detroit Pistons': 'DET',
      'Golden State Warriors': 'GSW',
      'Houston Rockets': 'HOU',
      'Indiana Pacers': 'IND',
      'LA Clippers': 'LAC',
      'Los Angeles Lakers': 'LAL',
      'Memphis Grizzlies': 'MEM',
      'Miami Heat': 'MIA',
      'Milwaukee Bucks': 'MIL',
      'Minnesota Timberwolves': 'MIN',
      'New Orleans Pelicans': 'NOP',
      'New York Knicks': 'NYK',
      'Oklahoma City Thunder': 'OKC',
      'Orlando Magic': 'ORL',
      'Philadelphia 76ers': 'PHI',
      'Phoenix Suns': 'PHX',
      'Portland Trail Blazers': 'POR',
      'Sacramento Kings': 'SAC',
      'San Antonio Spurs': 'SAS',
      'Toronto Raptors': 'TOR',
      'Utah Jazz': 'UTA',
      'Washington Wizards': 'WAS'
    };
    return abbreviations[teamName] || teamName.substring(0, 3).toUpperCase();
  }

  private parseStreak(streak: string): { type: 'W' | 'L'; count: number } {
    const match = streak.match(/([WL])(\d+)/);
    if (match) {
      return {
        type: match[1] as 'W' | 'L',
        count: parseInt(match[2])
      };
    }
    return { type: 'W', count: 1 };
  }

  private calculatePlayoffOdds(winPct: number): number {
    // Simple calculation based on win percentage
    if (winPct >= 0.6) return Math.min(95, winPct * 100 + 20);
    if (winPct >= 0.5) return Math.min(80, winPct * 100 + 10);
    if (winPct >= 0.4) return Math.min(50, winPct * 100);
    return Math.max(5, winPct * 50);
  }

  private determineTeamStatus(winPct: number): 'contender' | 'playoff-push' | 'rebuilding' {
    if (winPct >= 0.6) return 'contender';
    if (winPct >= 0.45) return 'playoff-push';
    return 'rebuilding';
  }

  /**
   * Clear cache (useful for testing or forced refresh)
   */
  clearCache(): void {
    this.leagueDataCache.clear();
    this.teamDataCache.clear();
  }
}

// Export singleton instance
export const teamsDataService = TeamsDataService.getInstance();
