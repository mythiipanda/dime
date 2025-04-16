'use client';

import React, { useState, useEffect } from 'react';
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

  useEffect(() => {
    const fetchScores = async () => {
      setLoading(true);
      setError(null);
      try {
        // Fetch live scores via our Next.js API
        const response = await fetch('/api/games/scoreboard');
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data: ScoreboardData = await response.json();
        setScores(data);
      } catch (e: any) {
        console.error("Failed to fetch scores:", e);
        setError(`Failed to load scores: ${e.message}`);
      } finally {
        setLoading(false);
      }
    };

    fetchScores();
    // TODO: Implement polling or WebSocket for real-time updates
    // const intervalId = setInterval(fetchScores, 30000); // Poll every 30 seconds
    // return () => clearInterval(intervalId);
  }, []);

  if (loading) {
    return <div className={styles.loading}>Loading live scores...</div>;
  }

  if (error) {
    return <div className={styles.error}>{error}</div>;
  }

  if (!scores || scores.games.length === 0) {
    return <div className={styles.noGames}>No live games currently.</div>;
  }

  return (
    <div className={styles.liveScoresContainer}>
      <h2>Live NBA Scores - {new Date(scores.gameDate).toLocaleDateString()}</h2>
      <div className={styles.gamesGrid}>
        {scores.games.map((game) => (
          <div key={game.gameId} className={styles.gameCard}>
            <div className={styles.gameStatus}>
              <span>{game.gameStatusText}</span>
              {game.gameStatus === 2 && <span> - Q{game.period} {game.gameClock}</span>}
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