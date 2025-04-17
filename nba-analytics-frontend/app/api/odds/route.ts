import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const backendBaseUrl = process.env.BACKEND_API_URL || 'http://localhost:8000';
  try {
    const res = await fetch(`${backendBaseUrl}/api/v1/odds`, { cache: 'no-store' });
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({ detail: res.statusText }));
      console.error(`Backend error fetching odds: ${res.status} ${res.statusText}`, errorData);
      return NextResponse.json(errorData, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error: unknown) {
    console.error('Error fetching odds data:', error);
    const message = error instanceof Error ? error.message : 'An unknown error occurred';
    return NextResponse.json({ message }, { status: 500 });
  }
}

export const dynamic = 'force-dynamic';
