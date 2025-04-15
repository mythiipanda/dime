'use client';

import React, { useState, useEffect } from 'react';
import styles from './LiveScores.module.css'; // We'll create this CSS module next

interface TeamScore {
  teamId: number;
  teamName: string;
  teamCity: string;
  teamTricode: string;
  wins: number;
  losses: number;
  score: number;
  inBonus: string | null;
  timeoutsRemaining: number;
  periods: { period: number; periodType: string; score: number }[];
}

interface GameLeader {
  personId: number;
  name: string;
  jerseyNum: string;
  position: string;
  teamTricode: string;
  playerSlug: string | null;
  points: number;
  rebounds: number;
  assists: number;
}

interface Game {
  gameId: string;
  gameCode: string;
  gameStatus: number;
  gameStatusText: string;
  period: number;
  gameClock: string;
  gameTimeUTC: string;
  gameEt: string;
  regulationPeriods: number;
  seriesGameNumber: string;
  seriesText: string;
  homeTeam: TeamScore;
  awayTeam: TeamScore;
  gameLeaders: {
    homeLeaders: GameLeader;
    awayLeaders: GameLeader;
  };
  pbOdds: {
    team: string | null;
    odds: number;
    suspended: number;
  };
}

interface ScoreboardData {
  meta: {
    version: number;
    request: string;
    time: string;
    code: number;
  };
  scoreboard: {
    gameDate: string;
    leagueId: string;
    leagueName: string;
    games: Game[];
  };
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
        // Assuming the backend runs on port 8000 locally
        const response = await fetch('http://localhost:8000/league/scoreboard');
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

  if (!scores || scores.scoreboard.games.length === 0) {
    return <div className={styles.noGames}>No live games currently.</div>;
  }

  return (
    <div className={styles.liveScoresContainer}>
      <h2>Live NBA Scores - {new Date(scores.scoreboard.gameDate).toLocaleDateString()}</h2>
      <div className={styles.gamesGrid}>
        {scores.scoreboard.games.map((game) => (
          <div key={game.gameId} className={styles.gameCard}>
            <div className={styles.gameStatus}>
              <span>{game.gameStatusText}</span>
              {game.gameStatus === 2 && <span> - Q{game.period} {game.gameClock.replace('PT','').replace('M','.').replace('S','')}</span>}
            </div>
            <div className={styles.teamInfo}>
              <span className={styles.teamName}>{game.awayTeam.teamCity} {game.awayTeam.teamName}</span>
              <span className={styles.score}>{game.awayTeam.score}</span>
            </div>
            <div className={styles.teamInfo}>
              <span className={styles.teamName}>{game.homeTeam.teamCity} {game.homeTeam.teamName}</span>
              <span className={styles.score}>{game.homeTeam.score}</span>
            </div>
            {/* Add more details like leaders if needed */}
            {/* <div className={styles.gameLeaders}>
              Leaders: {game.gameLeaders.homeLeaders.name} ({game.gameLeaders.homeLeaders.points} PTS) / {game.gameLeaders.awayLeaders.name} ({game.gameLeaders.awayLeaders.points} PTS)
            </div> */}
          </div>
        ))}
      </div>
    </div>
  );
};

export default LiveScores;