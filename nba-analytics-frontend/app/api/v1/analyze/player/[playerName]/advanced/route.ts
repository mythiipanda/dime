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

  try {
    const apiUrl = `${API_BASE_URL}/analyze/player/${encodeURIComponent(playerName)}/advanced`;
    
    const response = await fetch(apiUrl, {
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: `HTTP error ${response.status}` }));
      console.error(`Advanced metrics fetch failed (${response.status}):`, errorData);
      return NextResponse.json(
        { error: errorData.detail || `Failed to fetch advanced metrics (${response.status})` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching advanced metrics:', error);
    return NextResponse.json(
      { error: 'Failed to fetch advanced metrics' },
      { status: 500 }
    );
  }
}
