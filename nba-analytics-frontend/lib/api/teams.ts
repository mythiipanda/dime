import { API_BASE_URL } from '@/lib/config';

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
 * Fetches league standings from the API and parses them.
 * @param {string} season - The season to fetch standings for (e.g., "2024-25")
 * @returns {Promise<StandingsResponse>} A promise that resolves to the parsed standings data.
 */
export async function getLeagueStandings(season?: string): Promise<StandingsResponse> {
  let response: Response | null = null;
  try {
    // Add season as a query parameter if provided
    const url = new URL(`${API_BASE_URL}/standings`);
    if (season) {
      url.searchParams.append('season', season);
    }
    
    console.log('Fetching standings from:', url.toString());
    response = await fetch(url.toString());

    if (!response.ok) {
       const errorBody = await response.text().catch(() => 'Could not read error body');
       console.error('Server', `HTTP error! status: ${response.status}, statusText: ${response.statusText}, body: ${errorBody}`);
       throw new Error(`HTTP error! status: ${response.status}`);
    }

    // --- Get RAW text ---
    const rawText = await response.text();

    // --- Attempt initial parse ---
    let parsedData: Record<string, unknown>;
    try {
        if (!rawText || rawText.trim() === '') {
             console.error('Server', 'Received empty response body.');
             throw new Error('Invalid response format: empty body');
        }
        parsedData = JSON.parse(rawText); // First parse
        console.log('Server', `Fetched standings for season: ${season || 'default'}`);

    } catch (parseError: unknown) {
        console.error('Server', 'Failed initial JSON parse:', parseError);
        console.error('Server', 'Raw text that failed initial parse:', rawText.substring(0, 500) + '...');
        throw new Error(`Failed initial JSON parse: ${parseError instanceof Error ? parseError.message : String(parseError)}`);
    }

    // --- Check for double encoding and perform second parse if needed ---
    let data: Record<string, unknown>;
    if (typeof parsedData === 'string') {
        console.log('Server', 'Detected string after first parse, attempting second parse...');
        try {
            data = JSON.parse(parsedData);
        } catch (secondParseError: unknown) {
             console.error('Server', 'Failed second JSON parse:', secondParseError);
             console.error('Server', 'String content that failed second parse:', parsedData.substring(0, 500) + '...');
             throw new Error(`Failed second JSON parse (double encoding issue?): ${secondParseError instanceof Error ? secondParseError.message : String(secondParseError)}`);
        }
    } else {
        data = parsedData;
    }

    // --- Validation ---
    if (!data || typeof data !== 'object' || !('standings' in data) || !Array.isArray(data.standings)) {
        console.error('Server', 'Invalid data structure received:', data);
        throw new Error('Invalid response format');
    }

    // --- Data Mapping ---
    const mappedStandings: TeamStanding[] = data.standings.map((standing: Record<string, unknown>): TeamStanding => {
        if (!standing || typeof standing !== 'object') {
            console.warn('Server', 'Mapping warning: Invalid item in standings array:', standing);
            return {
                TeamID: 0,
                TeamName: 'Invalid Data',
                Conference: '',
                PlayoffRank: 0,
                WinPct: 0,
                GB: 0,
                L10: '',
                STRK: '',
                WINS: 0,
                LOSSES: 0,
                HOME: '',
                ROAD: '',
                Division: '',
                ClinchIndicator: '',
                DivisionRank: 0,
                ConferenceRecord: '',
                DivisionRecord: ''
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
      console.error('Server', `Error fetching standings for season ${season}:`, error instanceof Error ? error.message : String(error));
      throw error;
  }
}

export function formatRecord(wins: number, losses: number): string {
  return `${wins}-${losses}`;
}

export function formatWinPct(pct: number): string {
  // Ensure pct is a number before calling toFixed
  const numPct = Number(pct);
  if (isNaN(numPct)) {
    return 'N/A';
  }
  return (numPct * 100).toFixed(1);
}


export function getGamesBehind(gb: number): string {
  const numGb = Number(gb);
  if (isNaN(numGb) || numGb === 0) return '-';
  return numGb.toFixed(1);
}

export function getRecordColor(wins: number, losses: number): string {
  const totalGames = wins + losses;
  if (totalGames === 0) return 'text-gray-500'; // Handle division by zero

  const winPct = wins / totalGames;
  if (winPct >= 0.6) return 'text-green-500';
  if (winPct <= 0.4) return 'text-red-500';
  return 'text-yellow-500';
}

export function formatStreak(streak: string): string {
  return String(streak || '').trim(); // Ensure it's a string before trimming
}

export function getClinchIndicators(indicator?: string): string[] {
  if (!indicator || typeof indicator !== 'string') return [];

  // Normalize: Trim whitespace, replace common prefixes, then split by '-', trim parts.
  const parts = indicator
    .trim()
    .replace(/^[\s*-]+/, '') // Remove leading space/hyphen/asterisk
    .split('-')
    .map(s => s.trim().toLowerCase()) // Trim each part and make lowercase
    .filter(i => i); // Remove empty strings

  if (parts.length === 0) return [];

  return parts.map(i => {
    switch(i) {
      // Playoff/Conference/League Status
      case 'x': return 'Clinched Playoff Spot';
      case 'y': return 'Clinched Division Title'; // Most common meaning for y
      case 'z': return 'Clinched Conference Best Record';
      case '*': return 'Clinched Conference Best Record'; // Or potentially 'Clinched' generally
      case 'w': return 'Clinched Conference/Division'; // Ambiguous - label cautiously or check API docs
      case 'p': return 'Clinched Play-In Spot';
      case 'pi': return 'Clinched Play-In Spot';
      case 'e': return 'Eliminated from Contention';
      case 'o': return 'Eliminated from Contention';

      // Division Titles
      case 'a': // Fall-through
      case 'atl': return 'Clinched Atlantic Division';
      case 'c': // Fall-through - also used in your example, likely for Central Division
      case 'cen': return 'Clinched Central Division';
      case 'se': return 'Clinched Southeast Division';
      case 'nw': return 'Clinched Northwest Division';
      case 'p': // Fall-through - careful, 'p' also means play-in, context matters!
      case 'pac': return 'Clinched Pacific Division';
      case 'sw': return 'Clinched Southwest Division';

      default:
          console.warn(`Unknown clinch indicator part: '${i}' in full indicator '${indicator}'`);
          return `Unknown (${i})`; // Return something indicating unknown status
    }
  }).filter((value, index, self) => self.indexOf(value) === index); // Remove duplicates if any arise
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