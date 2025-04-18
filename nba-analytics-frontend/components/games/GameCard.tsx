"use client";

import { Game } from "@/app/(app)/games/types"; // Adjust path as needed
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { format, parseISO, isToday } from 'date-fns';

interface GameCardProps {
  game: Game;
  viewingToday: boolean; // Need to know if we should show live indicator/pulse
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
          className={`whitespace-nowrap px-2 py-0.5 rounded text-xs font-semibold ${
            game.gameStatus === 1 ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' : 
            (game.gameStatus === 2 && viewingToday) ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 animate-pulse' : 
            game.gameStatus === 2 ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' : 
            'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
          }`}
        >
          {game.gameStatusText}
        </span>
      </CardHeader>
      <CardContent className="pt-2"> 
        {/* Away Team */}
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
        {/* Home Team */}
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
        {/* Game Time / Clock */}
        {game.gameStatus === 1 && game.gameEt && (
           <div className="text-center text-xs text-muted-foreground mt-2">
             {(() => {
                try {
                  return format(parseISO(game.gameEt), 'p zzz'); 
                } catch { 
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
  );
} 