"use client";

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { format, parseISO, subDays, addDays, isToday } from 'date-fns';
import { Button } from "@/components/ui/button";
import { ChevronLeftIcon, ChevronRightIcon, Loader2, AlertCircleIcon, CalendarOffIcon } from "lucide-react";
import { ScoreboardData, Game } from "./types";
import { PlayByPlayModal } from "@/components/games/PlayByPlayModal";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import { GameCard } from "@/components/games/GameCard";
import { useScoreboardWebSocket } from '@/lib/hooks/useScoreboardWebSocket';
import { useHistoricalScoreboardData } from '@/lib/hooks/useHistoricalScoreboardData';

// Constants
const GAME_CARD_STAGGER_DELAY_MS = 75;

interface GamesClientPageProps {
  searchParams: { [key: string]: string | string[] | undefined };
  initialScoreboardData: ScoreboardData | null;
  serverFetchError: string | null;
}

export default function GamesClientPage({ searchParams }: GamesClientPageProps) {
  const router = useRouter();

  // --- Combined State Management (Primary states from hooks) ---
  const [liveScoreboardData, setLiveScoreboardData] = useState<ScoreboardData | null>(null);
  const [isWsConnected, setIsWsConnected] = useState<boolean>(false);
  const [wsError, setWsError] = useState<string | null>(null);
  const [isWsLoading, setIsWsLoading] = useState<boolean>(false); // For initial WS connection attempt

  // --- Date Logic ---
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
  const formattedDateUrl = viewingToday ? null : format(currentDate, 'yyyy-MM-dd'); // null if today

  // --- Hooks for Data Fetching ---
  useScoreboardWebSocket({
    viewingToday,
    onDataReceived: setLiveScoreboardData,
    onLoadingChange: setIsWsLoading,
    onErrorChange: setWsError,
    onConnectionChange: setIsWsConnected,
  });

  const { 
    data: historicalScoreboardData, 
    isLoading: isHistoricalLoading, 
    error: historicalError,
  } = useHistoricalScoreboardData({
    dateToFetch: formattedDateUrl, // Pass null if viewingToday, hook will not fetch
    viewingToday,
  });
  
  // --- Derived State (Decide which data source, loading, and error to use) ---
  const scoreboardData = viewingToday ? liveScoreboardData : historicalScoreboardData;
  const isLoading = viewingToday ? isWsLoading : isHistoricalLoading;
  const error = viewingToday ? wsError : historicalError;

  // PBP Modal State
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [isPbpModalOpen, setIsPbpModalOpen] = useState<boolean>(false);
  
  // --- Initial state setting for WS when viewing today ---
  useEffect(() => {
    if (viewingToday) {
      // Clear historical data if switching to today
      // The useHistoricalScoreboardData hook already handles clearing its data when viewingToday becomes true.
      // Set live data to null initially until WS connects or sends data
      setLiveScoreboardData(null); 
      setIsWsLoading(true); // Assume loading until WS connects
      setWsError(null);
    }
    // No explicit else needed here, useHistoricalScoreboardData handles non-today cases
  }, [viewingToday]);

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
     if (viewingToday && !isWsConnected && !error) return "Connecting to live scores...";
     if (isLoading) return "Loading Games..."; // Generic loading for historical or initial WS
     return ""; // Should not be called if not loading
   };

  return (
    <div className={cn("space-y-6", { "opacity-50 pointer-events-none": isLoading && !scoreboardData })}>
      {/* Date Navigation Header */}
      <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
         <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-center sm:text-left">NBA Games</h1>
         <div className="flex items-center gap-2">
           <Button variant="outline" size="icon" onClick={handlePrevDay} disabled={isLoading}>
             <ChevronLeftIcon className="h-4 w-4" />
             <span className="sr-only">Previous Day</span>
           </Button>
           <span className="text-lg font-medium text-center w-64 sm:w-auto">{displayDate}</span>
           <Button variant="outline" size="icon" onClick={handleNextDay} disabled={isLoading}>
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
                {viewingToday && isWsConnected ? "Waiting for live games data..." :
                 viewingToday && !isWsConnected && !isWsLoading ? "Could not connect to live feed." : // More specific message
                 !viewingToday ? "No games scheduled for this date." : 
                 "Connecting..." // Fallback while WS might still be connecting initially
                }
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