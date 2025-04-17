"use client";

import { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronLeftIcon, ChevronRightIcon, Loader2, XIcon, Target, AlertTriangle, Timer, ArrowLeftRight, Info, XCircle } from "lucide-react";
import { format, parseISO, addDays, subDays, isToday } from 'date-fns';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogClose,
  DialogDescription,
  DialogFooter
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Terminal } from "lucide-react";

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

// Interface for Play-by-Play data based on backend logic
interface Play {
  event_num: number;
  clock: string;
  score?: string | null;
  margin?: string | null;
  team: "home" | "away" | "neutral";
  home_description?: string | null;
  away_description?: string | null;
  neutral_description?: string | null;
  event_type: string;
}

interface PbpPeriod {
  period: number;
  plays: Play[];
}

interface PbpData {
  game_id: string;
  has_video: boolean;
  filtered_periods?: { start: number; end: number } | null;
  periods: PbpPeriod[];
  source: 'live' | 'historical';
}

// Fetch data via HTTP (for non-today dates)
async function getScoreboardDataHttp(gameDate: string): Promise<ScoreboardData> {
  let apiUrl = `/api/games/scoreboard?game_date=${gameDate}`;
  console.log("Fetching scoreboard via HTTP:", apiUrl);
  const res = await fetch(apiUrl, { cache: 'no-store' });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ message: `HTTP error! status: ${res.status}` }));
    console.error("API route error:", errorData);
    throw new Error(errorData.message || `Failed to fetch scoreboard: ${res.statusText}`);
  }
  const data = await res.json();
  if (!data.games) {
      data.games = [];
  }
  return data as ScoreboardData;
}

// Helper to format date as YYYY-MM-DD
const formatDateUrl = (date: Date): string => format(date, 'yyyy-MM-dd');

export default function GamesPage() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [scoreboardData, setScoreboardData] = useState<ScoreboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false); // WebSocket state
  const ws = useRef<WebSocket | null>(null); // WebSocket ref

  // Play-by-Play Modal State
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [isPbpModalOpen, setIsPbpModalOpen] = useState<boolean>(false);
  const [pbpData, setPbpData] = useState<PbpData | null>(null);
  const [isPbpLoading, setIsPbpLoading] = useState<boolean>(false);
  const [pbpError, setPbpError] = useState<string | null>(null);
  const [periodFilter, setPeriodFilter] = useState<string>("all"); // "all", "q1", "q2", etc.

  // Define polling interval constant
  const LIVE_UPDATE_INTERVAL = 3000; // 3 seconds

  const displayDate = format(currentDate, 'PPPP');
  const urlDate = formatDateUrl(currentDate);
  const viewingToday = isToday(currentDate);

  // Effect for handling data fetching (HTTP or WebSocket) based on date
  useEffect(() => {
    let isMounted = true; // Flag to prevent state updates on unmounted component
    setError(null);
    setIsLoading(true);
    setIsConnected(false); // Reset connection status on date change
    setScoreboardData(null); // Clear previous data

    // Clean up previous WebSocket connection if it exists
    if (ws.current) {
        console.log("Closing previous WebSocket connection due to date change.");
        ws.current.close();
        ws.current = null;
    }

    if (viewingToday) {
      // --- WebSocket Logic for Today ---
      console.log("Setting up WebSocket for today's scores.");
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/v1/live/scoreboard/ws`;
      
      console.log(`Attempting to connect WebSocket: ${wsUrl}`);
      const currentWs = new WebSocket(wsUrl);
      ws.current = currentWs; // Assign to ref

      currentWs.onopen = () => {
        if (!isMounted) return;
        console.log("WebSocket connected");
        setIsConnected(true);
        setError(null); 
        // Keep loading until first message arrives
      };

      currentWs.onclose = () => {
        if (!isMounted) return;
        console.log("WebSocket disconnected");
        setIsConnected(false);
        // Only show loading/error if we never got data initially
        if (!scoreboardData) {
           setIsLoading(true); 
           setError("WebSocket disconnected. Please refresh or check back."); 
        }
      };

      currentWs.onerror = (event) => {
        if (!isMounted) return;
        console.error("WebSocket error:", event);
        setError("WebSocket connection error.");
        setIsLoading(false);
        setIsConnected(false);
        ws.current = null; // Clear ref on error
      };

      currentWs.onmessage = (event) => {
         if (!isMounted) return;
         try {
           const data: ScoreboardData = JSON.parse(event.data);
           // Log the received data structure for inspection
           console.log("Received data via WebSocket:", JSON.stringify(data, null, 2));
           
           if (data && data.games && Array.isArray(data.games)) {
             setScoreboardData(data);
    setError(null);
             if (isLoading) {
                console.log("Setting isLoading to false"); // Check if this logs
                setIsLoading(false); 
             }
             console.log("Scoreboard state updated via WebSocket"); // Renamed log for clarity
           } else {
             console.warn("Received invalid data format from WebSocket:", event.data);
           }
         } catch (e) {
           console.error("Failed to parse WebSocket message:", e);
         }
      };

    } else {
      // --- HTTP Fetch Logic for Past/Future Dates ---
      console.log(`Fetching scores via HTTP for non-today date: ${urlDate}`);
      getScoreboardDataHttp(urlDate)
        .then(data => {
          if (isMounted) {
            setScoreboardData(data);
            setIsLoading(false);
          }
        })
        .catch(err => {
          if (isMounted) {
            console.error("Failed to load scoreboard data via HTTP:", err);
            setError(err.message || "Could not load games.");
            setIsLoading(false);
          }
        });
    }

    // Cleanup function
    return () => {
      isMounted = false;
      if (ws.current) {
        console.log("Closing WebSocket connection on cleanup.");
        ws.current.close();
        ws.current = null;
      }
    };
  // Rerun effect when the date changes
  }, [urlDate, viewingToday]); 

  // Function to fetch Play-by-Play data
  const fetchPbpData = useCallback(async (gameId: string, isPollingUpdate = false) => {
    if (!gameId) return;
    if (!isPollingUpdate) {
        console.log(`Fetching PBP for gameId: ${gameId}`);
        setIsPbpLoading(true);
        setPbpError(null);
        setPbpData(null); // Clear previous PBP data on initial load
    } else {
        console.log(`Polling PBP for gameId: ${gameId}`);
    }

    try {
      const response = await fetch(`/api/v1/games/playbyplay`, { 
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          target: "playbyplay", 
          params: { game_id: gameId }
        }),
        cache: 'no-store', 
      });
      
      // Log raw response text first
      const rawResponseText = await response.text();
      console.log("Raw PBP Response:", rawResponseText);

      if (!response.ok) {
        let errorDetail = `HTTP error! status: ${response.status}`;
        try {
          const errorData = JSON.parse(rawResponseText); // Try parsing error from raw text
          errorDetail = errorData.detail || errorDetail;
        } catch (parseError) {
          console.error("Could not parse error response:", parseError);
          // Use raw text if JSON parsing fails
          if (rawResponseText.length < 500) { // Avoid logging huge HTML errors
            errorDetail = rawResponseText || errorDetail;
          }
        }
        console.error("PBP API route error:", errorDetail);
        if (!isPollingUpdate) setPbpError(errorDetail);
        else console.warn("PBP polling update failed:", errorDetail);
        return; 
      }
      
      // Now parse the successful response
      const data = JSON.parse(rawResponseText);

      if (data.result && data.result.periods) {
        const newData = data.result as PbpData;

        if (isPollingUpdate && pbpData) {
          console.log("Merging polled PBP data...");
          const mergedData: PbpData = {
            ...newData, 
            periods: [], 
          };

          const existingPeriodsMap = new Map(pbpData.periods.map(p => [p.period, p]));
          const existingEventNums = new Set<number>();
          pbpData.periods.forEach(p => p.plays.forEach(play => existingEventNums.add(play.event_num)));
          console.log(`Existing event numbers (${existingEventNums.size}):`, Array.from(existingEventNums).slice(-10)); // Log last 10 existing event nums

          newData.periods.forEach(newPeriod => {
            const existingPeriod = existingPeriodsMap.get(newPeriod.period);
            if (existingPeriod) {
              const newPlays = newPeriod.plays.filter(play => !existingEventNums.has(play.event_num));
              if (newPlays.length > 0) {
                 console.log(`Found ${newPlays.length} new plays for period ${newPeriod.period}`);
                 console.log("New play event_nums:", newPlays.map(p => p.event_num));
                 mergedData.periods.push({
                   ...existingPeriod, 
                   plays: [...existingPeriod.plays, ...newPlays] // Append new plays
                 });
              } else {
                console.log(`No new plays found for period ${newPeriod.period}`);
                  mergedData.periods.push(existingPeriod);
              }
            } else {
              console.log(`Adding new period ${newPeriod.period}`);
              mergedData.periods.push(newPeriod);
            }
          });

          mergedData.periods.sort((a, b) => a.period - b.period);
          console.log("Final merged data structure (periods):", mergedData.periods.map(p => ({ period: p.period, playCount: p.plays.length })));
          setPbpData(mergedData);

        } else {
          // --- Initial load or no previous data --- 
          setPbpData(newData);
        }

        // Clear error only on successful fetch (initial or polling)
        setPbpError(null); 
        if (!isPollingUpdate) console.log("PBP data fetched successfully:", data.result);
      } else {
        console.error("Invalid PBP data structure received:", data);
        // Keep previous data on polling error?
        if (!isPollingUpdate) setPbpError("Received invalid PBP data structure.");
      }
    } catch (err: any) {
      console.error("Failed to load PBP data:", err);
      // Keep previous data on polling error?
      if (!isPollingUpdate) setPbpError(err.message || "Could not load play-by-play.");
    } finally {
       // Only stop initial loading indicator
      if (!isPollingUpdate) {
          setIsPbpLoading(false);
      }
    }
  }, []);

  // Handler for opening the PBP modal
  const handleOpenPbp = (gameId: string) => {
    setSelectedGameId(gameId);
    setIsPbpModalOpen(true);
    fetchPbpData(gameId, false); // Initial fetch (not polling)
  };

  // Effect for PBP Polling
  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null;

    if (isPbpModalOpen && selectedGameId && pbpData?.source === 'live') {
      console.log(`Starting PBP polling for live game: ${selectedGameId}`);
      intervalId = setInterval(() => {
        fetchPbpData(selectedGameId, true); // Pass true for polling update
      }, LIVE_UPDATE_INTERVAL);
    }

    // Cleanup function: clear interval when modal closes, game changes, or data source changes
    return () => {
      if (intervalId) {
        console.log(`Stopping PBP polling for game: ${selectedGameId}`);
        clearInterval(intervalId);
      }
    };
  // Dependencies: only run when modal state, selected game, or initial pbpData source changes
  }, [isPbpModalOpen, selectedGameId, pbpData?.source]);

  const handlePrevDay = () => {
    setCurrentDate(prev => subDays(prev, 1));
  };

  const handleNextDay = () => {
    setCurrentDate(prev => addDays(prev, 1));
  };

  // --- Render Logic ---
  const renderLoading = () => {
    if (viewingToday) {
      if (!isConnected && !error) return "Connecting to live scores...";
      if (isConnected && !scoreboardData && !error) return "Waiting for live scores...";
    }
    return "Loading Games..."; // Default for HTTP or initial WS load
  };

  // Helper to get description from a play
  const getPlayDescription = (play: Play): string => {
      return play.home_description || play.away_description || play.neutral_description || "Play description unavailable";
  }
  
  // Helper to get team color/indicator based on play
  const getPlayTeamIndicator = (play: Play): string => {
      if (play.team === 'home') return 'border-l-4 border-blue-500 pl-2'; // Example: Blue border for home
      if (play.team === 'away') return 'border-l-4 border-red-500 pl-2'; // Example: Red border for away
      return 'pl-3'; // Neutral plays
  }

  // Helper function to filter PBP actions based on the selected period
  const filteredPlays = useCallback((): Play[] => {
    if (!pbpData || !pbpData.periods) return [];
    let combinedPlays: Play[] = [];
    if (periodFilter === "all") {
      combinedPlays = pbpData.periods.reduce((allPlays, currentPeriod) => {
         return allPlays.concat(currentPeriod.plays || []);
      }, [] as Play[]);
    } else {
      const periodNumber = parseInt(periodFilter.replace("q", ""));
      const period = pbpData.periods.find(p => p.period === periodNumber);
      combinedPlays = period ? (period.plays || []) : [];
    }
    // Ensure plays are sorted chronologically by event_num
    return combinedPlays.sort((a, b) => a.event_num - b.event_num);
  }, [pbpData, periodFilter]);

  // Helper to format event type string
  const formatEventType = (eventType: string): string => {
    return eventType
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ')
      .replace('2pt', '2PT')
      .replace('3pt', '3PT')
      .replace('Of', 'of'); // Keep 'of' lowercase for free throws
  }

  // Helper to get an icon based on event type
  const getEventTypeIcon = (play: Play): React.ReactNode => {
    const eventType = play.event_type;
    // Check for scoring plays first
    if (eventType.includes('PT_') || eventType.includes('FREETHROW')) {
      // Check description for MISS
      if (getPlayDescription(play).toUpperCase().startsWith('MISS')) {
        return <XCircle className="h-4 w-4 mr-2 inline-block text-muted-foreground" />; // Muted icon for miss
      } else {
        return <Target className="h-4 w-4 mr-2 inline-block text-orange-500" />; // Target icon for make
      }
    }
    if (eventType.includes('FOUL') || eventType.includes('VIOLATION')) return <AlertTriangle className="h-4 w-4 mr-2 inline-block text-red-500" />;
    if (eventType.includes('TIMEOUT') || eventType.includes('PERIOD')) return <Timer className="h-4 w-4 mr-2 inline-block text-blue-500" />;
    if (eventType.includes('TURNOVER') || eventType.includes('SUBSTITUTION') || eventType.includes('STEAL') || eventType.includes('JUMPBALL')) return <ArrowLeftRight className="h-4 w-4 mr-2 inline-block text-purple-500" />;
    // Add more specific icons as needed (e.g., for rebounds, blocks)
    return <Info className="h-4 w-4 mr-2 inline-block text-gray-500" />; // Default icon
  }

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
          <span className="ml-2 text-muted-foreground">{renderLoading()}</span>
        </div>
      )}
      
      {error && !isLoading && (
         <div className="text-center text-red-600 dark:text-red-400 pt-10">
           <p>Error: {error}</p>
           {/* Optional: Add retry logic specific to HTTP/WS if needed */}
           {/* <Button onClick={fetchData} variant="outline" className="mt-4">Retry</Button> */}
         </div>
       )}

      {!isLoading && !error && scoreboardData && (
        <>
         {scoreboardData.games.length === 0 ? (
            <p className="text-center text-muted-foreground pt-10">
              {viewingToday ? "No live games currently or waiting for data." : "No games scheduled for this date."}
            </p>
         ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {scoreboardData.games.filter(game => game && game.gameId).map((game) => (
                <Card 
                  key={game.gameId} 
                  className="cursor-pointer hover:shadow-lg transition-shadow duration-200"
                  onClick={() => handleOpenPbp(game.gameId)}
                >
                  <CardHeader className={`flex flex-row items-center justify-between space-y-0 pb-2 ${game.gameStatus === 2 && viewingToday ? 'bg-green-50 dark:bg-green-900/20' : ''}`}>
                    <CardTitle className="text-sm font-medium">
                      {game.awayTeam?.teamTricode || 'N/A'} @ {game.homeTeam?.teamTricode || 'N/A'}
                    </CardTitle>
                    <span 
                      className={`whitespace-nowrap px-2 py-0.5 rounded text-xs font-semibold ${
                        game.gameStatus === 1 ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' : 
                        // Make live game pulse only if viewing today
                        (game.gameStatus === 2 && viewingToday) ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 animate-pulse' : 
                        game.gameStatus === 2 ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' : // Non-pulsing green for historical live games
                        'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200' // Final/Scheduled
                      }`}
                    >
                      {game.gameStatusText}
                    </span>
                  </CardHeader>
                  <CardContent className="pt-2"> 
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

      {/* Play-by-Play Modal */}
      <Dialog open={isPbpModalOpen} onOpenChange={setIsPbpModalOpen}>
        <DialogContent className="sm:max-w-[80vw] max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>Play-by-Play</DialogTitle>
            <DialogDescription>
              {pbpData?.game_id ? `Game ID: ${pbpData.game_id} - Source: ${pbpData.source}` : 'Loading game details...'}
              {isPbpLoading && pbpData?.source === 'live' && " (Updating...)"}
            </DialogDescription>
          </DialogHeader>
          {isPbpLoading && !pbpData ? ( // Show loading indicator only on initial load
            <div className="flex justify-center items-center h-64">
              <p>Loading Play-by-Play...</p>
            </div>
          ) : pbpError ? (
             <Alert variant="destructive">
                <Terminal className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>{pbpError}</AlertDescription>
              </Alert>
          ) : pbpData ? (
            <div className="flex-grow overflow-y-auto pr-2"> {/* Make content scrollable */}
              {/* Period Filter */}
               {pbpData.periods && pbpData.periods.length > 0 && (
                 <div className="mb-4 flex items-center gap-2">
                    <Label htmlFor="period-filter">Filter Period:</Label>
                    <Select value={periodFilter} onValueChange={setPeriodFilter}>
                       <SelectTrigger id="period-filter" className="w-[180px]">
                         <SelectValue placeholder="Select period" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Periods</SelectItem>
                        {pbpData.periods
                           .sort((a, b) => a.period - b.period) // Ensure periods are sorted
                           .map((p) => (
                          <SelectItem key={p.period} value={`q${p.period}`}>
                            Period {p.period}
                          </SelectItem>
                         ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
              {/* PBP Table -> Changed to List Format */}
              <div className="space-y-2 text-sm">
                {/* Header Row (Optional, but helps define columns) */}
                <div className="flex items-center font-semibold text-muted-foreground px-2 py-1 sticky top-0 bg-background z-10 border-b">
                  <div className="w-16 shrink-0">Time</div>
                  <div className="w-20 shrink-0">Score</div>
                  <div className="w-48 shrink-0">Action</div>
                  <div className="flex-grow min-w-0">Description</div>
                </div>

                {/* Play List */} 
                {filteredPlays().length > 0 ? (
                  filteredPlays().map((play: Play, index: number) => (
                    <div 
                      key={play.event_num} 
                      className={`flex items-start gap-2 px-2 py-2 rounded-md ${index % 2 === 0 ? "bg-muted/30" : ""}`}
                    >
                      <div className="w-16 shrink-0 font-mono pt-0.5">{play.clock}</div>
                      <div className="w-20 shrink-0 font-medium pt-0.5 whitespace-nowrap">{play.score || "-"}</div>
                      <div className="w-48 shrink-0">
                        <span className="flex items-center text-xs bg-secondary px-2 py-1 rounded">
                          {getEventTypeIcon(play)}
                          {formatEventType(play.event_type)}
                        </span>
                      </div>
                      <div className="flex-grow min-w-0 pt-0.5 text-muted-foreground">{getPlayDescription(play)}</div>
                    </div>
                  ))
                ) : (
                  <div className="text-center p-4 text-muted-foreground">No actions for the selected period.</div>
                )}
              </div>
            </div>
          ) : (
            <p>No Play-by-Play data available.</p> // Fallback if no data and no error
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsPbpModalOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}