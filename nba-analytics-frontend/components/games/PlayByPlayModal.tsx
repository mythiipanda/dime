"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { PbpData, Play } from "@/app/(app)/games/types"; // Adjust path as needed
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription,
  DialogFooter
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Terminal, XCircle, Target, AlertTriangle, Info, Loader2 } from "lucide-react"; // Import necessary icons
import { cn } from "@/lib/utils"; // Import cn

interface PlayByPlayModalProps {
  gameId: string | null;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}

const LIVE_UPDATE_INTERVAL = 5000; // 5 seconds polling for PBP

export function PlayByPlayModal({ gameId, isOpen, onOpenChange }: PlayByPlayModalProps) {
  const [pbpData, setPbpData] = useState<PbpData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [periodFilter, setPeriodFilter] = useState<string>("all");
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null); // Ref for polling interval

  // Fetch Play-by-Play data
  const fetchPbpData = useCallback(async (currentGameId: string | null, isPollingUpdate = false) => {
     if (!currentGameId) return;
     if (!isPollingUpdate) {
         console.log(`[PBP Modal] Initial fetch for gameId: ${currentGameId}`);
         setIsLoading(true);
         setError(null);
         setPbpData(null);
     } else {
         // Avoid flicker during polling unless error occurs
         // setIsLoading(true); 
         console.log(`[PBP Modal] Polling PBP for gameId: ${currentGameId}`);
     }
 
     try {
       let apiUrl = `/api/v1/game/playbyplay/${currentGameId}`; // Corrected to include /v1 for backend routing
       const periodNum = periodFilter !== "all" ? parseInt(periodFilter.replace("q", "")) : 0;
       if (periodNum > 0) {
           apiUrl += `?start_period=${periodNum}&end_period=${periodNum}`;
       }
       // console.log(`[PBP Modal] Requesting PBP from: ${apiUrl}`); // Optional: reduce logging
 
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
         // TODO: Consider merging logic for polling updates if UI flicker/state loss is an issue
         setPbpData(newData);
         if (error) setError(null); // Clear error on successful fetch (initial or poll)
         // if (!isPollingUpdate) console.log("[PBP Modal] PBP fetched successfully:", newData); // Optional: reduce logging
       } else {
         throw new Error("Invalid PBP data structure");
       }
     } catch (err: unknown) {
       console.error("[PBP Modal] Failed PBP fetch:", err);
       const message = err instanceof Error ? err.message : "Could not load play-by-play.";
       // Only set error on initial load or if polling fails when there wasn't already an error
       if (!isPollingUpdate || !error) {
         setError(message);
       } 
     } finally {
        // Only stop initial loading indicator
        if (!isPollingUpdate) setIsLoading(false);
     }
   }, [periodFilter, error]); // Add error to dependency array to clear it on success

  // Effect to fetch data when gameId or isOpen changes
  useEffect(() => {
    if (isOpen && gameId) {
      fetchPbpData(gameId, false); // Initial fetch
    } else {
      // Clear state when modal closes or gameId is null
      setPbpData(null);
      setError(null);
      setIsLoading(false);
      setPeriodFilter("all");
    }
  }, [isOpen, gameId, fetchPbpData]);

  // Effect for live polling
  useEffect(() => {
     if (pollingIntervalRef.current) {
       clearInterval(pollingIntervalRef.current);
       pollingIntervalRef.current = null;
     }
 
     // Start polling only if modal is open, game is live, and no current error
     if (isOpen && gameId && pbpData?.source === 'live' && !error) {
       console.log(`[PBP Modal] Starting polling for live game: ${gameId}`);
       pollingIntervalRef.current = setInterval(() => {
         fetchPbpData(gameId, true); // Polling update
       }, LIVE_UPDATE_INTERVAL);
     }
 
     // Cleanup interval
     return () => {
       if (pollingIntervalRef.current) {
         // console.log(`[PBP Modal] Stopping polling for game: ${gameId}`); // Optional: reduce logging
         clearInterval(pollingIntervalRef.current);
         pollingIntervalRef.current = null;
       }
     };
   // Re-run when these change, including error state to stop polling on error
   }, [isOpen, gameId, pbpData?.source, fetchPbpData, error]);

  // Helper functions for rendering play details
  const getPlayDescription = (play: Play): string => {
       return play.description || play.home_description || play.away_description || play.neutral_description || "(Description unavailable)";
   }
   
   const formatEventType = (eventType: string): string => {
     return eventType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
   }
 
   const getEventTypeIcon = (play: Play): React.ReactNode => {
     const desc = getPlayDescription(play).toUpperCase();
     if (desc.startsWith('MISS')) return <XCircle className="h-4 w-4 mr-1 text-muted-foreground" />;
     if (play.event_type.includes('PT') || play.event_type.includes('FREE')) return <Target className="h-4 w-4 mr-1 text-yellow-600 dark:text-yellow-500" />;
     if (play.event_type.includes('FOUL')) return <AlertTriangle className="h-4 w-4 mr-1 text-destructive" />;
     return <Info className="h-4 w-4 mr-1 text-muted-foreground" />;
   }

   // Memoized filtered plays list
   const filteredPlaysList = useMemo((): Play[] => {
     if (!pbpData || !pbpData.periods) return [];
     let combinedPlays: Play[] = [];
     if (periodFilter === "all") {
       combinedPlays = pbpData.periods.reduce((acc, p) => acc.concat(p.plays || []), [] as Play[]);
     } else {
       const periodNumber = parseInt(periodFilter.replace("q", ""));
       combinedPlays = pbpData.periods.find(p => p.period === periodNumber)?.plays || [];
     }
     // Sort plays by event number ascending (earliest first)
     return combinedPlays.sort((a, b) => a.event_num - b.event_num); 
   }, [pbpData, periodFilter]); // Use useMemo instead of useCallback for derived data

  if (!isOpen) {
    return null;
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[80vw] max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Play-by-Play</DialogTitle>
          <DialogDescription>
            {pbpData?.game_id ? `Game ID: ${pbpData.game_id} - Source: ${pbpData.source}` : (gameId || 'Loading...')}
            {/* Show updating indicator only during polling, not initial load */}
            {!isLoading && pbpData?.source === 'live' && " (Live)"} 
          </DialogDescription>
        </DialogHeader>
        
        {isLoading ? (
          <div className="flex justify-center items-center h-64">
            <Loader2 className="h-8 w-8 animate-spin mr-2" />
            Loading Play-by-Play...
          </div>
        ) : error ? (
          <Alert variant="destructive">
            <Terminal className="h-4 w-4" />
            <AlertTitle>Error Loading PBP</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : pbpData ? (
          <div className="flex-grow overflow-hidden flex flex-col">
             {pbpData.periods && pbpData.periods.length > 0 && (
                <div className="mb-4 flex items-center gap-2 flex-shrink-0">
                   <Label htmlFor="period-filter" className="whitespace-nowrap">Filter Period:</Label>
                   <Select value={periodFilter} onValueChange={setPeriodFilter}>
                      <SelectTrigger id="period-filter" className="w-[180px]">
                        <SelectValue placeholder="Select period" />
                     </SelectTrigger>
                     <SelectContent>
                       <SelectItem value="all">All Periods</SelectItem>
                       {pbpData.periods
                          .sort((a, b) => a.period - b.period)
                          .map((p) => (
                         <SelectItem key={p.period} value={`q${p.period}`}>
                           Period {p.period}
                         </SelectItem>
                        ))}
                     </SelectContent>
                   </Select>
                 </div>
               )}

            <div className="flex-grow overflow-y-auto pr-2 space-y-2 text-sm scrollbar-thin scrollbar-thumb-muted-foreground/50 hover:scrollbar-thumb-muted-foreground/80 scrollbar-track-transparent scrollbar-thumb-rounded-full">
               <div className="flex items-center font-semibold text-muted-foreground px-2 py-1 sticky top-0 bg-background z-10 border-b">
                 <div className="w-16 shrink-0">Time</div>
                 <div className="w-20 shrink-0">Score</div>
                 <div className="w-32 shrink-0">Action</div>
                 <div className="flex-grow min-w-0">Description</div>
               </div>
               {filteredPlaysList.length > 0 ? (
                 filteredPlaysList.map((play: Play, index: number) => (
                   <div 
                     key={play.event_num} 
                     className={cn("flex items-start gap-2 px-2 py-1.5 rounded-md", index % 2 === 0 ? "bg-muted/30" : "")}
                   >
                     <div className="w-16 shrink-0 font-mono pt-0.5">{play.clock}</div>
                     <div className="w-20 shrink-0 font-medium pt-0.5 whitespace-nowrap">{play.score || "-"}</div>
                     <div className="w-32 shrink-0">
                       <span className="flex items-center text-xs bg-secondary px-2 py-1 rounded-md">
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
          <p className="text-center py-10 text-muted-foreground">No Play-by-Play data available.</p>
        )}

        <DialogFooter className="mt-4 flex-shrink-0">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
} 