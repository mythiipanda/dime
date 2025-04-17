import { type NextRequest, NextResponse } from 'next/server';

interface Standing {
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
}

interface StandingsData {
  standings: Standing[];
}

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const season = searchParams.get('season');
  const backendBaseUrl = process.env.BACKEND_API_URL || 'http://localhost:8000';
  let url = `${backendBaseUrl}/api/v1/standings`;
  if (season) {
    url += `?season=${season}`;
  }

  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store'
    });
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({ detail: res.statusText }));
      return NextResponse.json(errorData, { status: res.status });
    }
    const data: StandingsData = await res.json();
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ message: error.message }, { status: 500 });
  }
}

export const dynamic = 'force-dynamic';
