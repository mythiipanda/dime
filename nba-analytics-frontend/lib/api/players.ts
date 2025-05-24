import { fetchFromAPI } from './fetch';
import { PlayerProfile, PlayerGameLog, PlayerBioInfo, ShotChartPoint } from '@/models/stats/PlayerStats';

/**
 * Fetches player profile information including bio, stats, and advanced metrics
 */
export async function getPlayerProfile(playerId: string, season?: string): Promise<PlayerProfile> {
  const endpoint = `/player/${playerId}/profile`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<PlayerProfile>(urlWithParams, { method: 'GET' });
    return data;
  } catch (error) {
    console.error(`Error fetching player profile for ${playerId}:`, error);
    throw error;
  }
}

/**
 * Fetches player basic information and bio
 */
export async function getPlayerInfo(playerId: string): Promise<PlayerBioInfo> {
  const endpoint = `/player/${playerId}/info`;

  try {
    const data = await fetchFromAPI<PlayerBioInfo>(endpoint, { method: 'GET' });
    return data;
  } catch (error) {
    console.error(`Error fetching player info for ${playerId}:`, error);
    throw error;
  }
}

/**
 * Fetches player game log for a specific season
 */
export async function getPlayerGameLog(playerId: string, season?: string): Promise<PlayerGameLog[]> {
  const endpoint = `/player/${playerId}/gamelog`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<{ games: PlayerGameLog[] }>(urlWithParams, { method: 'GET' });
    return data.games || [];
  } catch (error) {
    console.error(`Error fetching game log for player ${playerId}:`, error);
    throw error;
  }
}

/**
 * Fetches player shot chart data
 */
export async function getPlayerShotChart(playerId: string, season?: string): Promise<ShotChartPoint[]> {
  const endpoint = `/player/${playerId}/shotchart`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<{ shots: ShotChartPoint[] }>(urlWithParams, { method: 'GET' });
    return data.shots || [];
  } catch (error) {
    console.error(`Error fetching shot chart for player ${playerId}:`, error);
    throw error;
  }
}

/**
 * Fetches player statistics for a specific season
 */
export async function getPlayerStats(playerId: string, season?: string, statType: 'basic' | 'advanced' | 'shooting' = 'basic'): Promise<any> {
  const endpoint = `/player/${playerId}/stats`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  params.append('stat_type', statType);
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });
    return data;
  } catch (error) {
    console.error(`Error fetching ${statType} stats for player ${playerId}:`, error);
    throw error;
  }
}

/**
 * Fetches player comparison data for multiple players
 */
export async function getPlayerComparison(playerIds: string[], season?: string): Promise<any> {
  const endpoint = '/players/compare';
  const params = new URLSearchParams();
  params.append('player_ids', playerIds.join(','));
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });
    return data;
  } catch (error) {
    console.error('Error fetching player comparison:', error);
    throw error;
  }
}

/**
 * Searches for players by name or other criteria
 */
export async function searchPlayers(query: string, filters?: {
  team?: string;
  position?: string;
  active?: boolean;
}): Promise<PlayerBioInfo[]> {
  const endpoint = '/players/search';
  const params = new URLSearchParams();
  params.append('q', query);

  if (filters) {
    if (filters.team) params.append('team', filters.team);
    if (filters.position) params.append('position', filters.position);
    if (filters.active !== undefined) params.append('active', filters.active.toString());
  }

  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<{ players: PlayerBioInfo[] }>(urlWithParams, { method: 'GET' });
    return data.players || [];
  } catch (error) {
    console.error('Error searching players:', error);
    throw error;
  }
}

/**
 * Fetches all active players
 */
export async function getAllPlayers(season?: string): Promise<PlayerBioInfo[]> {
  const endpoint = '/players';
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<{ players: PlayerBioInfo[] }>(urlWithParams, { method: 'GET' });
    return data.players || [];
  } catch (error) {
    console.error('Error fetching all players:', error);
    throw error;
  }
}

/**
 * Fetches player awards and achievements
 */
export async function getPlayerAwards(playerId: string): Promise<any[]> {
  const endpoint = `/player/${playerId}/awards`;

  try {
    const data = await fetchFromAPI<{ awards: any[] }>(endpoint, { method: 'GET' });
    return data.awards || [];
  } catch (error) {
    console.error(`Error fetching awards for player ${playerId}:`, error);
    throw error;
  }
}

/**
 * Fetches player injury history
 */
export async function getPlayerInjuries(playerId: string): Promise<any[]> {
  const endpoint = `/player/${playerId}/injuries`;

  try {
    const data = await fetchFromAPI<{ injuries: any[] }>(endpoint, { method: 'GET' });
    return data.injuries || [];
  } catch (error) {
    console.error(`Error fetching injuries for player ${playerId}:`, error);
    throw error;
  }
}

/**
 * Fetches player career highlights and milestones
 */
export async function getPlayerHighlights(playerId: string): Promise<any[]> {
  const endpoint = `/player/${playerId}/highlights`;

  try {
    const data = await fetchFromAPI<{ highlights: any[] }>(endpoint, { method: 'GET' });
    return data.highlights || [];
  } catch (error) {
    console.error(`Error fetching highlights for player ${playerId}:`, error);
    throw error;
  }
}

/**
 * Fetches player season splits (home/away, by month, etc.)
 */
export async function getPlayerSeasonSplits(playerId: string, season?: string): Promise<any> {
  const endpoint = `/player/${playerId}/splits`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });
    return data;
  } catch (error) {
    console.error(`Error fetching season splits for player ${playerId}:`, error);
    throw error;
  }
}

/**
 * Fetches player tracking stats (speed, distance, touches, etc.)
 */
export async function getPlayerTrackingStats(playerId: string, season?: string, statType: 'speed' | 'touches' | 'passing' | 'rebounding' | 'shooting' = 'speed'): Promise<any> {
  const endpoint = `/player/${playerId}/tracking`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  params.append('stat_type', statType);
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });
    return data;
  } catch (error) {
    console.error(`Error fetching ${statType} tracking stats for player ${playerId}:`, error);
    throw error;
  }
}

/**
 * Fetches player hustle stats (deflections, loose balls, charges drawn, etc.)
 */
export async function getPlayerHustleStats(playerId: string, season?: string): Promise<any> {
  const endpoint = `/player/${playerId}/hustle`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });
    return data;
  } catch (error) {
    console.error(`Error fetching hustle stats for player ${playerId}:`, error);
    throw error;
  }
}

/**
 * Fetches player clutch time statistics
 */
export async function getPlayerClutchStats(playerId: string, season?: string): Promise<any> {
  const endpoint = `/player/${playerId}/clutch`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });
    return data;
  } catch (error) {
    console.error(`Error fetching clutch stats for player ${playerId}:`, error);
    throw error;
  }
}



/**
 * Fetches player playoff statistics
 */
export async function getPlayerPlayoffStats(playerId: string, season?: string): Promise<any> {
  const endpoint = `/player/${playerId}/playoffs`;
  const params = new URLSearchParams();
  if (season) {
    params.append('season', season);
  }
  const urlWithParams = `${endpoint}?${params.toString()}`;

  try {
    const data = await fetchFromAPI<any>(urlWithParams, { method: 'GET' });
    return data;
  } catch (error) {
    console.error(`Error fetching playoff stats for player ${playerId}:`, error);
    throw error;
  }
}
