import { useState, useEffect } from 'react';
import { API_BASE_URL } from "@/lib/config";

// Define types for shot and zone data, or import if they exist elsewhere
// For now, using 'any' for brevity, but specific types are recommended.
export interface Shot {
  x: number;
  y: number;
  made: boolean;
  value: number;
  shot_type: string;
  shot_zone: string;
  distance: number;
  game_date: string;
  period: number;
}

export interface Zone {
  zone: string;
  attempts: number;
  made: number;
  percentage: number;
  leaguePercentage: number;
  relativePercentage: number;
}

interface UsePlayerShotDataOptions {
  playerName: string | null;
  season: string | null;
  seasonType: string | null;
}

interface UsePlayerShotDataResult {
  shotData: Shot[];
  zoneData: Zone[];
  isLoading: boolean;
  error: string | null;
  fetchData: () => void; // Allow manual refetch if needed
}

export function usePlayerShotData({
  playerName,
  season,
  seasonType,
}: UsePlayerShotDataOptions): UsePlayerShotDataResult {
  const [shotData, setShotData] = useState<Shot[]>([]);
  const [zoneData, setZoneData] = useState<Zone[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!playerName) {
      setShotData([]);
      setZoneData([]);
      setError(null); // Clear error if no player name
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (season) params.append("season", season);
      if (seasonType) params.append("season_type", seasonType);

      const response = await fetch(
        `${API_BASE_URL}/analyze/player/${encodeURIComponent(playerName)}/shots?${params.toString()}`
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: `Failed to fetch shot data (${response.status})` }));
        throw new Error(errorData.error || `Failed to fetch shot data: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      const shots: Shot[] = data.shots.map((shot: any) => ({
        x: shot.x,
        y: shot.y,
        made: shot.made,
        value: shot.value,
        shot_type: shot.shot_type,
        shot_zone: shot.zone,
        distance: shot.distance,
        game_date: shot.game_date,
        period: shot.period,
      }));

      const zones: Zone[] = Object.entries(data.zones).map(([zoneName, stats]: [string, any]) => ({
        zone: zoneName,
        attempts: stats.attempts,
        made: stats.made,
        percentage: stats.percentage / 100,
        leaguePercentage: stats.league_percentage / 100,
        relativePercentage: stats.relative_percentage / 100,
      }));

      setShotData(shots);
      setZoneData(zones);
    } catch (err) {
      console.error("[usePlayerShotData] Error fetching shot data:", err);
      setError(err instanceof Error ? err.message : "Failed to fetch shot data");
      setShotData([]); // Clear data on error
      setZoneData([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [playerName, season, seasonType]); // Dependencies that trigger re-fetch

  return { shotData, zoneData, isLoading, error, fetchData };
} 