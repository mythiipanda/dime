import { fetchFromAPI } from './fetch'; // Import the fetch wrapper

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

// Sample JSON (for reference, matches the structure processed by getLeagueStandings)
/*
{"standings": [{"TeamID": 1610612738, "TeamName": "Boston Celtics", "Conference": "East", ... }, ... ]}
*/