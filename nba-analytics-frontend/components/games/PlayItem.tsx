"use client";

import React from 'react';
import { Play } from "@/app/(app)/games/types";
import { cn } from "@/lib/utils";
import { XCircle, Target, AlertTriangle, Info } from "lucide-react";

// Helper functions (co-located for now, can be moved to a utils file if shared)
const getPlayDescription = (play: Play): string => {
    return play.description || play.home_description || play.away_description || play.neutral_description || "(Description unavailable)";
};

const formatEventType = (eventType: string): string => {
    return eventType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
};

const getEventTypeIcon = (play: Play): React.ReactNode => {
    const desc = getPlayDescription(play).toUpperCase();
    if (desc.startsWith('MISS')) return <XCircle className="h-4 w-4 mr-1 text-muted-foreground" />;
    if (play.event_type.includes('PT') || play.event_type.includes('FREE')) return <Target className="h-4 w-4 mr-1 text-yellow-600 dark:text-yellow-500" />;
    if (play.event_type.includes('FOUL')) return <AlertTriangle className="h-4 w-4 mr-1 text-destructive" />;
    return <Info className="h-4 w-4 mr-1 text-muted-foreground" />;
};

interface PlayItemProps {
  play: Play;
  index: number;
}

export const PlayItem: React.FC<PlayItemProps> = ({ play, index }) => {
  if (!play) return null;

  return (
    <div 
      key={play.event_num} // Key should be on the list iteration, but also fine here for standalone item
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
  );
}; 