"use client";

import { useState, useEffect, useCallback, useRef } from 'react';
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

  // TODO: Move PBP fetching logic here (fetchPbpData)
  const fetchPbpData = useCallback(async (currentGameId: string | null, isPollingUpdate = false) => {
     if (!currentGameId) return;
     if (!isPollingUpdate) {
         console.log(`[PBP Modal] Initial fetch for gameId: ${currentGameId}`);
         setIsLoading(true);
         setError(null);
         setPbpData(null);
     } else {
         console.log(`[PBP Modal] Polling PBP for gameId: ${currentGameId}`);
     }
 
     try {
       let apiUrl = `/api/v1/games/playbyplay/${currentGameId}`;
       const periodNum = periodFilter !== "all" ? parseInt(periodFilter.replace("q", "")) : 0;
       if (periodNum > 0) {
           apiUrl += `?start_period=${periodNum}&end_period=${periodNum}`;
       }
       console.log(`[PBP Modal] Requesting PBP from: ${apiUrl}`);
 
       const response = await fetch(apiUrl, { method: 'GET', cache: 'no-store' });
       const rawResponseText = await response.text();
 
       if (!response.ok) {
         // ... (error handling logic from original page.tsx) ...
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
         // TODO: Implement merge logic for polling updates if needed
         setPbpData(newData);
         setError(null); 
         if (!isPollingUpdate) console.log("[PBP Modal] PBP fetched successfully:", newData);
       } else {
         throw new Error("Invalid PBP data structure");
       }
     } catch (err: unknown) {
       console.error("[PBP Modal] Failed PBP fetch:", err);
       const message = err instanceof Error ? err.message : "Could not load play-by-play.";
       if (!isPollingUpdate) setError(message);
     } finally {
        if (!isPollingUpdate) setIsLoading(false);
     }
   }, [periodFilter]); // Depend on periodFilter

  // Effect to fetch data when gameId or isOpen changes
  useEffect(() => {
    if (isOpen && gameId) {
      fetchPbpData(gameId, false); // Initial fetch
    } else {
      // Clear data when modal closes or gameId is null
      setPbpData(null);
      setError(null);
      setIsLoading(false);
      setPeriodFilter("all");
    }
  }, [isOpen, gameId, fetchPbpData]);

  // TODO: Move PBP polling logic here
  useEffect(() => {
     // Clear existing interval on dependency change
     if (pollingIntervalRef.current) {
       clearInterval(pollingIntervalRef.current);
       pollingIntervalRef.current = null;
     }
 
     if (isOpen && gameId && pbpData?.source === 'live') {
       console.log(`[PBP Modal] Starting polling for live game: ${gameId}`);
       pollingIntervalRef.current = setInterval(() => {
         fetchPbpData(gameId, true); // Polling update
       }, LIVE_UPDATE_INTERVAL);
     }
 
     // Cleanup: clear interval when component unmounts or dependencies change
     return () => {
       if (pollingIntervalRef.current) {
         console.log(`[PBP Modal] Stopping polling for game: ${gameId}`);
         clearInterval(pollingIntervalRef.current);
         pollingIntervalRef.current = null;
       }
     };
   }, [isOpen, gameId, pbpData?.source, fetchPbpData]); // Re-run when these change

  // TODO: Move PBP helper functions (getPlayDescription, etc.) here or to utils
  const getPlayDescription = (play: Play): string => {
       return play.home_description || play.away_description || play.neutral_description || "(Description unavailable)";
   }
   
   const formatEventType = (eventType: string): string => {
      // Basic formatting, can be enhanced
     return eventType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
   }
 
   const getEventTypeIcon = (play: Play): React.ReactNode => {
     // Simplified icon logic
     const desc = getPlayDescription(play).toUpperCase();
     if (desc.startsWith('MISS')) return <XCircle className="h-4 w-4 mr-1 text-muted-foreground" />;
     if (play.event_type.includes('PT') || play.event_type.includes('FREE')) return <Target className="h-4 w-4 mr-1 text-orange-500" />;
     if (play.event_type.includes('FOUL')) return <AlertTriangle className="h-4 w-4 mr-1 text-red-500" />;
     return <Info className="h-4 w-4 mr-1 text-gray-500" />;
   }

   // Filtered plays based on state
   const filteredPlays = useCallback((): Play[] => {
     if (!pbpData || !pbpData.periods) return [];
     let combinedPlays: Play[] = [];
     if (periodFilter === "all") {
       combinedPlays = pbpData.periods.reduce((acc, p) => acc.concat(p.plays || []), [] as Play[]);
     } else {
       const periodNumber = parseInt(periodFilter.replace("q", ""));
       combinedPlays = pbpData.periods.find(p => p.period === periodNumber)?.plays || [];
     }
     return combinedPlays.sort((a, b) => a.event_num - b.event_num);
   }, [pbpData, periodFilter]);

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
            {isLoading && pbpData?.source === 'live' && " (Updating...)"}
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
          <div className="flex-grow overflow-hidden flex flex-col"> {/* Allow vertical flex growth */}
             {/* Period Filter */}
              {pbpData.periods && pbpData.periods.length > 0 && (
                <div className="mb-4 flex items-center gap-2 flex-shrink-0"> {/* Prevent filter from shrinking */}
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

            {/* PBP List Area - Make this scrollable */}
            <div className="flex-grow overflow-y-auto pr-2 space-y-2 text-sm"> 
               {/* Header Row */}
               <div className="flex items-center font-semibold text-muted-foreground px-2 py-1 sticky top-0 bg-background z-10 border-b">
                 <div className="w-16 shrink-0">Time</div>
                 <div className="w-20 shrink-0">Score</div>
                 <div className="w-32 shrink-0">Action</div>
                 <div className="flex-grow min-w-0">Description</div>
               </div>
               {/* Play List */} 
               {filteredPlays().length > 0 ? (
                 filteredPlays().map((play: Play, index: number) => (
                   <div 
                     key={play.event_num} 
                     className={`flex items-start gap-2 px-2 py-1.5 rounded-md ${index % 2 === 0 ? "bg-muted/30" : ""}`}
                   >
                     <div className="w-16 shrink-0 font-mono pt-0.5">{play.clock}</div>
                     <div className="w-20 shrink-0 font-medium pt-0.5 whitespace-nowrap">{play.score || "-"}</div>
                     <div className="w-32 shrink-0">
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
          <p className="text-center py-10 text-muted-foreground">No Play-by-Play data available.</p>
        )}

        <DialogFooter className="mt-4 flex-shrink-0"> {/* Prevent footer shrinking */}
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
} 