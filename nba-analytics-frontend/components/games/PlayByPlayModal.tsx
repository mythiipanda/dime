"use client";

import { useState, useMemo, useEffect } from 'react'; // Removed useCallback, useRef
import { PbpData, Play } from "@/app/(app)/games/types";
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
import { Terminal, Loader2 } from "lucide-react"; // Removed icons now in PlayItem
// import { cn } from "@/lib/utils"; // cn is used by PlayItem, not directly here
import { usePlayByPlayData } from '@/lib/hooks/usePlayByPlayData';
import { PlayItem } from './PlayItem'; // Import the new PlayItem component

interface PlayByPlayModalProps {
  gameId: string | null;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}

export function PlayByPlayModal({ gameId, isOpen, onOpenChange }: PlayByPlayModalProps) {
  const [periodFilter, setPeriodFilter] = useState<string>("all");

  const { 
    pbpData, 
    isLoading, 
    error, 
    // fetchPbpData // Not called directly, hook manages it based on deps
  } = usePlayByPlayData({ gameId, isOpen, periodFilter });

  // Reset periodFilter when modal is closed or gameId changes
  useEffect(() => {
    if (!isOpen || (pbpData && pbpData.game_id !== gameId)) {
        setPeriodFilter("all");
    }
  }, [isOpen, gameId, pbpData]);

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
            {!isLoading && pbpData?.source === 'live' && " (Live Update)"}
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

            <div className="flex-grow overflow-y-auto pr-2 space-y-1 text-sm scrollbar-thin scrollbar-thumb-muted-foreground/50 hover:scrollbar-thumb-muted-foreground/80 scrollbar-track-transparent scrollbar-thumb-rounded-full">
               <div className="flex items-center font-semibold text-muted-foreground px-2 py-1 sticky top-0 bg-background z-10 border-b mb-1">
                 <div className="w-16 shrink-0">Time</div>
                 <div className="w-20 shrink-0">Score</div>
                 <div className="w-32 shrink-0">Action</div>
                 <div className="flex-grow min-w-0">Description</div>
               </div>
               {filteredPlaysList.length > 0 ? (
                 filteredPlaysList.map((play: Play, index: number) => (
                   <PlayItem key={play.event_num} play={play} index={index} />
                 ))
               ) : (
                 <div className="text-center p-4 text-muted-foreground">No actions for the selected period.</div>
               )}
             </div>
          </div>
        ) : (
          <p className="text-center py-10 text-muted-foreground">No Play-by-Play data available for this game or selection.</p>
        )}

        <DialogFooter className="mt-4 flex-shrink-0 pt-4 border-t">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
} 