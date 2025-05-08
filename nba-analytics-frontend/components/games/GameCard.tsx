"use client";

import { Game } from "@/app/(app)/games/types"; // Adjust path as needed
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar"; // Import Avatar
import { cn } from "@/lib/utils"; // Import cn utility
import { format, parseISO } from 'date-fns';

interface GameCardProps {
  game: Game;
  viewingToday: boolean; // Used for live indicator/pulse
  onClick: (gameId: string) => void;
}

export function GameCard({ game, viewingToday, onClick }: GameCardProps) {
  if (!game || !game.gameId) return null; // Basic validation

  const handleCardClick = () => {
    onClick(game.gameId);
  };

  // TODO: Move rendering logic for a single game card here
  // from the original page.tsx loop.

  return (
    <Card
      key={game.gameId}
      className="cursor-pointer hover:shadow-lg transition-shadow duration-200"
      onClick={handleCardClick}
    >
      <CardHeader className={`flex flex-row items-center justify-between space-y-0 pb-2 ${game.gameStatus === 2 && viewingToday ? 'bg-green-50 dark:bg-green-900/20' : ''}`}>
        <CardTitle className="text-sm font-medium">
          {game.awayTeam?.teamTricode || 'N/A'} @ {game.homeTeam?.teamTricode || 'N/A'}
        </CardTitle>
        <span 
          className={cn(
            "whitespace-nowrap px-2 py-0.5 rounded-full text-xs font-semibold",
            game.gameStatus === 1 && "bg-accent text-accent-foreground", // Scheduled
            game.gameStatus === 2 && viewingToday && "bg-primary text-primary-foreground animate-pulse", // Live
            game.gameStatus === 2 && !viewingToday && "bg-muted text-muted-foreground", // Final (on past date)
            game.gameStatus >= 3 && "bg-muted text-muted-foreground" // Final / Other
          )}
        >
          {game.gameStatusText}
        </span>
      </CardHeader>
      <CardContent className="pt-2"> 
        {/* Away Team */}
        <div className="flex justify-between items-center mb-2">
          <div className="flex items-center gap-2">
            <Avatar className="h-6 w-6 text-xs">
              <AvatarFallback>{game.awayTeam?.teamTricode ? game.awayTeam.teamTricode.substring(0,2) : 'AWY'}</AvatarFallback>
            </Avatar>
            <span className="font-semibold">{game.awayTeam?.teamTricode || 'N/A'}</span>
            {game.awayTeam?.wins !== undefined && game.awayTeam?.losses !== undefined && (
                <span className="text-xs text-muted-foreground">({game.awayTeam.wins}-{game.awayTeam.losses})</span>
            )}
          </div>
          <div className="text-xl font-bold">{game.gameStatus === 1 ? '-' : (game.awayTeam?.score ?? '-')}</div>
        </div>
        {/* Home Team */}
        <div className="flex justify-between items-center">
           <div className="flex items-center gap-2">
            <Avatar className="h-6 w-6 text-xs">
              <AvatarFallback>{game.homeTeam?.teamTricode ? game.homeTeam.teamTricode.substring(0,2) : 'HME'}</AvatarFallback>
            </Avatar>
            <span className="font-semibold">{game.homeTeam?.teamTricode || 'N/A'}</span>
             {game.homeTeam?.wins !== undefined && game.homeTeam?.losses !== undefined && (
                <span className="text-xs text-muted-foreground">({game.homeTeam.wins}-{game.homeTeam.losses})</span>
             )}
          </div>
           <div className="text-xl font-bold">{game.gameStatus === 1 ? '-' : (game.homeTeam?.score ?? '-')}</div>
        </div>
        {/* Game Time / Clock Info */}
        {game.gameStatus === 1 && game.gameEt && (
           <div className="text-center text-xs text-muted-foreground mt-2">
             {(() => {
                try {
                  // Format start time
                  return format(parseISO(game.gameEt), 'p zzz'); 
                } catch { 
                  return game.gameEt; // Fallback to raw string if parse fails
                }
              })()}
           </div>
         )}
          {game.gameStatus === 2 && game.gameClock && (
             <div className="text-center text-xs text-muted-foreground mt-2">
               {/* Display live clock */}
               {game.period && `Q${game.period} `}{game.gameClock}
             </div>
         )}
      </CardContent>
    </Card>
  );
} 