import { useState, useEffect, useCallback, useRef } from 'react';
import { ScoreboardData } from '@/app/(app)/games/types';
import { API_BASE_URL } from '@/lib/config';

interface UseHistoricalScoreboardDataOptions {
  dateToFetch: string | null; // formattedDateUrl (yyyy-MM-dd), or null if not fetching
  viewingToday: boolean; // To prevent fetching if it's today (WS handles today)
}

interface HistoricalScoreboardDataResult {
  data: ScoreboardData | null;
  isLoading: boolean;
  error: string | null;
  fetchData: (date: string) => Promise<void>; // Allow manual refetch if needed
}

const scoreCache = new Map<string, ScoreboardData>(); // Module-level cache (persists across hook instances for same dates)

export function useHistoricalScoreboardData({
  dateToFetch,
  viewingToday,
}: UseHistoricalScoreboardDataOptions): HistoricalScoreboardDataResult {
  const [data, setData] = useState<ScoreboardData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async (currentDateToFetch: string) => {
    if (viewingToday) {
        // Should not be called if viewing today, but as a safeguard:
        setData(null); 
        setError(null);
        setIsLoading(false);
        return;
    }

    if (scoreCache.has(currentDateToFetch)) {
      console.log(`[Hist. Hook Cache] Cache hit for ${currentDateToFetch}`);
      setData(scoreCache.get(currentDateToFetch)!);
      setIsLoading(false);
      setError(null);
      return;
    }

    console.log(`[Hist. Hook] Cache miss. Fetching data for ${currentDateToFetch}`);
    setIsLoading(true);
    setError(null);
    // setData(null); // Avoid clearing previous data for smoother UX on date change

    try {
      const apiUrl = `${API_BASE_URL}/scoreboard/?game_date=${currentDateToFetch}`;
      const res = await fetch(apiUrl, { cache: 'no-store' }); // 'no-store' for fetch, but we have our own cache

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: `HTTP error! status: ${res.status}` }));
        throw new Error(errorData.detail || `Failed to fetch scoreboard: ${res.statusText}`);
      }
      const fetchedData: ScoreboardData = await res.json();
      if (fetchedData && typeof fetchedData === 'object' && Array.isArray(fetchedData.games)) {
        setData(fetchedData);
        scoreCache.set(currentDateToFetch, fetchedData);
      } else {
        console.warn("[Hist. Hook] Invalid data structure received:", fetchedData);
        setData({ gameDate: currentDateToFetch, games: [] });
        // Consider setting an error here: setError("Received invalid data structure from server.");
      }
    } catch (err: unknown) {
      console.error("[Hist. Hook] Error fetching scoreboard:", err);
      const errorMessage = err instanceof Error ? err.message : "Could not load games.";
      setError(errorMessage);
      setData({ gameDate: currentDateToFetch, games: [] }); // Set empty games on error
    } finally {
      setIsLoading(false);
    }
  }, [viewingToday, API_BASE_URL]); // API_BASE_URL is a dependency

  useEffect(() => {
    if (dateToFetch && !viewingToday) {
        // Reset states before fetching new date if it's different from current data's date
        if (data && data.gameDate !== dateToFetch) {
            setData(null);
            setError(null); 
            // setIsLoading(true); // fetchData will set this
        }
        fetchData(dateToFetch);
    } else if (viewingToday) {
        // If switching to today, clear historical data as WS will take over
        setData(null);
        setError(null);
        setIsLoading(false); // WS will handle its own loading state
    }
  }, [dateToFetch, viewingToday, fetchData, data]); // data is needed to compare gameDate

  return { data, isLoading, error, fetchData };
} 