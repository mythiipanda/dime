"use client";
import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import styles from './Odds.module.css';

interface Outcome {
  type: string;
  odds: string;
  spread?: number;
  opening_spread?: number;
}

interface Book {
  id: string;
  name: string;
  outcomes: Outcome[];
}

interface Market {
  name: string;
  books: Book[];
}

interface GameOdds {
  gameId: string;
  markets: Market[];
}

const Odds: React.FC = () => {
  const [games, setGames] = useState<GameOdds[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchOdds = async () => {
      try {
        const res = await fetch('/api/odds');
        if (!res.ok) throw new Error(res.statusText);
        const data = await res.json();
        setGames(data.games || []);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchOdds();
  }, []);

  if (loading) return <div className={styles.loading}>Loading odds...</div>;
  if (error) return <div className={styles.error}>Error: {error}</div>;
  if (games.length === 0) return <div className={styles.noData}>No odds available.</div>;

  return (
    <>
      {games.map((game) => (
        <Card key={game.gameId} className={styles.card}>
          <CardHeader>
            <CardTitle>Game {game.gameId}</CardTitle>
          </CardHeader>
          <CardContent>
            {game.markets.map((market, mi) => (
              <div key={mi} className={styles.market}>
                <h4 className={styles.marketName}>{market.name}</h4>
                {market.books.map((book) => (
                  <div key={book.id} className={styles.book}>
                    <strong>{book.name}</strong>
                    <ul className={styles.outcomes}>
                      {book.outcomes.map((outcome, oi) => (
                        <li key={oi}>
                          <span className={styles.outcomeType}>{outcome.type}</span>: {' '}
                          <span className={styles.outcomeOdds}>{outcome.odds}</span>
                          {outcome.spread != null && (
                            <span className={styles.outcomeSpread}> (Spread: {outcome.spread})</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            ))}
          </CardContent>
        </Card>
      ))}
    </>
  );
};

export default Odds;
