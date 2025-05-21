import { useState, useEffect, useCallback, useRef } from 'react';
import { PbpData } from '@/app/(app)/games/types'; // Adjust path as needed

const LIVE_UPDATE_INTERVAL = 5000; // 5 seconds polling for PBP

interface UsePlayByPlayDataOptions {
  gameId: string | null;
  isOpen: boolean;
  periodFilter: string; // e.g., "all", "q1", "q2"
}

interface UsePlayByPlayDataResult {
  pbpData: PbpData | null;
  isLoading: boolean;
  error: string | null;
  fetchPbpData: (isPollingUpdate?: boolean) => Promise<void>; // Expose for manual refresh if needed
}

export function usePlayByPlayData({
  gameId,
  isOpen,
  periodFilter,
}: UsePlayByPlayDataOptions): UsePlayByPlayDataResult {
  const [pbpData, setPbpData] = useState<PbpData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchPbpData = useCallback(async (isPollingUpdate = false) => {
    if (!gameId) {
        // Clear data if gameId becomes null (e.g. modal closed and reset)
        setPbpData(null);
        setError(null);
        setIsLoading(false); 
        return;
    }

    if (!isPollingUpdate) {
      console.log(`[PBP Hook] Initial fetch for gameId: ${gameId}, period: ${periodFilter}`);
      setIsLoading(true);
      setError(null);
      setPbpData(null); // Clear previous game's PBP data on new gameId/period
    } else {
      console.log(`[PBP Hook] Polling PBP for gameId: ${gameId}, period: ${periodFilter}`);
    }

    try {
      let apiUrl = `/api/v1/game/playbyplay/${gameId}`;
      const periodNum = periodFilter !== "all" ? parseInt(periodFilter.replace("q", "")) : 0;
      if (periodNum > 0) {
        apiUrl += `?start_period=${periodNum}&end_period=${periodNum}`;
      }

      const response = await fetch(apiUrl, { method: 'GET', cache: 'no-store' });
      const rawResponseText = await response.text();

      if (!response.ok) {
        let errorDetail = `HTTP error! status: ${response.status}`;
        try {
          const errorData = JSON.parse(rawResponseText);
          errorDetail = errorData.detail || errorDetail;
        } catch { /* ignore parse error */ }
        throw new Error(errorDetail);
      }

      const data = JSON.parse(rawResponseText);
      if (data.game_id && data.periods) {
        const newData = data as PbpData;
        setPbpData(newData);
        if (error && !isPollingUpdate) setError(null); // Clear initial error on successful fetch
        else if (error && isPollingUpdate && newData.source !== 'live') setError(null); // Clear polling error if game ended
      } else {
        throw new Error("Invalid PBP data structure");
      }
    } catch (err: unknown) {
      console.error("[PBP Hook] Failed PBP fetch:", err);
      const message = err instanceof Error ? err.message : "Could not load play-by-play.";
      if (!isPollingUpdate || !error) { // Set error on initial or if polling fails without prior error
        setError(message);
      }
    } finally {
      if (!isPollingUpdate) setIsLoading(false);
    }
  }, [gameId, periodFilter, error]); // Include error to allow clearing it

  // Effect to fetch data when gameId, isOpen, or periodFilter changes
  useEffect(() => {
    if (isOpen && gameId) {
      fetchPbpData(false); // Initial fetch for the current gameId and periodFilter
    } else {
      // Clear state when modal closes or gameId is null
      setPbpData(null);
      setError(null);
      setIsLoading(false);
      // periodFilter is managed by the component using the hook
    }
  }, [isOpen, gameId, periodFilter, fetchPbpData]); // periodFilter added as a dependency

  // Effect for live polling
  useEffect(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }

    if (isOpen && gameId && pbpData?.source === 'live' && !error && periodFilter === 'all') {
      console.log(`[PBP Hook] Starting polling for live game: ${gameId} (all periods)`);
      pollingIntervalRef.current = setInterval(() => {
        fetchPbpData(true); // Polling update
      }, LIVE_UPDATE_INTERVAL);
    } else if (pbpData?.source !== 'live' && pollingIntervalRef.current) {
        console.log(`[PBP Hook] Game ${gameId} is no longer live or polling conditions not met. Stopping polling.`);
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
    }

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [isOpen, gameId, pbpData?.source, periodFilter, fetchPbpData, error]); // error added to stop polling on error

  return { pbpData, isLoading, error, fetchPbpData };
} 