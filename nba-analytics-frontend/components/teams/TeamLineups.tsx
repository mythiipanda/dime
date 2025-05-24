"use client";

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { RefreshCw, AlertTriangle, Users, BarChart3 } from "lucide-react";
import { cn } from "@/lib/utils";
import { getTeamLineups } from "@/lib/api/teams";
import { getTeamDashboardData } from "@/lib/api/teams";

interface TeamLineupsProps {
  teamId: string;
  season: string;
  lineups?: any[]; // Real lineups data passed from parent
}

export function TeamLineups({ teamId, season, lineups }: TeamLineupsProps) {
  const [filter, setFilter] = useState("all");
  const [lineupData, setLineupData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const processLineupData = () => {
      try {
        setLoading(true);
        setError(null);

        // Use passed lineups data if available
        if (lineups && lineups.length > 0) {
          setLineupData({ lineups: lineups });
        } else {
          console.warn('No lineups data provided, will use mock data');
          setLineupData(null);
        }
      } catch (err) {
        console.error('Error processing lineup data:', err);
        setError('Failed to load lineup data');
      } finally {
        setLoading(false);
      }
    };

    processLineupData();
  }, [teamId, season, lineups]);

  const refreshData = () => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // Try to fetch real lineup data first
        try {
          const lineupsData = await getTeamLineups(teamId, season);
          setLineupData(lineupsData);
        } catch (lineupError) {
          console.warn('Lineup API failed, trying dashboard data:', lineupError);
          const data = await getTeamDashboardData(teamId, season);
          setLineupData(data);
        }
        setError(null);
      } catch (err) {
        setError('Failed to refresh data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  };

  // Transform real lineup data or use mock data
  const processedLineups = lineupData?.lineups ? lineupData.lineups.map((lineup: any, index: number) => {
    // Extract player names from the GROUP_NAME field
    const playerNames = lineup.GROUP_NAME ? lineup.GROUP_NAME.split(' - ') : [`Lineup ${index + 1}`];

    // Calculate realistic ratings from available stats
    const minutes = lineup.MIN || 0;
    const points = lineup.PTS || 0;
    const fga = lineup.FGA || 0;
    const fta = lineup.FTA || 0;
    const tov = lineup.TOV || 0;
    const plusMinus = lineup.PLUS_MINUS || 0;
    const gamesPlayed = lineup.GP || 1;

    // Calculate per-game averages
    const pointsPerGame = points / gamesPlayed;
    const fgaPerGame = fga / gamesPlayed;
    const ftaPerGame = fta / gamesPlayed;
    const tovPerGame = tov / gamesPlayed;

    // Estimate possessions per game: FGA + 0.44 * FTA + TOV
    const possessionsPerGame = fgaPerGame + 0.44 * ftaPerGame + tovPerGame;

    // Offensive rating: points per 100 possessions
    const offRtg = possessionsPerGame > 0 ? (pointsPerGame / possessionsPerGame) * 100 : 110;

    // Defensive rating estimate based on plus/minus and league average
    // If plus/minus is positive, assume better defense (lower rating)
    const leagueAvgDefRtg = 112;
    const defRtg = Math.max(95, Math.min(125, leagueAvgDefRtg - (plusMinus / gamesPlayed) * 2));

    const netRtg = offRtg - defRtg;

    return {
      id: lineup.GROUP_ID || `lineup_${index}`,
      players: playerNames,
      minutes: minutes,
      gamesPlayed: lineup.GP || 0,
      offRtg: Math.round(offRtg * 10) / 10,
      defRtg: Math.round(defRtg * 10) / 10,
      netRtg: Math.round(netRtg * 10) / 10,
      pace: 100, // Default pace since not available in lineup data
      plusMinus: plusMinus,
      type: index === 0 ? "starters" : index < 3 ? "rotation" : "bench"
    };
  }) : [];

  const filteredLineups = filter === "all"
    ? processedLineups
    : processedLineups.filter(lineup => lineup.type === filter);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-10 w-[180px]" />
        </div>
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-semibold">Team Lineups</h2>
          {error && (
            <Badge variant="destructive" className="text-xs">
              <AlertTriangle className="w-3 h-3 mr-1" />
              {error}
            </Badge>
          )}
          {lineupData && (
            <Badge variant="secondary" className="text-xs">
              <Users className="w-3 h-3 mr-1" />
              Real Data
            </Badge>
          )}
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
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Filter lineups" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Lineups</SelectItem>
              <SelectItem value="starters">Starters</SelectItem>
              <SelectItem value="closing">Closing</SelectItem>
              <SelectItem value="small">Small Ball</SelectItem>
              <SelectItem value="defensive">Defensive</SelectItem>
              <SelectItem value="bench">Bench</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <Tabs defaultValue="table" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="table">Table View</TabsTrigger>
          <TabsTrigger value="cards">Card View</TabsTrigger>
        </TabsList>

        <TabsContent value="table" className="pt-4">
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Lineup</TableHead>
                  <TableHead className="text-right">MIN</TableHead>
                  <TableHead className="text-right">GP</TableHead>
                  <TableHead className="text-right">OFF RTG</TableHead>
                  <TableHead className="text-right">DEF RTG</TableHead>
                  <TableHead className="text-right">NET RTG</TableHead>
                  <TableHead className="text-right">PACE</TableHead>
                  <TableHead className="text-right">+/-</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredLineups.map((lineup) => (
                  <TableRow key={lineup.id}>
                    <TableCell className="font-medium">
                      <div>
                        {lineup.players.join(", ")}
                      </div>
                      <div className="mt-1">
                        <Badge variant="outline" className="text-xs">
                          {lineup.type.charAt(0).toUpperCase() + lineup.type.slice(1)}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">{lineup.minutes}</TableCell>
                    <TableCell className="text-right">{lineup.gamesPlayed}</TableCell>
                    <TableCell className="text-right">{lineup.offRtg.toFixed(1)}</TableCell>
                    <TableCell className="text-right">{lineup.defRtg.toFixed(1)}</TableCell>
                    <TableCell className={cn(
                      "text-right font-medium",
                      lineup.netRtg > 0 ? "text-green-600" : "text-red-600"
                    )}>
                      {lineup.netRtg > 0 ? "+" : ""}{lineup.netRtg.toFixed(1)}
                    </TableCell>
                    <TableCell className="text-right">{lineup.pace.toFixed(1)}</TableCell>
                    <TableCell className={cn(
                      "text-right font-medium",
                      lineup.plusMinus > 0 ? "text-green-600" : "text-red-600"
                    )}>
                      {lineup.plusMinus > 0 ? "+" : ""}{lineup.plusMinus}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="cards" className="pt-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredLineups.map((lineup) => (
              <Card key={lineup.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <Badge variant="outline">
                      {lineup.type.charAt(0).toUpperCase() + lineup.type.slice(1)}
                    </Badge>
                    <div className={cn(
                      "text-sm font-medium",
                      lineup.netRtg > 0 ? "text-green-600" : "text-red-600"
                    )}>
                      Net Rating: {lineup.netRtg > 0 ? "+" : ""}{lineup.netRtg.toFixed(1)}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex flex-wrap gap-1">
                      {lineup.players.map((player, i) => (
                        <Badge key={i} variant="secondary">{player}</Badge>
                      ))}
                    </div>
                    <div className="grid grid-cols-4 gap-2 pt-2">
                      <div className="text-center">
                        <p className="text-xs text-muted-foreground">Minutes</p>
                        <p className="font-medium">{lineup.minutes}</p>
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-muted-foreground">OFF</p>
                        <p className="font-medium">{lineup.offRtg.toFixed(1)}</p>
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-muted-foreground">DEF</p>
                        <p className="font-medium">{lineup.defRtg.toFixed(1)}</p>
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-muted-foreground">+/-</p>
                        <p className={cn(
                          "font-medium",
                          lineup.plusMinus > 0 ? "text-green-600" : "text-red-600"
                        )}>
                          {lineup.plusMinus > 0 ? "+" : ""}{lineup.plusMinus}
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}