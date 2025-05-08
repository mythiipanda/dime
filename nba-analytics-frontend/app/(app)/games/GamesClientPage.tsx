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

// Constants
const GAME_CARD_STAGGER_DELAY_MS = 75;

interface GamesClientPageProps {
  targetDateISO: string;
  initialScoreboardData: ScoreboardData | null;
  serverFetchError: string | null; // Add serverFetchError prop
}

export default function GamesClientPage({
  targetDateISO,
  initialScoreboardData,
  serverFetchError, // Receive serverFetchError
}: GamesClientPageProps) {
  const router = useRouter();
  const currentDate = parseISO(targetDateISO);
  const viewingToday = isToday(currentDate);
  const displayDate = format(currentDate, 'PPPP');

  // State for live data (if viewing today)
  const [liveScoreboardData, setLiveScoreboardData] = useState<ScoreboardData | null>(viewingToday ? null : initialScoreboardData); // Start null if today, use initial otherwise
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(serverFetchError); // Initialize internal error with server error
  const [isLoading, setIsLoading] = useState(!error && !initialScoreboardData); // Initial loading state based on props
  const ws = useRef<WebSocket | null>(null);

  // Effect to derive loading state (more robustly handles initial load vs live updates)
  useEffect(() => {
    if (viewingToday) {
        // Today: Loading = not connected AND no data yet AND no error
        setIsLoading(!isConnected && !liveScoreboardData && !error);
    } else {
        // Past Date: Loading = no initial data AND no error
        setIsLoading(!initialScoreboardData && !error);
    }
  }, [viewingToday, isConnected, liveScoreboardData, initialScoreboardData, error]);

  // PBP Modal State
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [isPbpModalOpen, setIsPbpModalOpen] = useState<boolean>(false);

   // WebSocket connection logic
  useEffect(() => {
    if (!viewingToday) {
      // Ensure WS is closed if navigating away from today
      if (ws.current) {
        console.log("[WebSocket] Navigated off today, closing connection.");
        ws.current.close();
        ws.current = null;
        setIsConnected(false);
      }
      return;
    }

    if (!ws.current) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/v1/scoreboard/ws`;
      console.log("[WebSocket] Attempting to connect to:", wsUrl);
      ws.current = new WebSocket(wsUrl);
      
      ws.current.onopen = () => {
        console.log("[WebSocket] Connection established");
        setIsConnected(true);
        setError(null); // Clear previous errors on successful connect
      };
      ws.current.onclose = (event) => {
        console.log(`[WebSocket] Connection closed: ${event.code} - ${event.reason}`);
        setIsConnected(false);
        // Avoid setting error if closed cleanly or already errored
        if (event.code !== 1000 && event.code !== 1005 && !error) {
             setError("WebSocket connection closed unexpectedly. Try refreshing.");
        }
      };
      ws.current.onerror = (ev) => {
        console.error("[WebSocket] Error:", ev);
        setError("WebSocket connection error. Please try refreshing the page.");
        setIsConnected(false);
      };
      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.games) {
            setLiveScoreboardData(data);
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
      if (ws.current && (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING)) {
        console.log("[WebSocket] Component unmount: Closing connection");
        ws.current.close(1000, "Client navigating away"); // Close cleanly
      }
      ws.current = null; // Ensure ref is cleared
      setIsConnected(false); // Ensure connected state is false
    };
  // Rerun only if viewingToday changes (e.g., navigating between today and past dates)
  // eslint-disable-next-line react-hooks/exhaustive-deps 
  }, [viewingToday]); // Dependency array refined

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
  const renderLoadingMessage = () => {
     if (viewingToday) {
       if (!isConnected && !error) return "Connecting to live scores...";
       if (isConnected && !liveScoreboardData && !error) return "Waiting for live scores...";
     }
     return "Loading Games..."; // Fallback for past dates or initial WS connection
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