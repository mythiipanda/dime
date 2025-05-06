import { API_BASE_URL } from "@/lib/config"; // Import from config

interface APIError {
  detail: string;
  code?: number;
}

// Define type for fetch options including cache
type FetchOptions = RequestInit & { cache?: RequestCache };

/**
 * Wrapper for fetch calls to our API
 */
export async function fetchFromAPI<T>(
  endpoint: string,
  options: FetchOptions = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  // Allow Next.js default fetch caching / revalidation by not defaulting to 'no-store'
  // Only apply cache option if explicitly provided
  const { cache: explicitCacheOption, ...restOptions } = options;
  
  const headers = {
    'Content-Type': 'application/json',
    ...restOptions.headers,
  };

  const fetchConfig: RequestInit = {
    ...restOptions,
    headers,
  };

  if (explicitCacheOption !== undefined) {
    fetchConfig.cache = explicitCacheOption;
  }

  console.debug(`[fetchFromAPI] Fetching: ${url}`, { cache: fetchConfig.cache, method: restOptions.method || 'GET' });

  try {
    const response = await fetch(url, fetchConfig);

    if (!response.ok) {
      let errorDetail = `API Error: ${response.status} ${response.statusText}`;
      try {
        const errorData: APIError = await response.json();
        errorDetail = errorData.detail || errorDetail;
      } catch {
        // If response is not JSON, use status text
        console.warn(`[fetchFromAPI] Non-JSON error response for ${url}: ${response.status}`);
      }
      console.error(`[fetchFromAPI] Error fetching ${url}: ${errorDetail}`);
      throw new Error(errorDetail);
    }

    // Handle cases where response might be empty (e.g., 204 No Content)
    if (response.status === 204) {
      return null as T; // Or handle as appropriate for the expected type T
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`[fetchFromAPI] Request Failed for ${url}:`, error);
    // Re-throw the specific error caught or a generic one
    throw error instanceof Error ? error : new Error('An unknown error occurred during API request');
  }
}