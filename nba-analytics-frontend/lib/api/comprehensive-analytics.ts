/**
 * Comprehensive NBA Analytics API Service
 * Provides efficient data loading for advanced analytics similar to dunksandthrees.com, craftednba.com
 */

import { API_BASE_URL } from '@/lib/config';

// Types for comprehensive analytics
export interface LeagueData {
  season: string;
  data_status: {
    status: string;
    players_loaded: number;
    teams_loaded: number;
    league_averages: Record<string, number>;
  };
  league_averages: Record<string, number>;
  players_count: number;
  teams_count: number;
}

export interface PlayerAdvancedMetrics {
  PPM: number; // Points per minute
  RPM: number; // Rebounds per minute
  APM: number; // Assists per minute
  TS_PCT: number; // True Shooting Percentage
  EFG_PCT: number; // Effective Field Goal Percentage
  USG_PCT?: number; // Usage Percentage
  PIE?: number; // Player Impact Estimate
  E_OFF_RATING?: number; // Estimated Offensive Rating
  E_DEF_RATING?: number; // Estimated Defensive Rating
  E_NET_RATING?: number; // Estimated Net Rating
  E_PACE?: number; // Estimated Pace
  E_USG_PCT?: number; // Estimated Usage Percentage
  percentiles: Record<string, number>; // Percentile rankings
}

export interface PlayerAdvancedAnalytics {
  player_id: number;
  season: string;
  advanced_metrics: PlayerAdvancedMetrics;
  league_averages: Record<string, number>;
}

export interface TeamComprehensiveData {
  team_id: number;
  season: string;
  team_info: Record<string, any>;
  players: Array<Record<string, any>>;
  schedule: Array<Record<string, any>>;
  lineups: Array<Record<string, any>>;
  advanced_metrics: {
    basic_stats: Record<string, number>;
    schedule_analysis: Record<string, any>;
    player_contributions: Record<string, any>;
    lineup_analysis: Record<string, any>;
    league_rankings: Record<string, any>;
  };
  data_status: Record<string, string>;
}

/**
 * Load comprehensive league data efficiently
 * This reduces API calls by fetching all data at once
 */
export async function getComprehensiveLeagueData(season: string = '2024-25'): Promise<LeagueData> {
  try {
    const response = await fetch(`${API_BASE_URL}/league/comprehensive-data?season=${season}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store', // Always fetch fresh data for real-time analytics
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch comprehensive league data: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching comprehensive league data:', error);
    throw error;
  }
}

/**
 * Get advanced analytics for a specific player
 */
export async function getPlayerAdvancedAnalytics(
  playerId: number,
  season: string = '2024-25'
): Promise<PlayerAdvancedAnalytics> {
  try {
    const response = await fetch(
      `${API_BASE_URL}/league/player-advanced-analytics/${playerId}?season=${season}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        cache: 'no-store',
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch player advanced analytics: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching player advanced analytics:', error);
    throw error;
  }
}

/**
 * Get comprehensive team analytics
 */
export async function getTeamComprehensiveAnalytics(
  teamId: number,
  season: string = '2024-25'
): Promise<TeamComprehensiveData> {
  try {
    const response = await fetch(
      `${API_BASE_URL}/team/${teamId}/comprehensive-analytics?season=${season}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        cache: 'no-store',
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch team comprehensive analytics: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching team comprehensive analytics:', error);
    throw error;
  }
}

/**
 * Get league-wide player statistics efficiently
 */
export async function getLeaguePlayerStats(
  season: string = '2024-25',
  measureType: string = 'Base',
  perMode: string = 'PerGame'
): Promise<any> {
  try {
    const params = new URLSearchParams({
      season,
      measure_type: measureType,
      per_mode: perMode,
    });

    const response = await fetch(`${API_BASE_URL}/league/player-stats?${params}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch league player stats: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching league player stats:', error);
    throw error;
  }
}

/**
 * Get league-wide player estimated metrics
 */
export async function getLeaguePlayerEstimatedMetrics(season: string = '2024-25'): Promise<any> {
  try {
    const response = await fetch(
      `${API_BASE_URL}/league/player-estimated-metrics?season=${season}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        cache: 'no-store',
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch player estimated metrics: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching player estimated metrics:', error);
    throw error;
  }
}

/**
 * Get league-wide team estimated metrics
 */
export async function getLeagueTeamEstimatedMetrics(season: string = '2024-25'): Promise<any> {
  try {
    const response = await fetch(
      `${API_BASE_URL}/league/team-estimated-metrics?season=${season}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        cache: 'no-store',
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch team estimated metrics: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching team estimated metrics:', error);
    throw error;
  }
}

/**
 * Enhanced team data with comprehensive analytics
 */
export interface EnhancedTeamWithAnalytics {
  id: string;
  name: string;
  abbreviation: string;
  conference: string;
  division: string;
  logo: string;
  primaryColor: string;
  secondaryColor: string;

  // Real NBA data
  record: { wins: number; losses: number };
  winPct: number;

  // Advanced metrics
  offensiveRating: number;
  defensiveRating: number;
  netRating: number;
  pace: number;

  // Estimated metrics
  estimatedOffRating?: number;
  estimatedDefRating?: number;
  estimatedNetRating?: number;

  // League rankings
  rankings: {
    wins: number;
    offensiveRating: number;
    defensiveRating: number;
    netRating: number;
    pace: number;
  };

  // Player data
  topPlayers: Array<{
    name: string;
    position: string;
    ppg: number;
    rpg: number;
    apg: number;
    advancedMetrics?: PlayerAdvancedMetrics;
  }>;

  // Schedule analysis
  recentForm: string; // e.g., "W-L-W-W-L"
  homeRecord: string;
  awayRecord: string;

  // Status and context
  status: 'contender' | 'playoff-push' | 'rebuilding' | 'lottery';
  playoffOdds?: number;
  injuries: string[];
}

/**
 * Get enhanced teams with comprehensive analytics
 */
export async function getEnhancedTeamsWithComprehensiveAnalytics(
  season: string = '2024-25'
): Promise<EnhancedTeamWithAnalytics[]> {
  try {
    // First, load comprehensive league data
    const leagueData = await getComprehensiveLeagueData(season);

    // Get team stats and estimated metrics
    const [teamStats, teamEstimatedMetrics] = await Promise.all([
      fetch(`${API_BASE_URL}/league/team-stats?season=${season}&measure_type=Advanced&per_mode=PerGame`).then(r => r.json()),
      getLeagueTeamEstimatedMetrics(season)
    ]);

    // Process and combine data
    const teams: EnhancedTeamWithAnalytics[] = [];

    // Extract team data from league stats
    if (teamStats?.data_sets?.LeagueDashTeamStats) {
      const teamsData = teamStats.data_sets.LeagueDashTeamStats;

      for (const team of teamsData) {
        const enhancedTeam: EnhancedTeamWithAnalytics = {
          id: team.TEAM_ID?.toString() || '',
          name: team.TEAM_NAME || '',
          abbreviation: team.TEAM_ABBREVIATION || '',
          conference: '', // Will be filled from team mapping
          division: '',
          logo: `https://cdn.nba.com/logos/nba/${team.TEAM_ID}/primary/L/logo.svg`,
          primaryColor: '#000000', // Default, will be enhanced
          secondaryColor: '#FFFFFF',

          record: {
            wins: team.W || 0,
            losses: team.L || 0
          },
          winPct: team.W_PCT || 0,

          offensiveRating: team.OFF_RATING || 0,
          defensiveRating: team.DEF_RATING || 0,
          netRating: team.NET_RATING || 0,
          pace: team.PACE || 0,

          rankings: {
            wins: 0, // Will be calculated
            offensiveRating: 0,
            defensiveRating: 0,
            netRating: 0,
            pace: 0
          },

          topPlayers: [], // Will be populated from player data
          recentForm: '', // Will be calculated from schedule
          homeRecord: '',
          awayRecord: '',

          status: team.W_PCT > 0.6 ? 'contender' :
                  team.W_PCT > 0.45 ? 'playoff-push' :
                  team.W_PCT > 0.3 ? 'rebuilding' : 'lottery',
          injuries: []
        };

        teams.push(enhancedTeam);
      }
    }

    return teams;
  } catch (error) {
    console.error('Error fetching enhanced teams with comprehensive analytics:', error);
    throw error;
  }
}
