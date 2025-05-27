import { NextRequest } from 'next/server';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);

  // Handle both direct parameters and prompt parameter (from useAgentChatSSE)
  let teamName = searchParams.get('team_name');
  let season = searchParams.get('season') || '2024-25';

  // If no team_name but there's a prompt parameter, parse it
  if (!teamName) {
    const prompt = searchParams.get('prompt');
    if (prompt) {
      // Parse the prompt parameter which contains team_name=...&season=...
      const promptParams = new URLSearchParams(prompt);
      teamName = promptParams.get('team_name');
      season = promptParams.get('season') || '2024-25';
    }
  }

  if (!teamName) {
    return new Response('Missing team_name parameter', { status: 400 });
  }

  try {
    // Forward the request to the backend summer strategy SSE endpoint
    const backendUrl = `${process.env.BACKEND_URL || 'http://localhost:8000'}/api/v1/summer-strategy?team_name=${encodeURIComponent(teamName)}&season=${encodeURIComponent(season)}`;

    const response = await fetch(backendUrl, {
      method: 'GET',
      headers: {
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
    });

    if (!response.ok) {
      throw new Error(`Backend responded with status: ${response.status}`);
    }

    // Return the SSE stream directly
    return new Response(response.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    });
  } catch (error) {
    console.error('Error forwarding summer strategy request to backend:', error);
    return new Response('Internal server error', { status: 500 });
  }
}
