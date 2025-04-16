"use client";

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronLeftIcon, ChevronRightIcon, Loader2 } from "lucide-react";
import { format, parseISO, addDays, subDays } from 'date-fns';

// Keep interfaces
interface Team {
  teamId: number;
  teamTricode: string;
  score: number;
  wins?: number;
  losses?: number;
}

interface Game {
  gameId: string;
  gameStatus: number;
  gameStatusText: string;
  period?: number;
  gameClock?: string;
  homeTeam: Team;
  awayTeam: Team;
  gameEt: string;
}

interface ScoreboardData {
  gameDate: string;
  games: Game[];
}

// Renamed function to reflect its purpose
async function getScoreboardData(gameDate: string | null): Promise<ScoreboardData> {
  // Construct the API URL, adding game_date if provided
  let apiUrl = `/api/games/scoreboard`; 
  if (gameDate) {
    apiUrl += `?game_date=${gameDate}`;
  }
  
  console.log("Fetching scoreboard from frontend API:", apiUrl);
  const res = await fetch(apiUrl, {
    cache: 'no-store', // Ensure fresh data 
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ message: `HTTP error! status: ${res.status}` }));
    console.error("API route error:", errorData);
    throw new Error(errorData.message || `Failed to fetch scoreboard: ${res.statusText}`);
  }
  const data = await res.json();
  // Ensure games is always an array, even if backend returns null/undefined somehow
  if (!data.games) {
      data.games = [];
  }
  return data as ScoreboardData;
}

// Helper to format date as YYYY-MM-DD
const formatDateUrl = (date: Date): string => format(date, 'yyyy-MM-dd');

export default function GamesPage() {
  // State for the currently displayed date (defaults to today)
  const [currentDate, setCurrentDate] = useState(new Date());
  const [scoreboardData, setScoreboardData] = useState<ScoreboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Format date for display
  const displayDate = format(currentDate, 'PPPP'); // e.g., Tuesday, July 30th, 2024
  const urlDate = formatDateUrl(currentDate);

  // Fetch data when date changes
  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    console.log(`Requesting data for date: ${urlDate}`);
    try {
      const data = await getScoreboardData(urlDate);
      setScoreboardData(data);
    } catch (err: any) {
      console.error("Failed to load scoreboard data:", err);
      setError(err.message || "Could not load games.");
      setScoreboardData(null); // Clear old data on error
    } finally {
      setIsLoading(false);
    }
  }, [urlDate]); // Depend on the formatted URL date

  useEffect(() => {
    fetchData();
  }, [fetchData]); // Trigger fetch when fetchData (due to urlDate change) updates

  const handlePrevDay = () => {
    setCurrentDate(prev => subDays(prev, 1));
  };

  const handleNextDay = () => {
    setCurrentDate(prev => addDays(prev, 1));
  };

  return (
    <div className="space-y-6">
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

      {isLoading && (
        <div className="flex justify-center items-center pt-10">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <span className="ml-2 text-muted-foreground">Loading Games...</span>
        </div>
      )}
      
      {error && (
         <div className="text-center text-red-600 dark:text-red-400 pt-10">
           <p>Error loading games: {error}</p>
           <Button onClick={fetchData} variant="outline" className="mt-4">Retry</Button>
         </div>
       )}

      {!isLoading && !error && scoreboardData && (
        <>
         {scoreboardData.games.length === 0 ? (
            <p className="text-center text-muted-foreground pt-10">No games scheduled for this date.</p>
         ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {scoreboardData.games.map((game) => (
                <Card key={game.gameId}>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">
                      {game.awayTeam?.teamTricode || 'N/A'} @ {game.homeTeam?.teamTricode || 'N/A'}
                    </CardTitle>
                    <span 
                      className={`whitespace-nowrap px-2 py-0.5 rounded text-xs font-semibold ${
                        game.gameStatus === 1 ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' : 
                        game.gameStatus === 2 ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 animate-pulse' : 
                        'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200' 
                      }`}
                    >
                      {game.gameStatusText}
                    </span>
                  </CardHeader>
                  <CardContent>
                    {/* Added checks for potentially null team data from ScoreboardV2 transformation */} 
                    <div className="flex justify-between items-center mb-2">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 bg-muted rounded-full flex items-center justify-center text-xs">{game.awayTeam?.teamTricode || '?'}</div>
                        <span className="font-semibold">{game.awayTeam?.teamTricode || 'N/A'}</span>
                        {game.awayTeam?.wins !== undefined && game.awayTeam?.losses !== undefined && (
                            <span className="text-xs text-muted-foreground">({game.awayTeam.wins}-{game.awayTeam.losses})</span>
                        )}
                      </div>
                      <div className="text-xl font-bold">{game.gameStatus === 1 ? '-' : (game.awayTeam?.score ?? '-')}</div>
                    </div>
                    <div className="flex justify-between items-center">
                       <div className="flex items-center gap-2">
                        <div className="w-6 h-6 bg-muted rounded-full flex items-center justify-center text-xs">{game.homeTeam?.teamTricode || '?'}</div>
                        <span className="font-semibold">{game.homeTeam?.teamTricode || 'N/A'}</span>
                         {game.homeTeam?.wins !== undefined && game.homeTeam?.losses !== undefined && (
                            <span className="text-xs text-muted-foreground">({game.homeTeam.wins}-{game.homeTeam.losses})</span>
                         )}
                      </div>
                       <div className="text-xl font-bold">{game.gameStatus === 1 ? '-' : (game.homeTeam?.score ?? '-')}</div>
                    </div>
                    {game.gameStatus === 1 && game.gameEt && (
                       <div className="text-center text-xs text-muted-foreground mt-2">
                         {/* Attempt to parse and format time, fallback if format is unexpected */}
                         {(() => {
                            try {
                              // Assuming gameEt is like '2024-07-28T19:00:00Z' or similar ISO string from V2
                              return format(parseISO(game.gameEt), 'p zzz'); 
                            } catch { 
                              // Fallback if gameEt isn't a parsable ISO string (e.g., just time like "7:00 PM ET")
                              return game.gameEt;
                            }
                          })()}
                       </div>
                     )}
                      {game.gameStatus === 2 && game.gameClock && (
                         <div className="text-center text-xs text-muted-foreground mt-2">
                           {game.period && `Q${game.period} `}{game.gameClock}
                         </div>
                     )}
                  </CardContent>
                </Card>
              ))}
            </div>
         )}
        </>
      )}
    </div>
  );
}