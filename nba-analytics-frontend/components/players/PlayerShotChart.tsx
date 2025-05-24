"use client";

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { 
  Target, 
  RefreshCw, 
  AlertTriangle,
  BarChart3,
  TrendingUp,
  TrendingDown
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getPlayerShotChart } from "@/lib/api/players";

interface PlayerShotChartProps {
  playerId: string;
  season: string;
}

interface ShotData {
  x: number;
  y: number;
  made: boolean;
  shot_type: string;
  distance: number;
  quarter: number;
  time_remaining: string;
  game_date: string;
  opponent: string;
}

interface ZoneStats {
  zone_name: string;
  made: number;
  attempted: number;
  percentage: number;
  league_average: number;
}

export function PlayerShotChart({ playerId, season }: PlayerShotChartProps) {
  const [shotData, setShotData] = useState<ShotData[]>([]);
  const [zoneStats, setZoneStats] = useState<ZoneStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [seasonType, setSeasonType] = useState("Regular Season");
  const [lastNGames, setLastNGames] = useState("0");

  useEffect(() => {
    const fetchShotChartData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const data = await getPlayerShotChart(playerId, season);
        
        // Transform API data
        const shots: ShotData[] = data.shots?.map((shot: any) => ({
          x: shot.LOC_X || shot.x || 0,
          y: shot.LOC_Y || shot.y || 0,
          made: shot.SHOT_MADE_FLAG === 1 || shot.made === true,
          shot_type: shot.ACTION_TYPE || shot.shot_type || 'Unknown',
          distance: shot.SHOT_DISTANCE || shot.distance || 0,
          quarter: shot.PERIOD || shot.quarter || 1,
          time_remaining: shot.MINUTES_REMAINING + ':' + shot.SECONDS_REMAINING || shot.time_remaining || '0:00',
          game_date: shot.GAME_DATE || shot.game_date || '',
          opponent: shot.HTM || shot.VTM || shot.opponent || 'Unknown'
        })) || [];

        // Calculate zone statistics
        const zones = calculateZoneStats(shots);
        
        setShotData(shots);
        setZoneStats(zones);
      } catch (err) {
        console.error('Error fetching shot chart data:', err);
        setError('Failed to load shot chart data');
        
        // Set mock data as fallback
        setShotData(createMockShotData());
        setZoneStats(createMockZoneStats());
      } finally {
        setLoading(false);
      }
    };

    fetchShotChartData();
  }, [playerId, season, seasonType, lastNGames]);

  const calculateZoneStats = (shots: ShotData[]): ZoneStats[] => {
    const zones = [
      { name: 'Restricted Area', shots: shots.filter(s => s.distance <= 4) },
      { name: 'Paint (Non-RA)', shots: shots.filter(s => s.distance > 4 && s.distance <= 8) },
      { name: 'Mid-Range', shots: shots.filter(s => s.distance > 8 && s.distance < 23) },
      { name: 'Three-Point', shots: shots.filter(s => s.distance >= 23) },
      { name: 'Corner 3', shots: shots.filter(s => s.distance >= 23 && Math.abs(s.x) > 220) },
      { name: 'Above Break 3', shots: shots.filter(s => s.distance >= 23 && Math.abs(s.x) <= 220) }
    ];

    return zones.map(zone => {
      const made = zone.shots.filter(s => s.made).length;
      const attempted = zone.shots.length;
      const percentage = attempted > 0 ? (made / attempted) * 100 : 0;
      
      return {
        zone_name: zone.name,
        made,
        attempted,
        percentage,
        league_average: getLeagueAverage(zone.name) // Mock league averages
      };
    });
  };

  const getLeagueAverage = (zoneName: string): number => {
    const averages: { [key: string]: number } = {
      'Restricted Area': 68.5,
      'Paint (Non-RA)': 45.2,
      'Mid-Range': 42.1,
      'Three-Point': 36.8,
      'Corner 3': 39.2,
      'Above Break 3': 35.4
    };
    return averages[zoneName] || 40.0;
  };

  const createMockShotData = (): ShotData[] => [
    { x: 0, y: 10, made: true, shot_type: 'Layup', distance: 2, quarter: 1, time_remaining: '10:30', game_date: '2024-01-15', opponent: 'LAL' },
    { x: 150, y: 100, made: false, shot_type: 'Jump Shot', distance: 18, quarter: 2, time_remaining: '5:45', game_date: '2024-01-15', opponent: 'LAL' },
    { x: -200, y: 200, made: true, shot_type: '3PT Field Goal', distance: 24, quarter: 3, time_remaining: '8:20', game_date: '2024-01-15', opponent: 'LAL' }
  ];

  const createMockZoneStats = (): ZoneStats[] => [
    { zone_name: 'Restricted Area', made: 45, attempted: 65, percentage: 69.2, league_average: 68.5 },
    { zone_name: 'Paint (Non-RA)', made: 28, attempted: 62, percentage: 45.2, league_average: 45.2 },
    { zone_name: 'Mid-Range', made: 35, attempted: 85, percentage: 41.2, league_average: 42.1 },
    { zone_name: 'Three-Point', made: 95, attempted: 265, percentage: 35.8, league_average: 36.8 }
  ];

  const refreshData = async () => {
    try {
      setLoading(true);
      const data = await getPlayerShotChart(playerId, season);
      const shots: ShotData[] = data.shots?.map((shot: any) => ({
        x: shot.LOC_X || shot.x || 0,
        y: shot.LOC_Y || shot.y || 0,
        made: shot.SHOT_MADE_FLAG === 1 || shot.made === true,
        shot_type: shot.ACTION_TYPE || shot.shot_type || 'Unknown',
        distance: shot.SHOT_DISTANCE || shot.distance || 0,
        quarter: shot.PERIOD || shot.quarter || 1,
        time_remaining: shot.MINUTES_REMAINING + ':' + shot.SECONDS_REMAINING || shot.time_remaining || '0:00',
        game_date: shot.GAME_DATE || shot.game_date || '',
        opponent: shot.HTM || shot.VTM || shot.opponent || 'Unknown'
      })) || [];
      
      setShotData(shots);
      setZoneStats(calculateZoneStats(shots));
      setError(null);
    } catch (err) {
      setError('Failed to refresh data');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-6 w-32" />
          <div className="flex gap-2">
            <Skeleton className="h-10 w-32" />
            <Skeleton className="h-10 w-32" />
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-96 w-full" />
          <div className="space-y-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-semibold">Shot Chart</h2>
          {error && (
            <Badge variant="destructive" className="text-xs">
              <AlertTriangle className="w-3 h-3 mr-1" />
              {error}
            </Badge>
          )}
          <Badge variant="secondary" className="text-xs">
            <Target className="w-3 h-3 mr-1" />
            {shotData.length} Shots
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={refreshData}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Select value={seasonType} onValueChange={setSeasonType}>
            <SelectTrigger className="w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Regular Season">Regular</SelectItem>
              <SelectItem value="Playoffs">Playoffs</SelectItem>
            </SelectContent>
          </Select>
          <Select value={lastNGames} onValueChange={setLastNGames}>
            <SelectTrigger className="w-[120px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="0">All Games</SelectItem>
              <SelectItem value="10">Last 10</SelectItem>
              <SelectItem value="20">Last 20</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Shot Chart Visualization */}
        <Card>
          <CardHeader>
            <CardTitle>Court Visualization</CardTitle>
            <CardDescription>
              {shotData.filter(s => s.made).length} made / {shotData.length} attempted 
              ({shotData.length > 0 ? ((shotData.filter(s => s.made).length / shotData.length) * 100).toFixed(1) : 0}%)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="relative w-full h-96 bg-orange-100 rounded-lg border-2 border-orange-300 overflow-hidden">
              {/* Basketball court representation */}
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-orange-600 text-sm">
                  Interactive shot chart visualization would be rendered here
                </div>
              </div>
              
              {/* Shot dots overlay */}
              <div className="absolute inset-0">
                {shotData.slice(0, 50).map((shot, index) => (
                  <div
                    key={index}
                    className={cn(
                      "absolute w-2 h-2 rounded-full",
                      shot.made ? "bg-green-500" : "bg-red-500"
                    )}
                    style={{
                      left: `${50 + (shot.x / 10)}%`,
                      top: `${50 + (shot.y / 10)}%`,
                    }}
                    title={`${shot.shot_type} - ${shot.made ? 'Made' : 'Missed'} - ${shot.distance}ft`}
                  />
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Zone Statistics */}
        <Card>
          <CardHeader>
            <CardTitle>Shooting Zones</CardTitle>
            <CardDescription>Performance by court area</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {zoneStats.map((zone, index) => (
                <div key={index} className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="font-medium">{zone.zone_name}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-muted-foreground">
                        {zone.made}/{zone.attempted}
                      </span>
                      <Badge 
                        variant={zone.percentage > zone.league_average ? "default" : "secondary"}
                        className="text-xs"
                      >
                        {zone.percentage.toFixed(1)}%
                      </Badge>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Player</span>
                      <span>League Avg: {zone.league_average.toFixed(1)}%</span>
                    </div>
                    <div className="relative">
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div 
                          className={cn(
                            "h-2 rounded-full transition-all",
                            zone.percentage > zone.league_average ? "bg-green-500" : "bg-red-500"
                          )}
                          style={{ width: `${Math.min(zone.percentage, 100)}%` }}
                        />
                      </div>
                      <div 
                        className="absolute top-0 w-0.5 h-2 bg-gray-600"
                        style={{ left: `${Math.min(zone.league_average, 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Shot Summary */}
      <Card>
        <CardHeader>
          <CardTitle>Shot Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {shotData.filter(s => s.made).length}
              </div>
              <div className="text-sm text-muted-foreground">Made</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">
                {shotData.filter(s => !s.made).length}
              </div>
              <div className="text-sm text-muted-foreground">Missed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">
                {shotData.length > 0 ? ((shotData.filter(s => s.made).length / shotData.length) * 100).toFixed(1) : 0}%
              </div>
              <div className="text-sm text-muted-foreground">Field Goal %</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">
                {shotData.length > 0 ? (shotData.reduce((sum, shot) => sum + shot.distance, 0) / shotData.length).toFixed(1) : 0}ft
              </div>
              <div className="text-sm text-muted-foreground">Avg Distance</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
