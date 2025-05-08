// Imports for Server Component
import { Metadata } from 'next';
import { format, parseISO, isToday } from 'date-fns';
import { ScoreboardData } from "./types";
import GamesClientPage from "./GamesClientPage";
import { API_BASE_URL } from "@/lib/config";

// Server-side fetch function
async function getScoreboardDataServer(gameDate: string): Promise<{ data: ScoreboardData | null, error: string | null }> {
  const apiUrl = `${API_BASE_URL}/scoreboard/?game_date=${gameDate}`;
  console.log("[Server] Fetching scoreboard via HTTP:", apiUrl);
  try {
    const res = await fetch(apiUrl, { 
      cache: 'no-store', // Consider caching strategy
    });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ message: `HTTP error! status: ${res.status}` }));
      console.error("[Server] API route error:", errorData);
      return { data: null, error: errorData.message || `Failed to fetch scoreboard: ${res.statusText}` };
    }
    const rawData = await res.json();
    if (!rawData || !rawData.games) {
       console.warn("[Server] Invalid scoreboard data structure received");
       return { data: { gameDate: gameDate, games: [] }, error: null }; // Return empty games array
    }
    rawData.games = Array.isArray(rawData.games) ? rawData.games : [];
    return { data: rawData as ScoreboardData, error: null };

  } catch (err: unknown) {
     console.error("[Server] Failed to fetch scoreboard data:", err);
     const message = err instanceof Error ? err.message : "Could not load games.";
     return { data: null, error: message };
  }
}

const formatDateUrl = (date: Date): string => format(date, 'yyyy-MM-dd');

export const metadata: Metadata = {
  title: 'NBA Games Scoreboard',
  description: 'View live and past NBA game scores and schedules.',
};

interface GamesPageProps {
  searchParams: { [key: string]: string | string[] | undefined }; // Simpler type for searchParams
}

export default async function GamesServerPage({ searchParams }: GamesPageProps) {
  // Determine the target date from search params or default to today
  let targetDate: Date;
  const dateParam = searchParams?.date;

  if (typeof dateParam === 'string' && /\d{4}-\d{2}-\d{2}/.test(dateParam)) {
     try {
        targetDate = parseISO(dateParam);
     } catch {
        targetDate = new Date(); // Default to today on parse error
     }
  } else {
     targetDate = new Date(); // Default to today if param missing/invalid
  }

  const isViewingToday = isToday(targetDate);
  const formattedDate = formatDateUrl(targetDate);

  let initialScoreboardData: ScoreboardData | null = null;
  let serverFetchError: string | null = null;

  // Fetch data server-side ONLY if not viewing today's games
  if (!isViewingToday) {
    console.log(`[Server Page] Fetching data for date: ${formattedDate}`);
    const { data, error } = await getScoreboardDataServer(formattedDate);
    initialScoreboardData = data;
    serverFetchError = error;
  } else {
     console.log("[Server Page] Date is today, client will handle WebSocket.");
     initialScoreboardData = { gameDate: formattedDate, games: [] }; // Provide date structure for client
  }

  return (
    <GamesClientPage
      targetDateISO={targetDate.toISOString()}
      initialScoreboardData={initialScoreboardData}
      serverFetchError={serverFetchError}
    />
  );
}

/*
// ---------------------------------------------------
//  ORIGINAL CLIENT-SIDE LOGIC (To be moved/deleted)
// ---------------------------------------------------

"use client";

import { useState, useEffect, useCallback, useRef } from 'react';
// ... other client imports ...

// Keep interfaces (These should be moved to types.ts)
// interface Team { ... }
// interface Game { ... }
// interface ScoreboardData { ... }
// interface Play { ... }
// interface PbpPeriod { ... }
// interface PbpData { ... }

// Fetch data via HTTP (Keep function signature, maybe move impl to lib/api)
// async function getScoreboardDataHttp(gameDate: string): Promise<ScoreboardData> { ... }

// Helper to format date as YYYY-MM-DD (Can be moved to lib/utils)
// const formatDateUrl = (date: Date): string => format(date, 'yyyy-MM-dd');

export default function GamesPage() { // This whole function body needs to be moved/refactored
  const [currentDate, setCurrentDate] = useState(new Date());
  // ... all state variables ...
  const ws = useRef<WebSocket | null>(null);

  // ... all useEffects ...
  useEffect(() => { // Data fetching effect
    // ... WS/HTTP logic ...
  }, [urlDate, viewingToday]); 

  // ... fetchPbpData function ...
  const fetchPbpData = useCallback(async (gameId: string, isPollingUpdate = false) => {
     // ... PBP fetching logic ...
  }, [pbpData, periodFilter]); // Corrected dependency array

  // ... handleOpenPbp function ...
  const handleOpenPbp = (gameId: string) => { ... };

  // ... PBP Polling useEffect ...
  useEffect(() => {
     // ... polling logic ...
  }, [isPbpModalOpen, selectedGameId, pbpData?.source, fetchPbpData]); // Added fetchPbpData dependency

  // ... handlePrevDay / handleNextDay functions ...
  const handlePrevDay = () => { ... };
  const handleNextDay = () => { ... };

  // ... Render Logic ... (To be moved)
  const renderLoading = () => { ... };
  const getPlayDescription = (play: Play): string => { ... };
  const getPlayTeamIndicator = (play: Play): string => { ... };
  const filteredPlays = useCallback((): Play[] => { ... }, [pbpData, periodFilter]);
  const formatEventType = (eventType: string): string => { ... };
  const getEventTypeIcon = (play: Play): React.ReactNode => { ... };

  return (
    // ... JSX structure to be moved/refactored ...
  );
}

*/