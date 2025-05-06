"use client";

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { format, parseISO, subDays, addDays, isToday } from 'date-fns';
import { Button } from "@/components/ui/button";
import { ChevronLeftIcon, ChevronRightIcon, Loader2, AlertCircleIcon, CalendarOffIcon } from "lucide-react"; // Added AlertCircleIcon, CalendarOffIcon
import { ScoreboardData } from "./types";
import { GameCard } from "@/components/games/GameCard";
import { PlayByPlayModal } from "@/components/games/PlayByPlayModal";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"; // Added Alert components
import { cn } from "@/lib/utils"; // Added cn

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
  const [isLoading, setIsLoading] = useState(true); // Make isLoading stateful
  const [error, setError] = useState<string | null>(null); // Make error stateful
  const ws = useRef<WebSocket | null>(null);

  // Effect to manage isLoading state based on data availability
  useEffect(() => {
    if (viewingToday) {
      // For today, loading is complete when live data is received or error occurs
      setIsLoading(!liveScoreboardData && !error);
    } else {
      // For past dates, loading is complete when initial data is available or error occurs
      setIsLoading(!initialScoreboardData && !error);
    }
    console.log(`[GamesClientPage] isLoading: ${isLoading}, viewingToday: ${viewingToday}, liveData: ${!!liveScoreboardData}, initialData: ${!!initialScoreboardData}, error: ${!!error}`); // Log loading state changes
  }, [isLoading, viewingToday, liveScoreboardData, initialScoreboardData, error]); // Add dependencies

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
      const wsUrl = `${protocol}//${window.location.host}/api/v1/scoreboard/ws`;
      ws.current = new WebSocket(wsUrl);
      ws.current.onopen = () => {
        console.log("[WebSocket] Connection established");
        setIsConnected(true);
      };
      ws.current.onclose = (event) => {
        console.log(`[WebSocket] Connection closed: ${event.code} - ${event.reason}`);
        setIsConnected(false);
      };
      ws.current.onerror = (error) => {
        console.error("[WebSocket] Error:", error);
        setError("WebSocket connection error. Please try refreshing the page.");
        setIsConnected(false);
      };
      ws.current.onmessage = (event) => {
        console.log("[WebSocket] Message received:", event.data); // Log raw data
        try {
          const data = JSON.parse(event.data);
          console.log("[WebSocket] Parsed data:", data); // Log parsed data
          if (data && data.games) {
            console.log("[WebSocket] Setting live scoreboard data:", data.games.length, "games"); // Log data being set
            setLiveScoreboardData(data);
          } else {
            console.warn("[WebSocket] Received data without 'games' property or invalid format:", data); // Warn if data is unexpected
          }
        } catch (parseError) {
          console.error("[WebSocket] Failed to parse message data:", parseError, "Raw data:", event.data); // Log parsing errors
        }
      };
    }
    return () => {
      // Only close if the WebSocket is open or connecting
      if (ws.current && (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING)) {
        console.log("[WebSocket] Cleaning up: Closing connection");
        ws.current.close();
      }
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

 // Log data source changes
 useEffect(() => {
   console.log(`[GamesClientPage] Data source updated. Viewing today: ${viewingToday}. Data available: ${!!currentScoreboardData}. Games count: ${currentScoreboardData?.games?.length}`);
 }, [currentScoreboardData, viewingToday]);

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
        <Alert variant="destructive" className="my-4">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error Loading Games</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Game Cards Display */}
      {!isLoading && !error && currentScoreboardData && (
        <>
          {currentScoreboardData.games.length === 0 ? (
            <div className="text-center text-muted-foreground py-12 flex flex-col items-center justify-center">
              <CalendarOffIcon className="h-12 w-12 mb-4 text-muted-foreground/70" />
              <p className="text-lg">
                {viewingToday && isConnected ? "Waiting for live games data..." :
                 viewingToday && !isConnected ? "Connecting to live feed..." :
                 "No games scheduled for this date."}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"> {/* Adjusted grid for potentially more cards */}
              {currentScoreboardData.games.filter(game => !!game?.gameId).map((game, index) => ( // Added index
                <div
                  key={game.gameId}
                  className={cn("animate-in fade-in-0 slide-in-from-bottom-4 duration-500")}
                  style={{ animationDelay: `${index * 75}ms` }}
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