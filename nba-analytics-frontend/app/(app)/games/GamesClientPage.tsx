"use client";

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { format, parseISO, subDays, addDays, isToday } from 'date-fns';
import { Button } from "@/components/ui/button";
import { ChevronLeftIcon, ChevronRightIcon, Loader2, AlertCircleIcon, CalendarOffIcon } from "lucide-react";
import { ScoreboardData, Game } from "./types";
import { PlayByPlayModal } from "@/components/games/PlayByPlayModal";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import { API_BASE_URL } from '@/lib/config';
import { GameCard } from "@/components/games/GameCard";

// Constants
const GAME_CARD_STAGGER_DELAY_MS = 75;

interface GamesClientPageProps {
  searchParams: { [key: string]: string | string[] | undefined };
  // These props are no longer used as client handles fetching/state
  initialScoreboardData: ScoreboardData | null; 
  serverFetchError: string | null; 
}

export default function GamesClientPage({ searchParams }: GamesClientPageProps) {
  const router = useRouter();

  // --- State Management ---
  const [scoreboardData, setScoreboardData] = useState<ScoreboardData | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const ws = useRef<WebSocket | null>(null);
  const scoreCache = useRef<Record<string, ScoreboardData>>({}); // Client-side cache

  // PBP Modal State
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [isPbpModalOpen, setIsPbpModalOpen] = useState<boolean>(false);

  // --- Date Logic (Client-Side) ---
  const dateParam = searchParams?.date;
  let targetDate: Date;
  if (typeof dateParam === 'string' && /\d{4}-\d{2}-\d{2}/.test(dateParam)) {
    try { targetDate = parseISO(dateParam); } catch { targetDate = new Date(); }
  } else {
    targetDate = new Date();
  }
  const currentDate = targetDate;
  const viewingToday = isToday(currentDate);
  const displayDate = format(currentDate, 'PPPP');
  const formattedDateUrl = format(currentDate, 'yyyy-MM-dd');

  // --- Data Fetching Logic (Client-Side for non-today) ---
  const fetchInitialData = useCallback(async (dateToFetch: string) => {
    // Check client cache first
    if (scoreCache.current[dateToFetch]) {
      console.log(`[Client Cache] Cache hit for ${dateToFetch}`);
      setScoreboardData(scoreCache.current[dateToFetch]);
      setIsLoading(false);
      setError(null);
      return; // Exit if cache hit
    }

    // Not in cache, fetch from backend
    setIsLoading(true);
    setError(null);
    // setScoreboardData(null); // << Avoid clearing data for smoother transition
    try {
      const apiUrl = `${API_BASE_URL}/scoreboard/?game_date=${dateToFetch}`;
      console.log(`[Client Fetch] Cache miss. Fetching initial data for ${dateToFetch}`);
      const res = await fetch(apiUrl);
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: `HTTP error! status: ${res.status}` }));
        throw new Error(errorData.detail || `Failed to fetch scoreboard: ${res.statusText}`);
      }
      const data: ScoreboardData = await res.json();
      if (data && typeof data === 'object' && Array.isArray(data.games)) {
        setScoreboardData(data);
        scoreCache.current[dateToFetch] = data; // Store in client cache
      } else {
        console.warn("[Client Fetch] Invalid data structure received:", data);
        // Set to empty games on invalid structure, keep error state null for now?
        setScoreboardData({ gameDate: dateToFetch, games: [] }); 
        // throw new Error("Received invalid data structure from server."); // Maybe don't throw, just show empty
      }
    } catch (err: unknown) {
      console.error("[Client Fetch] Error fetching initial scoreboard:", err);
      const errorMessage = err instanceof Error ? err.message : "Could not load games.";
      setError(errorMessage);
      // Set empty games on fetch error
      setScoreboardData({ gameDate: dateToFetch, games: [] }); 
    } finally {
      setIsLoading(false);
    }
  }, [API_BASE_URL]); // Dependency: API_BASE_URL

  // --- Effects ---

  // Effect to handle initial data load or WebSocket setup based on date
  useEffect(() => {
    setError(null); 
    if (viewingToday) {
      console.log("[Effect] Viewing today. Will attempt WebSocket connection.");
      setIsLoading(true); 
      setScoreboardData(null); 
      // WS connection handled by the next effect
    } else {
      console.log(`[Effect] Viewing past/future date (${formattedDateUrl}). Fetching initial data.`);
      fetchInitialData(formattedDateUrl);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewingToday, formattedDateUrl, fetchInitialData]); // Rerun when date changes

  // WebSocket connection logic
  useEffect(() => {
    if (!viewingToday) {
      if (ws.current) {
        console.log("[WebSocket Effect] Navigated off today, closing connection.");
        ws.current.close(1000, "Navigated off today");
        ws.current = null;
        setIsConnected(false);
      }
      return; 
    }

    if (!ws.current) {
      const wsBaseUrl = API_BASE_URL.replace(/^http(s?):/, 'ws:'); 
      const wsUrl = `${wsBaseUrl}/scoreboard/ws`; 

      console.log("[WebSocket Effect] Attempting to connect to:", wsUrl);
      const socket = new WebSocket(wsUrl);
      ws.current = socket;

      socket.onopen = () => {
        console.log("[WebSocket] Connection established");
        setIsConnected(true);
        setError(null); 
        setIsLoading(false); 
      };

      socket.onclose = (event) => {
        console.log(`[WebSocket] Connection closed: ${event.code} - ${event.reason}`);
        if (ws.current === socket) { 
            ws.current = null;
            setIsConnected(false);
            if (viewingToday && event.code !== 1000 && event.code !== 1005) { 
                 setError("WebSocket connection lost.");
                 setIsLoading(false); 
            }
        }
      };

      socket.onerror = (ev) => {
        console.error("[WebSocket] Error:", ev);
        if (ws.current === socket) {
            setError("WebSocket connection error.");
            setIsConnected(false);
            setIsLoading(false); 
            ws.current = null; 
        }
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && typeof data === 'object' && Array.isArray(data.games)) {
            setScoreboardData(data); 
            setError(null); 
            setIsLoading(false); 
          } else {
            console.warn("[WebSocket] Received invalid data structure:", data);
          }
        } catch (parseError) {
          console.error("[WebSocket] Failed to parse message data:", parseError, "Raw:", event.data);
        }
      };
    }
    
    // Cleanup function
    return () => {
      if (ws.current && ws.current.readyState === WebSocket.OPEN) {
        console.log("[WebSocket Effect Cleanup] Closing connection");
        ws.current.close(1000, "Client cleanup"); 
      }
    };
  }, [viewingToday, API_BASE_URL]); 

  // --- Event Handlers ---
  const handlePrevDay = () => {
    const prevDate = subDays(currentDate, 1);
    router.push(`/games?date=${format(prevDate, 'yyyy-MM-dd')}`);
  };
  const handleNextDay = () => {
    const nextDate = addDays(currentDate, 1);
    router.push(`/games?date=${format(nextDate, 'yyyy-MM-dd')}`);
  };
  const handleOpenPbp = (gameId: string) => {
    setSelectedGameId(gameId);
    setIsPbpModalOpen(true);
  };
  
  // --- Render Logic ---
  const renderLoadingMessage = () => {
     if (viewingToday && !isConnected && !error) return "Connecting to live scores...";
     return "Loading Games..."; 
   };

  return (
    <div className="space-y-6">
      {/* Date Navigation Header */}
      <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
         <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-center sm:text-left">NBA Games</h1>
         <div className="flex items-center gap-2">
           <Button variant="outline" size="icon" onClick={handlePrevDay}>
             <ChevronLeftIcon className="h-4 w-4" />
             <span className="sr-only">Previous Day</span>
           </Button>
           <span className="text-lg font-medium text-center w-64 sm:w-auto">{displayDate}</span>
           <Button variant="outline" size="icon" onClick={handleNextDay}>
             <ChevronRightIcon className="h-4 w-4" />
             <span className="sr-only">Next Day</span>
           </Button>
         </div>
       </div>

      {/* Loading State */}
      {isLoading && (
        <div className="flex justify-center items-center pt-10">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <span className="ml-2 text-muted-foreground">{renderLoadingMessage()}</span>
        </div>
      )}

      {/* Error State */}
      {!isLoading && error && (
        <Alert variant="destructive" className="my-4">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error Loading Games</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Game Cards Display */}
      {!isLoading && !error && scoreboardData && (
        <>
          {scoreboardData.games.length === 0 ? (
            <div className="text-center text-muted-foreground py-12 flex flex-col items-center justify-center">
              <CalendarOffIcon className="h-12 w-12 mb-4 text-muted-foreground/70" />
              <p className="text-lg">
                {viewingToday && isConnected ? "Waiting for live games data..." :
                 viewingToday && !isConnected ? "Connecting to live feed..." :
                 "No games scheduled for this date."}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {scoreboardData.games.filter(game => !!game?.gameId).map((game: Game, index: number) => ( 
                <div
                  key={game.gameId}
                  className={cn("animate-in fade-in-0 slide-in-from-bottom-4 duration-500")}
                  style={{ animationDelay: `${index * GAME_CARD_STAGGER_DELAY_MS}ms` }}
                >
                  <GameCard
                    game={game}
                    viewingToday={viewingToday}
                    onClick={handleOpenPbp}
                  />
                </div>
              ))}
            </div>
          )}
        </>
      )}
      
      {/* Render PlayByPlayModal */}
      <PlayByPlayModal 
          gameId={selectedGameId}
          isOpen={isPbpModalOpen}
          onOpenChange={setIsPbpModalOpen}
       />

    </div>
  );
}