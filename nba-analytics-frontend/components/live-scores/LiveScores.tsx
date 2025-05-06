'use client';

import React, { useState, useEffect, useRef } from 'react';
// Removed: import styles from './LiveScores.module.css';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertCircle, Loader2 } from "lucide-react"; // Added AlertCircle and Loader2
import { cn } from "@/lib/utils"; // Added cn

// Define our scoreboard shape
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

const LiveScores: React.FC = () => {
  const [scores, setScores] = useState<ScoreboardData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/games/scoreboard/ws`;

    console.log(`Attempting to connect WebSocket: ${wsUrl}`);
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      console.log("WebSocket connected");
      setIsConnected(true);
      setError(null);
    };

    ws.current.onclose = () => {
      console.log("WebSocket disconnected");
      setIsConnected(false);
      if (!scores) {
         setLoading(true); 
         setError("WebSocket disconnected. Attempting to reconnect...");
      }
    };

    ws.current.onerror = (event) => {
      console.error("WebSocket error:", event);
      setError("WebSocket connection error. Please try refreshing.");
      setLoading(false);
      setIsConnected(false);
    };

    ws.current.onmessage = (event) => {
      try {
        const data: ScoreboardData = JSON.parse(event.data);
        if (data && data.games && Array.isArray(data.games)) {
           setScores(data);
           setError(null);
           if (loading) setLoading(false);
           console.log("Scoreboard updated via WebSocket");
        } else {
           console.warn("Received invalid data format from WebSocket:", event.data);
        }
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
      }
    };

    return () => {
      console.log("Closing WebSocket connection");
      ws.current?.close();
    };
  }, [loading, scores]);

  if (loading && !isConnected && !error) {
    return (
      <div className="flex flex-col items-center justify-center p-6 bg-card text-card-foreground rounded-lg shadow-sm border min-h-[200px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary mb-3" />
        <p className="text-muted-foreground">Connecting to live scores...</p>
      </div>
    );
  }
  
  if (loading && isConnected && !scores && !error){
    return (
      <div className="flex flex-col items-center justify-center p-6 bg-card text-card-foreground rounded-lg shadow-sm border min-h-[200px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary mb-3" />
        <p className="text-muted-foreground">Waiting for initial scores...</p>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive" className="my-4">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Connection Error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (!scores || scores.games.length === 0) {
    if (!isConnected && !error) {
      return (
        <div className="flex flex-col items-center justify-center p-6 bg-card text-card-foreground rounded-lg shadow-sm border min-h-[200px]">
          <Loader2 className="h-8 w-8 animate-spin text-primary mb-3" />
          <p className="text-muted-foreground">Connecting...</p>
        </div>
      );
    }
    return (
      <div className="p-6 bg-card text-card-foreground rounded-lg shadow-sm border min-h-[200px] flex items-center justify-center">
        <p className="text-muted-foreground text-center">No live games currently or waiting for data.</p>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 bg-background rounded-lg">
      <h2 className="text-2xl font-semibold text-center mb-6 text-foreground">
        Live NBA Scores - {new Date(scores.gameDate).toLocaleDateString()}
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {scores.games.map((game) => (
          <Card key={game.gameId} className="transition-all hover:shadow-md flex flex-col">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 pt-4 px-4">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                {game.awayTeam.teamTricode} @ {game.homeTeam.teamTricode}
              </CardTitle>
              <Badge
                variant={game.gameStatus === 2 ? "default" : "outline"}
                className={cn(
                  "text-xs px-2 py-0.5",
                  game.gameStatus === 2 && "animate-pulse"
                )}
              >
                {game.gameStatusText}
              </Badge>
            </CardHeader>
            <CardContent className="pt-2 pb-4 px-4 flex-grow flex flex-col justify-between">
              <div>
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm font-medium text-foreground">{game.awayTeam.teamTricode}</span>
                  <span className="text-lg font-bold text-foreground">{game.awayTeam.score ?? '-'}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium text-foreground">{game.homeTeam.teamTricode}</span>
                  <span className="text-lg font-bold text-foreground">{game.homeTeam.score ?? '-'}</span>
                </div>
              </div>
              <div className="mt-3 text-center text-xs text-muted-foreground">
                {game.gameStatus === 2 && game.period && game.gameClock ? (
                  `Q${game.period} ${game.gameClock}`
                ) : game.gameStatus !== 2 ? (
                  new Date(game.gameEt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })
                ) : (
                  <span>&nbsp;</span> // Placeholder for consistent height if no clock/time
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
};

export default LiveScores;