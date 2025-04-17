'use client';

import React, { useState, useEffect, useRef } from 'react';
import styles from './LiveScores.module.css';

// Import our frontend API base for scoreboard
// Fetch live scoreboard via Next.js API route

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
  }, [scores === null]);

  if (loading && !isConnected && !error) {
     return <div className={styles.loading}>Connecting to live scores...</div>;
  }
  
  if (loading && isConnected && !scores && !error){
     return <div className={styles.loading}>Waiting for initial scores...</div>;
  }

  if (error) {
    return <div className={styles.error}>{error}</div>;
  }

  if (!scores || scores.games.length === 0) {
    if (!isConnected && !error) {
       return <div className={styles.noGames}>Connecting...</div>;
    }
    return <div className={styles.noGames}>No live games currently or waiting for data.</div>;
  }

  return (
    <div className={styles.liveScoresContainer}>
      <h2>Live NBA Scores - {new Date(scores.gameDate).toLocaleDateString()}</h2>
      <div className={styles.gamesGrid}>
        {scores.games.map((game) => (
          <div key={game.gameId} className={styles.gameCard}>
            <div className={styles.gameStatus}>
              <span>{game.gameStatusText}</span>
              {game.gameStatus === 2 && game.period && game.gameClock && (
                <span> - Q{game.period} {game.gameClock}</span>
              )}
            </div>
            <div className={styles.teamInfo}>
              <span className={styles.teamName}>{game.awayTeam.teamTricode}</span>
              <span className={styles.score}>{game.awayTeam.score}</span>
            </div>
            <div className={styles.teamInfo}>
              <span className={styles.teamName}>{game.homeTeam.teamTricode}</span>
              <span className={styles.score}>{game.homeTeam.score}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default LiveScores;