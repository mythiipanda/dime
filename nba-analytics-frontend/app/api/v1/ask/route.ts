import { NextRequest } from 'next/server';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const prompt = searchParams.get('prompt');

  if (!prompt) {
    return new Response('Missing prompt parameter', { status: 400 });
  }

  try {
    // Forward the request to the backend SSE endpoint
    const backendUrl = `${process.env.BACKEND_URL || 'http://localhost:8000'}/api/v1/ask?prompt=${encodeURIComponent(prompt)}`;

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
    console.error('Error forwarding to backend:', error);
    return new Response('Internal server error', { status: 500 });
  }
}
