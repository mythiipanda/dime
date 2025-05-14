import { NextRequest, NextResponse } from 'next/server';
import { API_BASE_URL } from '@/lib/config';

export async function GET(request: NextRequest) {
  // Get query parameters
  const searchParams = request.nextUrl.searchParams;
  const playerNames = searchParams.getAll('player_names');
  const season = searchParams.get('season') || undefined;
  const seasonType = searchParams.get('seasonType') || 'Regular Season';
  const chartType = searchParams.get('chartType') || 'scatter';
  const outputFormat = searchParams.get('outputFormat') || 'base64';
  const useCache = searchParams.get('useCache') !== 'false'; // Default to true
  
  if (!playerNames || playerNames.length < 2) {
    return NextResponse.json(
      { error: 'At least two player names are required' },
      { status: 400 }
    );
  }

  if (playerNames.length > 4) {
    return NextResponse.json(
      { error: 'Maximum of 4 players can be compared at once' },
      { status: 400 }
    );
  }

  try {
    // Build the API URL with query parameters
    let apiUrl = `${API_BASE_URL}/analyze/players/compare-shots`;
    
    // Add query parameters
    const queryParams = new URLSearchParams();
    
    // Add each player name as a separate query parameter
    playerNames.forEach(name => {
      queryParams.append('player_names', name);
    });
    
    if (season) queryParams.append('season', season);
    if (seasonType) queryParams.append('season_type', seasonType);
    if (chartType) queryParams.append('chart_type', chartType);
    if (outputFormat) queryParams.append('output_format', outputFormat);
    queryParams.append('use_cache', useCache.toString());
    
    const queryString = queryParams.toString();
    if (queryString) {
      apiUrl += `?${queryString}`;
    }
    
    const response = await fetch(apiUrl, {
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: `HTTP error ${response.status}` }));
      console.error(`Player comparison fetch failed (${response.status}):`, errorData);
      return NextResponse.json(
        { error: errorData.detail || `Failed to fetch player comparison data (${response.status})` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching player comparison data:', error);
    return NextResponse.json(
      { error: 'Failed to fetch player comparison data' },
      { status: 500 }
    );
  }
}
