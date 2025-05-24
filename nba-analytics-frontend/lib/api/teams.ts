import { fetchFromAPI } from './fetch'; // Import the fetch wrapper
import { teamsDataService } from '@/lib/services/TeamsDataService';

// Team colors mapping for enhanced UI
export const TEAM_COLORS: Record<number, { primary: string; secondary: string }> = {
  1610612737: { primary: '#E03A3E', secondary: '#C1D32F' }, // Atlanta Hawks
  1610612738: { primary: '#007A33', secondary: '#BA9653' }, // Boston Celtics
  1610612751: { primary: '#000000', secondary: '#FFFFFF' }, // Brooklyn Nets
  1610612766: { primary: '#1D1160', secondary: '#00788C' }, // Charlotte Hornets
  1610612741: { primary: '#CE1141', secondary: '#000000' }, // Chicago Bulls
  1610612739: { primary: '#860038', secondary: '#FDBB30' }, // Cleveland Cavaliers
  1610612742: { primary: '#00538C', secondary: '#002B5E' }, // Dallas Mavericks
  1610612743: { primary: '#0E2240', secondary: '#FEC524' }, // Denver Nuggets
  1610612765: { primary: '#C8102E', secondary: '#1D42BA' }, // Detroit Pistons
  1610612744: { primary: '#1D428A', secondary: '#FFC72C' }, // Golden State Warriors
  1610612745: { primary: '#CE1141', secondary: '#000000' }, // Houston Rockets
  1610612754: { primary: '#002D62', secondary: '#FDBB30' }, // Indiana Pacers
  1610612746: { primary: '#C8102E', secondary: '#1D428A' }, // LA Clippers
  1610612747: { primary: '#552583', secondary: '#FDB927' }, // Los Angeles Lakers
  1610612763: { primary: '#5D76A9', secondary: '#12173F' }, // Memphis Grizzlies
  1610612748: { primary: '#98002E', secondary: '#F9A01B' }, // Miami Heat
  1610612749: { primary: '#00471B', secondary: '#EEE1C6' }, // Milwaukee Bucks
  1610612750: { primary: '#0C2340', secondary: '#236192' }, // Minnesota Timberwolves
  1610612740: { primary: '#0C2340', secondary: '#C8102E' }, // New Orleans Pelicans
  1610612752: { primary: '#006BB6', secondary: '#F58426' }, // New York Knicks
  1610612760: { primary: '#007AC1', secondary: '#EF3B24' }, // Oklahoma City Thunder
  1610612753: { primary: '#0077C0', secondary: '#C4CED4' }, // Orlando Magic
  1610612755: { primary: '#006BB6', secondary: '#ED174C' }, // Philadelphia 76ers
  1610612756: { primary: '#1D1160', secondary: '#E56020' }, // Phoenix Suns
  1610612757: { primary: '#E03A3E', secondary: '#000000' }, // Portland Trail Blazers
  1610612758: { primary: '#5A2D81', secondary: '#63727A' }, // Sacramento Kings
  1610612759: { primary: '#C4CED4', secondary: '#000000' }, // San Antonio Spurs
  1610612761: { primary: '#CE1141', secondary: '#000000' }, // Toronto Raptors
  1610612762: { primary: '#002B5C', secondary: '#00471B' }, // Utah Jazz
  1610612764: { primary: '#002B5C', secondary: '#E31837' }  // Washington Wizards
};

// Interface for a single team's standing data
export interface TeamStanding {
  TeamID: number;
  TeamName: string;
  Conference: string;
  PlayoffRank: number;
  WinPct: number;
  GB: number;
  L10: string;
  STRK: string;
  WINS: number;
  LOSSES: number;
  HOME: string;
  ROAD: string;
  Division: string;
  ClinchIndicator: string;
  DivisionRank: number;
  ConferenceRecord: string;
  DivisionRecord: string;
}

// Interface for the structure returned by the getLeagueStandings function
export interface StandingsResponse {
  standings: TeamStanding[];
}

// Interface often useful for separating standings by conference later
export interface ConferenceStandings {
  eastern: TeamStanding[];
  western: TeamStanding[];
}

// Interface for team stats
export interface TeamStats {
  info: {
    team_id: number;
    team_city: string;
    team_name: string;
    team_division: string;
    conf_rank: number;
    wins: number;
    losses: number;
    win_pct: number;
    last_ten: string;
  };
  stats: {
    overall: {
      pts: number;
      opp_pts: number;
    };
  };
}

// Interface for teams by conference
export interface TeamsByConference {
  eastern: TeamStats[];
  western: TeamStats[];
}

// Enhanced team interface for the teams page
export interface EnhancedTeam {
  id: string;
  name: string;
  abbreviation: string;
  conference: 'East' | 'West';
  division: string;
  logo: string;
  primaryColor: string;
  secondaryColor: string;
  record: {
    wins: number;
    losses: number;
  };
  streak: {
    type: 'W' | 'L';
    count: number;
  };
  lastGame: {
    opponent: string;
    result: 'W' | 'L';
    score: string;
  };
  nextGame: {
    opponent: string;
    date: string;
    home: boolean;
  };
  offensiveRating: number;
  defensiveRating: number;
  pace: number;
  playoffOdds: number;
  keyPlayers: string[];
  injuries: string[];
  recentTrades: string[];
  capSpace: number;
  status: 'contender' | 'playoff-push' | 'rebuilding';
}

// Team details interface
export interface TeamDetails {
  info: {
    team_id: number;
    team_name: string;
    team_city: string;
    team_abbreviation: string;
    team_conference: string;
    team_division: string;
    arena: string;
    founded_year: number;
  };
  ranks: {
    conference_rank: number;
    division_rank: number;
    playoff_rank: number;
  };
  roster: Array<{
    player_id: number;
    player_name: string;
    position: string;
    jersey_number: string;
    height: string;
    weight: string;
    birth_date: string;
    experience: string;
  }>;
  coaches: Array<{
    coach_name: string;
    coach_type: string;
    is_assistant: boolean;
  }>;
}

// Team stats interface
export interface TeamStatsDetailed {
  current_stats: {
    overall: {
      games_played: number;
      wins: number;
      losses: number;
      win_pct: number;
      pts: number;
      opp_pts: number;
      plus_minus: number;
    };
    advanced: {
      offensive_rating: number;
      defensive_rating: number;
      net_rating: number;
      pace: number;
      true_shooting_pct: number;
      effective_fg_pct: number;
      turnover_pct: number;
      offensive_rebound_pct: number;
      defensive_rebound_pct: number;
    };
  };
  historical_stats: Array<{
    season: string;
    games_played: number;
    wins: number;
    losses: number;
    win_pct: number;
    pts: number;
    opp_pts: number;
  }>;
}

/**
 * Fetches league standings from the API.
 * Uses fetchFromAPI wrapper.
 * Handles potential double-encoded JSON from the backend.
 * @param {string} season - The season to fetch standings for (e.g., "2024-25")
 * @returns {Promise<StandingsResponse>} A promise that resolves to the parsed standings data.
 */
export async function getLeagueStandings(season?: string): Promise<StandingsResponse> {
  const endpoint = '/league/standings'; // Corrected: Added /league prefix
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const rawData = await fetchFromAPI<Record<string, unknown> | string>(urlWithParams, {
      method: 'GET',
    });

    let data: Record<string, unknown>;
    // TODO: Remove this double-parsing if API can be fixed to consistently return JSON.
    if (typeof rawData === 'string') {
      console.log('Server', 'Detected string response, attempting second parse...');
      try {
        data = JSON.parse(rawData);
      } catch (secondParseError: unknown) {
         console.error('Server', 'Failed second JSON parse:', secondParseError);
         throw new Error(`Failed second JSON parse (double encoding?): ${secondParseError instanceof Error ? secondParseError.message : String(secondParseError)}`);
      }
    } else if (rawData && typeof rawData === 'object') {
       data = rawData;
    } else {
        console.error('Server', 'Unexpected data type received from fetchFromAPI:', typeof rawData);
        throw new Error('Invalid response format received from API helper');
    }

    if (!data || !('standings' in data) || !Array.isArray(data.standings)) {
      console.error('Server', 'Invalid standings data structure received:', data);
      throw new Error('Invalid standings response format');
    }

    const mappedStandings: TeamStanding[] = data.standings.map((standing: Record<string, unknown>): TeamStanding => {
        if (!standing || typeof standing !== 'object') {
            console.warn('Server', 'Mapping warning: Invalid item in standings array:', standing);
            return {
                TeamID: 0, TeamName: 'Invalid Data', Conference: '', PlayoffRank: 0, WinPct: 0,
                GB: 0, L10: '', STRK: '', WINS: 0, LOSSES: 0, HOME: '', ROAD: '', Division: '',
                ClinchIndicator: '', DivisionRank: 0, ConferenceRecord: '', DivisionRecord: ''
            };
        }
        return {
            TeamID: Number(standing.TeamID) || 0,
            TeamName: String(standing.TeamName || '').trim(),
            Conference: String(standing.Conference || '').trim(),
            PlayoffRank: Number(standing.PlayoffRank) || 0,
            WinPct: Number(standing.WinPct) || 0,
            GB: Number(standing.GB) || 0,
            L10: String(standing.L10 || '').trim(),
            STRK: String(standing.STRK || '').trim(),
            WINS: Number(standing.WINS) || 0,
            LOSSES: Number(standing.LOSSES) || 0,
            HOME: String(standing.HOME || '').trim(),
            ROAD: String(standing.ROAD || '').trim(),
            Division: String(standing.Division || '').trim(),
            ClinchIndicator: String(standing.ClinchIndicator || '').trim(),
            DivisionRank: Number(standing.DivisionRank) || 0,
            ConferenceRecord: String(standing.ConferenceRecord || '').trim(),
            DivisionRecord: String(standing.DivisionRecord || '').trim()
        };
    });

    return { standings: mappedStandings };

  } catch (error: unknown) {
    console.error(`Server: Error fetching standings for season ${season}:`, error instanceof Error ? error.message : String(error));
    throw error;
  }
}

export async function getTeamsByConference(season?: string): Promise<TeamsByConference> {
  try {
    console.log('Fetching teams for season:', season);
    const { standings } = await getLeagueStandings(season);

    // Transform standings data into TeamStats format
    const transformTeam = (standing: TeamStanding): TeamStats => ({
      info: {
        team_id: standing.TeamID,
        team_city: standing.TeamName.split(' ')[0],
        team_name: standing.TeamName.split(' ').slice(1).join(' '),
        team_division: standing.Division,
        conf_rank: standing.PlayoffRank,
        wins: standing.WINS,
        losses: standing.LOSSES,
        win_pct: standing.WinPct,
        last_ten: standing.L10.trim()
      },
      stats: {
        overall: {
          pts: 0,
          opp_pts: 0
        }
      }
    });

    // Separate and transform teams by conference
    const eastern: TeamStats[] = [];
    const western: TeamStats[] = [];

    standings.forEach((standing) => {
      const transformedTeam = transformTeam(standing);
      if (standing.Conference.toLowerCase() === 'east') {
        eastern.push(transformedTeam);
      } else {
        western.push(transformedTeam);
      }
    });

    return { eastern, western };
  } catch (error) {
    console.error('Error fetching teams:', error);
    throw error;
  }
}

/**
 * Fetches detailed team information including roster and coaching staff
 */
export async function getTeamDetails(teamId: string, season?: string): Promise<TeamDetails> {
  const endpoint = `/team/${teamId}/info_roster`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<TeamDetails>(urlWithParams, { method: 'GET' });
    return data;
  } catch (error) {
    console.error(`Error fetching team details for ${teamId}:`, error);
    throw error;
  }
}

/**
 * Fetches detailed team statistics including advanced metrics
 */
export async function getTeamStats(teamId: string, season?: string): Promise<TeamStatsDetailed> {
  const endpoint = `/team/${teamId}/stats`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  params.append('measure_type', 'Advanced'); // Get advanced stats
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<TeamStatsDetailed>(urlWithParams, { method: 'GET' });
    return data;
  } catch (error) {
    console.error(`Error fetching team stats for ${teamId}:`, error);
    throw error;
  }
}

/**
 * Fetches estimated metrics for all teams at once
 */
export async function getAllTeamsEstimatedMetrics(season?: string): Promise<any> {
  const endpoint = '/team/estimated-metrics';
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });
    return data;
  } catch (error) {
    console.error('Error fetching all teams estimated metrics:', error);
    throw error;
  }
}

/**
 * Fetches league-wide team statistics
 */
export async function getLeagueTeamStats(season?: string): Promise<any> {
  const endpoint = '/league/team-stats';
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });
    return data;
  } catch (error) {
    console.error('Error fetching league team stats:', error);
    throw error;
  }
}

/**
 * Fetches team tracking statistics (passing, rebounding, shooting)
 */
export async function getTeamTrackingStats(teamId: string, season?: string): Promise<any> {
  const endpoints = [
    `/team/${teamId}/tracking/passing`,
    `/team/${teamId}/tracking/rebounding`,
    `/team/${teamId}/tracking/shooting`
  ];

  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const paramString = params.toString();

  try {
    const [passing, rebounding, shooting] = await Promise.all(
      endpoints.map(endpoint =>
        fetchFromAPI<any>(`${endpoint}?${paramString}`, { method: 'GET' })
      )
    );

    return {
      passing,
      rebounding,
      shooting
    };
  } catch (error) {
    console.error(`Error fetching tracking stats for team ${teamId}:`, error);
    throw error;
  }
}

/**
 * Fetches comprehensive team data for dashboard
 */
export async function getTeamDashboardData(teamId: string, season?: string): Promise<any> {
  const endpoint = `/team/${teamId}/stats`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  params.append('measure_type', 'Advanced'); // Get advanced stats
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const stats = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });
    return stats; // Return the stats directly, not wrapped in an object
  } catch (error) {
    console.error(`Error fetching dashboard data for team ${teamId}:`, error);
    throw error;
  }
}

/**
 * Fetches team player statistics
 */
export async function getTeamPlayerStats(teamId: string, season?: string): Promise<any> {
  const endpoint = `/team/${teamId}/players`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  params.append('per_mode', 'PerGame'); // Get per-game stats
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const playerStats = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });
    return playerStats;
  } catch (error) {
    console.error(`Error fetching player stats for team ${teamId}:`, error);
    throw error;
  }
}

/**
 * Fetches league averages for team stats
 */
export async function getLeagueAverages(season?: string): Promise<any> {
  const endpoint = `/league/team-stats`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  params.append('measure_type', 'Advanced');
  params.append('per_mode', 'PerGame');
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const leagueStats = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });

    // Calculate league averages from all teams
    const teams = leagueStats.data_sets?.LeagueDashTeamStats || [];
    if (teams.length === 0) return null;

    const averages = {
      OFF_RATING: teams.reduce((sum: number, team: any) => sum + (team.OFF_RATING || 0), 0) / teams.length,
      DEF_RATING: teams.reduce((sum: number, team: any) => sum + (team.DEF_RATING || 0), 0) / teams.length,
      NET_RATING: teams.reduce((sum: number, team: any) => sum + (team.NET_RATING || 0), 0) / teams.length,
      PACE: teams.reduce((sum: number, team: any) => sum + (team.PACE || 0), 0) / teams.length,
      EFG_PCT: teams.reduce((sum: number, team: any) => sum + (team.EFG_PCT || 0), 0) / teams.length,
      TS_PCT: teams.reduce((sum: number, team: any) => sum + (team.TS_PCT || 0), 0) / teams.length,
      TM_TOV_PCT: teams.reduce((sum: number, team: any) => sum + (team.TM_TOV_PCT || 0), 0) / teams.length,
      OREB_PCT: teams.reduce((sum: number, team: any) => sum + (team.OREB_PCT || 0), 0) / teams.length
    };

    return averages;
  } catch (error) {
    console.error(`Error fetching league averages:`, error);
    throw error;
  }
}

/**
 * Fetches team schedule/game logs
 */
export async function getTeamSchedule(teamId: string, season?: string): Promise<any> {
  const endpoint = `/team/${teamId}/schedule`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const schedule = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });
    return schedule;
  } catch (error) {
    console.error(`Error fetching schedule for team ${teamId}:`, error);
    throw error;
  }
}

/**
 * Enhanced team functions using the data service
 * Implements proper data hierarchy: League → Team → Player
 */

/**
 * Get enhanced teams using efficient data hierarchy
 */
export async function getEnhancedTeams(season: string = '2024-25'): Promise<EnhancedTeam[]> {
  return teamsDataService.getEnhancedTeams(season);
}

/**
 * Get enhanced teams with comprehensive statistics
 * Uses league data first, falls back to team-specific data
 */
export async function getEnhancedTeamsWithStats(season: string = '2024-25'): Promise<EnhancedTeam[]> {
  return teamsDataService.getEnhancedTeamsWithStats(season);
}

/**
 * Get all teams basic info (most efficient)
 */
export async function getAllTeams(): Promise<EnhancedTeam[]> {
  return getEnhancedTeams();
}

/**
 * Fetches team lineups
 */
export async function getTeamLineups(teamId: string, season?: string): Promise<any> {
  const endpoint = `/team/${teamId}/lineups`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const lineups = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });
    return lineups;
  } catch (error) {
    console.error(`Error fetching lineups for team ${teamId}:`, error);
    throw error;
  }
}



/**
 * Fetches team passing statistics
 */
export async function getTeamPassingStats(teamId: string, season?: string): Promise<any> {
  const endpoint = `/team/${teamId}/tracking/passing`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });
    return data;
  } catch (error) {
    console.error(`Error fetching passing stats for team ${teamId}:`, error);
    throw error;
  }
}

/**
 * Fetches team rebounding statistics
 */
export async function getTeamReboundingStats(teamId: string, season?: string): Promise<any> {
  const endpoint = `/team/${teamId}/tracking/rebounding`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });
    return data;
  } catch (error) {
    console.error(`Error fetching rebounding stats for team ${teamId}:`, error);
    throw error;
  }
}

/**
 * Fetches team shooting statistics
 */
export async function getTeamShootingStats(teamId: string, season?: string): Promise<any> {
  const endpoint = `/team/${teamId}/tracking/shooting`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });
    return data;
  } catch (error) {
    console.error(`Error fetching shooting stats for team ${teamId}:`, error);
    throw error;
  }
}

/**
 * Fetches team comparison data for multiple teams
 */
export async function getTeamComparison(teamIds: string[], season?: string): Promise<any> {
  try {
    const teamData = await Promise.all(
      teamIds.map(teamId => getTeamDashboardData(teamId, season))
    );

    return teamData.map((data, index) => ({
      teamId: teamIds[index],
      ...data
    }));
  } catch (error) {
    console.error('Error fetching team comparison data:', error);
    throw error;
  }
}

// REMOVED: Duplicate TEAM_COLORS declaration - using the one at the top of the file

/**
 * Calculate playoff odds based on current standings and performance
 */
function calculatePlayoffOdds(winPct: number, conference: string, rank: number): number {
  // Simple playoff odds calculation based on win percentage and conference rank
  if (rank <= 6) return Math.min(95, winPct * 100 + 20);
  if (rank <= 10) return Math.min(80, winPct * 100 + 10);
  return Math.max(5, winPct * 100 - 20);
}

/**
 * Determine team status based on performance and context
 */
function determineTeamStatus(winPct: number, rank: number): 'contender' | 'playoff-push' | 'rebuilding' {
  if (winPct > 0.65 && rank <= 4) return 'contender';
  if (winPct > 0.45 && rank <= 10) return 'playoff-push';
  return 'rebuilding';
}



// REMOVED: Duplicate getEnhancedTeams function - using the one from TeamsDataService

// REMOVED: Duplicate getEnhancedTeamsWithStats function - using the one from TeamsDataService

// Sample JSON (for reference, matches the structure processed by getLeagueStandings)
/*
{"standings": [{"TeamID": 1610612738, "TeamName": "Boston Celtics", "Conference": "East", ... }, ... ]}
*/





// REMOVED: Duplicate getAllTeams function - using the one from TeamsDataService

// TEAM_COLORS is already exported at the top of the file