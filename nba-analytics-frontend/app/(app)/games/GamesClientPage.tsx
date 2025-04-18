"use client";

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { format, parseISO, addDays, subDays, isToday } from 'date-fns';
import { ScoreboardData, Game } from "./types";
import { Button } from "@/components/ui/button";
import { ChevronLeftIcon, ChevronRightIcon, Loader2 } from "lucide-react";
// Import the new components
import { GameCard } from "@/components/games/GameCard";
import { PlayByPlayModal } from "@/components/games/PlayByPlayModal";

interface GamesClientPageProps {
  targetDateISO: string;
  initialScoreboardData: ScoreboardData | null;
  serverFetchError: string | null;
}

export default function GamesClientPage({
  targetDateISO,
  initialScoreboardData,
  serverFetchError,
}: GamesClientPageProps) {
  const router = useRouter();
  const currentDate = parseISO(targetDateISO);
  const viewingToday = isToday(currentDate);
  const displayDate = format(currentDate, 'PPPP');

  // State for live data (if viewing today)
  const [liveScoreboardData, setLiveScoreboardData] = useState<ScoreboardData | null>(viewingToday ? null : initialScoreboardData); // Start null if today, use initial otherwise
  const [isConnected, setIsConnected] = useState<boolean>(false);
  // Loading is true if viewing today and not connected OR if not today and no initial data/error
  const [isLoading, setIsLoading] = useState(
    (viewingToday && !isConnected) || 
    (!viewingToday && !initialScoreboardData && !serverFetchError)
  );
  const [error, setError] = useState<string | null>(serverFetchError);
  const ws = useRef<WebSocket | null>(null);

  // PBP Modal State
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [isPbpModalOpen, setIsPbpModalOpen] = useState<boolean>(false);

   // WebSocket connection logic (remains largely the same)
   useEffect(() => {
      if (!viewingToday) {
         ws.current?.close();
         ws.current = null;
         setIsConnected(false);
         // When navigating TO a non-today date, use initial server data
         setLiveScoreboardData(initialScoreboardData); 
         setError(serverFetchError);
         setIsLoading(!initialScoreboardData && !serverFetchError); // Set loading based on server data for non-today
         return;
      }
      
      console.log("[Client] Connecting WebSocket...");
      setError(null);
      setIsLoading(true); // Always set loading true when attempting WS connection
      setIsConnected(false); 

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/v1/live/scoreboard/ws`;
      const socket = new WebSocket(wsUrl);
      ws.current = socket;
      let connectionEstablished = false;

      socket.onopen = () => { 
         console.log("[Client] WebSocket connected");
         connectionEstablished = true;
         setIsConnected(true);
         setError(null);
         // Don't set loading false yet, wait for first message
      };
      socket.onclose = () => { 
         console.log(`[Client] WebSocket disconnected - Established: ${connectionEstablished}`);
         ws.current = null;
         setIsConnected(false);
         // Only show error if we actually connected or never received data
         if (connectionEstablished || !liveScoreboardData) { 
             setError("Live connection lost. Please refresh.");
         }
         setIsLoading(false); // Stop loading on close
      };
      socket.onerror = (event) => { 
         console.error("[Client] WebSocket error:", event);
         ws.current = null;
         setError("WebSocket connection error.");
         setIsLoading(false);
         setIsConnected(false);
      };
      socket.onmessage = (event) => { 
         try {
           const data = JSON.parse(event.data);
           if (data && data.games && Array.isArray(data.games)) {
             setLiveScoreboardData(data as ScoreboardData);
             setError(null); 
             setIsLoading(false); // Stop loading once data arrives
           } else {
             console.warn("[Client] Received non-scoreboard WS data:", data);
           }
         } catch (e) {
           console.error("[Client] Failed to parse WS message:", e);
           setIsLoading(false); // Stop loading even on parse error
           setError("Error processing live data.");
         }
      };

      return () => {
         console.log("[Client] Cleaning up WebSocket.");
         socket.close();
         ws.current = null;
         setIsConnected(false); 
      };
   // Depend also on initial data/error in case server render failed for non-today
   }, [viewingToday, targetDateISO, initialScoreboardData, serverFetchError]);

  // Navigation handlers (remain the same)
  const handlePrevDay = () => {
    const prevDate = subDays(currentDate, 1);
    router.push(`/games?date=${format(prevDate, 'yyyy-MM-dd')}`);
  };
  const handleNextDay = () => {
    const nextDate = addDays(currentDate, 1);
    router.push(`/games?date=${format(nextDate, 'yyyy-MM-dd')}`);
  };

  // PBP Modal handler (remains the same)
  const handleOpenPbp = (gameId: string) => {
    setSelectedGameId(gameId);
    setIsPbpModalOpen(true);
  };
  
  // Loading message render function (remains the same)
  const renderLoading = () => {
     if (viewingToday) {
       if (!isConnected && !error) return "Connecting to live scores...";
       // If connected but no data yet (first message pending)
       if (isConnected && !liveScoreboardData && !error) return "Waiting for live scores..."; 
     }
     // Fallback for non-today initial load or WS connecting phase
     return "Loading Games...";
   };

  // Determine current data source
  const currentScoreboardData = viewingToday ? liveScoreboardData : initialScoreboardData;

  return (
    <div className="space-y-6">
      {/* Date Navigation Header (remains the same) */}
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
          <span className="ml-2 text-muted-foreground">{renderLoading()}</span>
        </div>
      )}

      {/* Error State */}
      {error && !isLoading && (
        <div className="text-center text-red-600 dark:text-red-400 pt-10">
          <p>Error: {error}</p>
           {/* Optionally add a refresh button for WS errors? */}
        </div>
      )}

      {/* Game Cards Display */}
      {!isLoading && !error && currentScoreboardData && (
        <>
          {currentScoreboardData.games.length === 0 ? (
            <p className="text-center text-muted-foreground pt-10">
              {viewingToday && isConnected ? "Waiting for live games data..." : 
               viewingToday && !isConnected ? "Connecting to live feed..." : // Show connecting if WS hasn't opened yet
               "No games scheduled for this date."}
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {/* Use GameCard component */}
              {currentScoreboardData.games.filter(game => !!game?.gameId).map((game) => (
                <GameCard 
                  key={game.gameId} 
                  game={game} 
                  viewingToday={viewingToday} 
                  onClick={handleOpenPbp} 
                />
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