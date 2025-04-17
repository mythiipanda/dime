"use client";
import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import styles from './Standings.module.css';

interface Standing {
  TeamID: number;
  TeamName: string;
  Conference: string;
  PlayoffRank: number;
  WinPct: number;
  GB: number;
  L10: string;
  STRK: string;
  WINS: number;
  LOSSES: number;
}

const Standings: React.FC = () => {
  const [standings, setStandings] = useState<Standing[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStandings = async () => {
      try {
        const res = await fetch('/api/standings');
        if (!res.ok) throw new Error(res.statusText);
        const data = await res.json();
        setStandings(data.standings || []);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchStandings();
  }, []);

  if (loading) return <div className={styles.loading}>Loading standings...</div>;
  if (error) return <div className={styles.error}>Error: {error}</div>;

  return (
    <Card>
      <CardHeader>
        <CardTitle>League Standings</CardTitle>
      </CardHeader>
      <CardContent>
        <div className={styles.tableContainer}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>#</th>
                <th>Team</th>
                <th>W-L</th>
                <th>Win%</th>
                <th>GB</th>
                <th>Strk</th>
              </tr>
            </thead>
            <tbody>
              {standings.map((s) => (
                <tr key={s.TeamID}>
                  <td>{s.PlayoffRank}</td>
                  <td>{s.TeamName}</td>
                  <td>{s.WINS}-{s.LOSSES}</td>
                  <td>{(s.WinPct * 100).toFixed(1)}%</td>
                  <td>{s.GB}</td>
                  <td>{s.STRK}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
};

export default Standings;
