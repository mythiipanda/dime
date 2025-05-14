import { NextRequest, NextResponse } from 'next/server';
import { API_BASE_URL } from '@/lib/config';

export async function GET(
  request: NextRequest,
  { params }: { params: { playerName: string } }
) {
  const playerName = params.playerName;
  
  if (!playerName) {
    return NextResponse.json(
      { error: 'Player name is required' },
      { status: 400 }
    );
  }

  // Get query parameters
  const searchParams = request.nextUrl.searchParams;
  const season = searchParams.get('season') || undefined;
  const seasonType = searchParams.get('seasonType') || 'Regular Season';
  const chartType = searchParams.get('chartType') || 'scatter';
  const outputFormat = searchParams.get('outputFormat') || 'base64';

  try {
    // Build the API URL with query parameters
    let apiUrl = `${API_BASE_URL}/analyze/player/${encodeURIComponent(playerName)}/advanced-shotchart`;
    
    // Add query parameters if they exist
    const queryParams = new URLSearchParams();
    if (season) queryParams.append('season', season);
    if (seasonType) queryParams.append('season_type', seasonType);
    if (chartType) queryParams.append('chart_type', chartType);
    if (outputFormat) queryParams.append('output_format', outputFormat);
    
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
      console.error(`Advanced shot chart fetch failed (${response.status}):`, errorData);
      return NextResponse.json(
        { error: errorData.detail || `Failed to fetch advanced shot chart data (${response.status})` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching advanced shot chart data:', error);
    return NextResponse.json(
      { error: 'Failed to fetch advanced shot chart data' },
      { status: 500 }
    );
  }
}
