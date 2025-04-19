"use client";

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { format, parseISO, subDays, addDays, isToday } from 'date-fns';
import { Button } from "@/components/ui/button";
import { ChevronLeftIcon, ChevronRightIcon, Loader2 } from "lucide-react";
import { ScoreboardData } from "./types";
// Import the new components
import { GameCard } from "@/components/games/GameCard";
import { PlayByPlayModal } from "@/components/games/PlayByPlayModal";

interface GamesClientPageProps {
  targetDateISO: string;
  initialScoreboardData: ScoreboardData | null;
}

export default function GamesClientPage({
  targetDateISO,
  initialScoreboardData,
}: GamesClientPageProps) {
  const router = useRouter();
  const currentDate = parseISO(targetDateISO);
  const viewingToday = isToday(currentDate);
  const displayDate = format(currentDate, 'PPPP');

  // State for live data (if viewing today)
  const [liveScoreboardData, setLiveScoreboardData] = useState<ScoreboardData | null>(viewingToday ? null : initialScoreboardData); // Start null if today, use initial otherwise
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isLoading] = useState(true);
  const [error] = useState<string | null>(null);
  const ws = useRef<WebSocket | null>(null);

  // PBP Modal State
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [isPbpModalOpen, setIsPbpModalOpen] = useState<boolean>(false);

   // WebSocket connection logic (remains largely the same)
  useEffect(() => {
    // WebSocket connection logic (as before)
    if (!viewingToday) {
      ws.current?.close();
      ws.current = null;
      setIsConnected(false);
      return;
    }

    if (!ws.current) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/games/scoreboard/ws`;
      ws.current = new WebSocket(wsUrl);
      ws.current.onopen = () => setIsConnected(true);
      ws.current.onclose = () => setIsConnected(false);
      ws.current.onerror = () => setIsConnected(false);
      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.games) {
            setLiveScoreboardData(data);
          }
        } catch {
          // ignore
        }
      };
    }
    return () => {
      ws.current?.close();
      ws.current = null;
      setIsConnected(false);
    };
  }, [viewingToday]);

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