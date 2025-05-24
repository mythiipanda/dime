"use client";

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Calendar,
  Clock,
  MapPin,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  AlertTriangle,
  Trophy,
  Target,
  Users
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getTeamSchedule } from "@/lib/api/teams";

interface TeamScheduleProps {
  teamId: string;
  season: string;
  schedule?: any[]; // Real schedule data passed from parent
}

interface Game {
  game_id: string;
  game_date: string;
  matchup: string;
  opponent: string;
  home: boolean;
  result?: 'W' | 'L';
  score?: string;
  status: 'completed' | 'upcoming' | 'live';
  tv_broadcast?: string;
  arena?: string;
  time?: string;
}

export function TeamSchedule({ teamId, season, schedule }: TeamScheduleProps) {
  const [filter, setFilter] = useState("all");
  const [scheduleData, setScheduleData] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const processScheduleData = () => {
      try {
        setLoading(true);
        setError(null);

        // Use passed schedule data if available
        if (schedule && schedule.length > 0) {
          // Transform real API data to component format
          const transformedSchedule: Game[] = schedule.map((game: any) => {
            // Determine if it's a home game based on matchup
            const isHome = game.MATCHUP?.includes('vs.') || game.MATCHUP?.includes('vs ');
            const opponent = game.MATCHUP?.replace(/^.*?(vs\.|@)\s*/, '') || 'Unknown';

            // For completed games, show team score with margin of victory/defeat
            const teamScore = game.PTS;
            const plusMinus = game.PLUS_MINUS || 0;
            const hasScore = teamScore && game.WL;

            let scoreDisplay = undefined;
            if (hasScore) {
              if (game.WL === 'W') {
                scoreDisplay = `W ${teamScore} (+${Math.abs(plusMinus)})`;
              } else {
                scoreDisplay = `L ${teamScore} (-${Math.abs(plusMinus)})`;
              }
            }

            return {
              game_id: game.GAME_ID || game.Game_ID || `game_${Math.random()}`,
              game_date: game.GAME_DATE || game.Game_Date,
              matchup: game.MATCHUP || 'TBD',
              opponent: opponent,
              home: isHome,
              result: game.WL || undefined,
              score: scoreDisplay,
              status: game.WL ? 'completed' : 'upcoming',
              tv_broadcast: game.TV_BROADCAST || 'TBD',
              arena: game.ARENA || 'TBD',
              time: game.GAME_TIME || 'TBD'
            };
          });

          setScheduleData(transformedSchedule);
        } else {
          // Fallback to mock data if no real data available
          console.warn('No schedule data provided, using mock data');

          // Fallback to mock data
          const mockSchedule: Game[] = [
          {
            game_id: "0022400001",
            game_date: "2024-01-15",
            matchup: "vs LAL",
            opponent: "Los Angeles Lakers",
            home: true,
            result: "W",
            score: "118-112",
            status: "completed",
            tv_broadcast: "ESPN",
            arena: "TD Garden",
            time: "7:30 PM"
          },
          {
            game_id: "0022400002",
            game_date: "2024-01-17",
            matchup: "@ LAL",
            opponent: "Los Angeles Lakers",
            home: false,
            result: "L",
            score: "108-115",
            status: "completed",
            tv_broadcast: "TNT",
            arena: "Crypto.com Arena",
            time: "8:00 PM"
          },
          {
            game_id: "0022400003",
            game_date: "2024-01-20",
            matchup: "vs MIA",
            opponent: "Miami Heat",
            home: true,
            status: "upcoming",
            tv_broadcast: "NBA TV",
            arena: "TD Garden",
            time: "7:30 PM"
          }
          ];

          setScheduleData(mockSchedule);
        }
      } catch (err) {
        console.error('Error processing schedule data:', err);
        setError('Failed to load schedule data');
      } finally {
        setLoading(false);
      }
    };

    processScheduleData();
  }, [teamId, season, schedule]);

  const refreshData = () => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 1000));
        setError(null);
      } catch (err) {
        setError('Failed to refresh data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  };

  const filteredGames = scheduleData.filter(game => {
    switch (filter) {
      case "home":
        return game.home;
      case "away":
        return !game.home;
      case "completed":
        return game.status === "completed";
      case "upcoming":
        return game.status === "upcoming";
      default:
        return true;
    }
  });

  const getResultBadge = (game: Game) => {
    if (game.status === "upcoming") {
      return <Badge variant="outline">Upcoming</Badge>;
    }
    if (game.status === "live") {
      return <Badge variant="default" className="bg-red-500">Live</Badge>;
    }
    if (game.result === "W") {
      return <Badge variant="default" className="bg-green-500">W</Badge>;
    }
    return <Badge variant="destructive">L</Badge>;
  };

  const getScheduleStats = () => {
    const completed = scheduleData.filter(g => g.status === "completed");
    const wins = completed.filter(g => g.result === "W").length;
    const losses = completed.filter(g => g.result === "L").length;
    const homeGames = scheduleData.filter(g => g.home).length;
    const awayGames = scheduleData.filter(g => !g.home).length;
    const upcoming = scheduleData.filter(g => g.status === "upcoming").length;

    return { wins, losses, homeGames, awayGames, upcoming, total: scheduleData.length };
  };

  const stats = getScheduleStats();

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-10 w-[180px]" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
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
          <h2 className="text-xl font-semibold">Team Schedule</h2>
          {error && (
            <Badge variant="destructive" className="text-xs">
              <AlertTriangle className="w-3 h-3 mr-1" />
              {error}
            </Badge>
          )}
          <Badge variant="secondary" className="text-xs">
            <Calendar className="w-3 h-3 mr-1" />
            {stats.total} Games
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
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Filter games" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Games</SelectItem>
              <SelectItem value="home">Home</SelectItem>
              <SelectItem value="away">Away</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="upcoming">Upcoming</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Schedule Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Record</p>
                <p className="text-2xl font-bold">{stats.wins}-{stats.losses}</p>
              </div>
              <Trophy className="w-8 h-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Home Games</p>
                <p className="text-2xl font-bold">{stats.homeGames}</p>
              </div>
              <Users className="w-8 h-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Away Games</p>
                <p className="text-2xl font-bold">{stats.awayGames}</p>
              </div>
              <MapPin className="w-8 h-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Upcoming</p>
                <p className="text-2xl font-bold">{stats.upcoming}</p>
              </div>
              <Clock className="w-8 h-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Schedule Table */}
      <Card>
        <CardHeader>
          <CardTitle>Games Schedule</CardTitle>
          <CardDescription>
            {filter === "all" ? "All games" : `${filter} games`} for {season} season
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Matchup</TableHead>
                  <TableHead>Opponent</TableHead>
                  <TableHead>Result</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Time/TV</TableHead>
                  <TableHead>Arena</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredGames.map((game) => (
                  <TableRow key={game.game_id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-muted-foreground" />
                        {new Date(game.game_date).toLocaleDateString()}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {game.home ? (
                          <Users className="w-4 h-4 text-blue-500" />
                        ) : (
                          <MapPin className="w-4 h-4 text-orange-500" />
                        )}
                        <span className="font-medium">{game.matchup}</span>
                      </div>
                    </TableCell>
                    <TableCell>{game.opponent}</TableCell>
                    <TableCell>{getResultBadge(game)}</TableCell>
                    <TableCell>
                      {game.score ? (
                        <span className={cn(
                          "font-medium",
                          game.result === "W" ? "text-green-600" : "text-red-600"
                        )}>
                          {game.score}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        {game.time && (
                          <div className="flex items-center gap-1 text-sm">
                            <Clock className="w-3 h-3" />
                            {game.time}
                          </div>
                        )}
                        {game.tv_broadcast && (
                          <Badge variant="outline" className="text-xs">
                            {game.tv_broadcast}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {game.arena}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
