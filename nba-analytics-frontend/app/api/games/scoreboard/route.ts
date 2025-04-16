import { type NextRequest, NextResponse } from 'next/server'

// Re-use or redefine types if needed
interface Team {
  teamId: number;
  teamTricode: string;
  score: number;
  wins?: number;
  losses?: number;
}

interface Game {
  gameId: string;
  gameStatus: number;
  gameStatusText: string;
  period?: number;
  gameClock?: string;
  homeTeam: Team;
  awayTeam: Team;
  gameEt: string;
}

interface ScoreboardData {
  gameDate: string;
  games: Game[];
}

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const game_date = searchParams.get('game_date'); // YYYY-MM-DD or null

  // Construct backend URL
  const backendBaseUrl = process.env.BACKEND_API_URL || 'http://localhost:8000';
  // Use the updated backend endpoint /api/v1/scoreboard/
  let scoreboardUrl = `${backendBaseUrl}/api/v1/scoreboard/`;

  // Append query parameter if date is provided
  if (game_date) {
    // Optional: Validate date format here too if desired
    scoreboardUrl += `?game_date=${game_date}`;
  }

  try {
    console.log(`Fetching scoreboard data from backend: ${scoreboardUrl}`);
    const res = await fetch(scoreboardUrl, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store', // Revalidate frequently, especially for today
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({ detail: res.statusText }));
      console.error(`Backend error fetching scoreboard: ${res.status} ${res.statusText}`, errorData);
      // Propagate status code from backend error if possible
      throw new Error(`Failed to fetch scoreboard from backend: ${errorData.detail || res.statusText}`, { cause: { status: res.status } });
    }

    const data: ScoreboardData = await res.json();
    console.log(`Successfully fetched scoreboard data for ${game_date || 'today'} from backend.`);
    return NextResponse.json(data);

  } catch (error: any) {
    console.error('Error fetching scoreboard data:', error);
    const status = error.cause?.status || (error.message.includes("Invalid date format") ? 400 : 500);
    return NextResponse.json(
      { message: error.message || 'Failed to fetch scoreboard data' }, 
      { status: status }
    );
  }
}

// Ensure route is dynamically evaluated, especially for today's data
export const dynamic = 'force-dynamic'; 