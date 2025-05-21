import { useState, useEffect, useRef, useCallback } from 'react';
import { Suggestion } from "@/app/(app)/players/types"; // Adjust path as necessary
import { API_BASE_URL } from "@/lib/config";

const MIN_SEARCH_LENGTH = 2;
const DEBOUNCE_DELAY_MS = 300;
const SUGGESTION_LIMIT = 7;

interface UsePlayerSearchSuggestionsResult {
  suggestions: Suggestion[];
  isLoading: boolean;
  error: string | null;
  fetchSuggestions: (query: string) => void;
  clearSuggestions: () => void;
}

export function usePlayerSearchSuggestions(): UsePlayerSearchSuggestionsResult {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceTimer = useRef<NodeJS.Timeout | null>(null);

  const clearSuggestions = useCallback(() => {
    setSuggestions([]);
    setError(null);
    setIsLoading(false);
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
  }, []);

  const fetchSuggestions = useCallback((query: string) => {
    const trimmedQuery = query.trim();
    if (debounceTimer.current) clearTimeout(debounceTimer.current);

    if (trimmedQuery.length < MIN_SEARCH_LENGTH) {
      clearSuggestions();
      return;
    }

    setIsLoading(true);
    setError(null);

    debounceTimer.current = setTimeout(async () => {
      console.log(`[usePlayerSearchSuggestions] Debounced suggestion search for: ${trimmedQuery}`);
      try {
        const suggestionsUrl = `${API_BASE_URL}/player/search?q=${encodeURIComponent(trimmedQuery)}&limit=${SUGGESTION_LIMIT}`;
        const response = await fetch(suggestionsUrl);
        if (!response.ok) {
          throw new Error(`Failed to fetch suggestions (${response.status})`);
        }
        const data: Suggestion[] = await response.json();
        setSuggestions(data);
        setError(null); // Clear previous errors on success
      } catch (err) {
        console.error("[usePlayerSearchSuggestions] Failed to fetch suggestions:", err);
        setError(err instanceof Error ? err.message : "Could not fetch suggestions.");
        setSuggestions([]); // Clear suggestions on error
      } finally {
        setIsLoading(false);
      }
    }, DEBOUNCE_DELAY_MS);
  }, [clearSuggestions]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, []);

  return { suggestions, isLoading, error, fetchSuggestions, clearSuggestions };
} 