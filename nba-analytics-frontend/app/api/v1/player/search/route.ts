import { NextRequest, NextResponse } from 'next/server';
import { API_BASE_URL } from '@/lib/config';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const query = searchParams.get('q');
  const limit = searchParams.get('limit') || '10';
  
  if (!query) {
    return NextResponse.json(
      { detail: 'Search query is required' },
      { status: 400 }
    );
  }

  try {
    const searchUrl = `${API_BASE_URL}/player/search?q=${encodeURIComponent(query)}&limit=${limit}`;
    
    const response = await fetch(searchUrl, {
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: `HTTP error ${response.status}` }));
      console.error(`Player search failed (${response.status}):`, errorData);
      return NextResponse.json(
        { detail: errorData.detail || `Failed to search players (${response.status})` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error searching players:', error);
    return NextResponse.json(
      { detail: 'Failed to search players' },
      { status: 500 }
    );
  }
}
