const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

interface APIError {
  detail: string;
  code?: number;
}

/**
 * Wrapper for fetch calls to our API
 */
export async function fetchFromAPI<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      cache: 'no-store', // Disable caching
    });

    if (!response.ok) {
      const errorData: APIError = await response.json();
      throw new Error(errorData.detail || `API Error: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('API Request Failed:', error);
    throw error instanceof Error ? error : new Error('Failed to fetch data');
  }
}