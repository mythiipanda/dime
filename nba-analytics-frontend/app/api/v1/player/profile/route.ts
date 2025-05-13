import { NextRequest, NextResponse } from 'next/server';
import { API_BASE_URL } from '@/lib/config';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const playerName = searchParams.get('player_name');
  
  if (!playerName) {
    return NextResponse.json(
      { detail: 'Player name is required' },
      { status: 400 }
    );
  }

  try {
    const profileUrl = `${API_BASE_URL}/player/profile?player_name=${encodeURIComponent(playerName)}`;
    
    const response = await fetch(profileUrl, {
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: `HTTP error ${response.status}` }));
      console.error(`Player profile fetch failed (${response.status}):`, errorData);
      return NextResponse.json(
        { detail: errorData.detail || `Failed to fetch player profile (${response.status})` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching player profile:', error);
    return NextResponse.json(
      { detail: 'Failed to fetch player profile' },
      { status: 500 }
    );
  }
}
