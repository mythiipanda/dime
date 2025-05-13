import { NextRequest, NextResponse } from 'next/server';
import { API_BASE_URL } from '@/lib/config';

export async function GET(
  request: NextRequest,
  { params }: { params: { playerId: string } }
) {
  const playerId = params.playerId;
  
  if (!playerId) {
    return NextResponse.json(
      { detail: 'Player ID is required' },
      { status: 400 }
    );
  }

  try {
    const headshotUrl = `${API_BASE_URL}/player/${playerId}/headshot`;
    
    const response = await fetch(headshotUrl, {
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: `HTTP error ${response.status}` }));
      console.error(`Player headshot fetch failed (${response.status}):`, errorData);
      return NextResponse.json(
        { detail: errorData.detail || `Failed to fetch player headshot (${response.status})` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching player headshot:', error);
    return NextResponse.json(
      { detail: 'Failed to fetch player headshot' },
      { status: 500 }
    );
  }
}
