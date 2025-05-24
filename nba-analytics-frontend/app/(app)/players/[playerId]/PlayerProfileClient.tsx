"use client";

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Target,
  Activity,
  Calendar,
  MapPin,
  Users,
  Trophy,
  Zap,
  GitCompare,
  ExternalLink,
  Star,
  AlertTriangle
} from "lucide-react";
import Link from "next/link";
import { PlayerProfile, PlayerGameLog, PlayerTrend } from "@/models/stats/PlayerStats";
import { PlayerShotChart } from "@/components/players/PlayerShotChart";
import { AdvancedAnalyticsDashboard } from "@/components/analytics/AdvancedAnalyticsDashboard";
import {
  getPlayerProfile,
  getPlayerGameLog,
  getPlayerShotChart,
  getPlayerStats,
  getPlayerTrackingStats,
  getPlayerClutchStats,
  getPlayerHustleStats
} from "@/lib/api/players";

interface PlayerProfileClientProps {
  playerId: string;
  season: string;
  initialTab: string;
}

export default function PlayerProfileClient({ playerId, season, initialTab }: PlayerProfileClientProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState(initialTab);
  const [playerData, setPlayerData] = useState<PlayerProfile | null>(null);
  const [gameLog, setGameLog] = useState<PlayerGameLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPlayerData = async () => {
      try {
        setLoading(true);
        setError(null);

        const [profile, games, shotChart, trackingStats, clutchStats, hustleStats] = await Promise.all([
          getPlayerProfile(playerId, season),
          getPlayerGameLog(playerId, season),
          getPlayerShotChart(playerId, season),
          getPlayerTrackingStats(playerId, season),
          getPlayerClutchStats(playerId, season),
          getPlayerHustleStats(playerId, season)
        ]);

        // Combine all data sources
        const enhancedProfile = {
          ...profile,
          shotChart,
          tracking: trackingStats,
          clutch: clutchStats,
          hustle: hustleStats
        };

        setPlayerData(enhancedProfile);
        setGameLog(games);
      } catch (err) {
        console.error('Error fetching player data:', err);
        setError('Failed to load player data');

        // Set mock data as fallback
        setPlayerData(createMockPlayerProfile(playerId));
        setGameLog(createMockGameLog());
      } finally {
        setLoading(false);
      }
    };

    fetchPlayerData();
  }, [playerId, season]);

  const createMockPlayerProfile = (id: string): PlayerProfile => ({
    bio: {
      player_id: parseInt(id),
      player_name: "Sample Player",
      first_name: "Sample",
      last_name: "Player",
      display_first_last: "Sample Player",
      display_last_comma_first: "Player, Sample",
      display_fi_last: "S. Player",
      birthdate: "1995-01-01",
      school: "Sample University",
      country: "USA",
      last_affiliation: "Sample University",
      height: "6-6",
      weight: "220",
      season_exp: 5,
      jersey: "23",
      position: "SF",
      rosterstatus: "Active",
      team_id: 1610612744,
      team_name: "Golden State Warriors",
      team_abbreviation: "GSW",
      team_code: "warriors",
      team_city: "Golden State",
      playercode: "sample_player",
      from_year: 2019,
      to_year: 2024,
      dleague_flag: "N",
      nba_flag: "Y",
      games_played_flag: "Y",
      draft_year: "2019",
      draft_round: "1",
      draft_number: "15"
    },
    basic_stats: {
      games_played: 65,
      minutes_per_game: 32.5,
      points_per_game: 18.7,
      rebounds_per_game: 6.2,
      assists_per_game: 4.1,
      steals_per_game: 1.3,
      blocks_per_game: 0.8,
      turnovers_per_game: 2.4,
      field_goal_percentage: 0.465,
      three_point_percentage: 0.378,
      free_throw_percentage: 0.825,
      field_goals_made: 6.8,
      field_goals_attempted: 14.6,
      three_pointers_made: 2.3,
      three_pointers_attempted: 6.1,
      free_throws_made: 3.1,
      free_throws_attempted: 3.8
    },
    advanced_stats: {
      player_efficiency_rating: 18.5,
      true_shooting_percentage: 0.582,
      effective_field_goal_percentage: 0.544,
      usage_rate: 0.235,
      assist_percentage: 0.185,
      rebound_percentage: 0.142,
      steal_percentage: 0.021,
      block_percentage: 0.018,
      turnover_percentage: 0.125,
      offensive_rating: 115.2,
      defensive_rating: 108.7,
      net_rating: 6.5,
      box_plus_minus: 3.2,
      value_over_replacement: 2.8,
      win_shares: 7.2,
      win_shares_per_48: 0.185
    },
    shooting_stats: {
      restricted_area_fg_pct: 0.685,
      in_paint_non_ra_fg_pct: 0.425,
      mid_range_fg_pct: 0.398,
      left_corner_3_fg_pct: 0.412,
      right_corner_3_fg_pct: 0.389,
      above_break_3_fg_pct: 0.365,
      backcourt_fg_pct: 0.125,
      shot_chart_data: []
    },
    defensive_stats: {
      defensive_field_goal_percentage: 0.445,
      defensive_rebounds_per_game: 4.8,
      defensive_rating: 108.7,
      steals_per_game: 1.3,
      blocks_per_game: 0.8,
      deflections_per_game: 2.1,
      loose_balls_recovered: 1.2,
      charges_drawn: 0.3,
      contested_shots: 8.5,
      contested_2pt_shots: 5.2,
      contested_3pt_shots: 3.3
    },
    playmaking_stats: {
      assists_per_game: 4.1,
      potential_assists: 7.8,
      assist_percentage: 0.185,
      assist_to_turnover_ratio: 1.71,
      secondary_assists: 1.8,
      passes_made: 45.2,
      passes_received: 38.7,
      screen_assists: 2.1,
      screen_assist_points: 4.8
    },
    rebounding_stats: {
      total_rebounds_per_game: 6.2,
      offensive_rebounds_per_game: 1.4,
      defensive_rebounds_per_game: 4.8,
      rebound_percentage: 0.142,
      offensive_rebound_percentage: 0.058,
      defensive_rebound_percentage: 0.185,
      contested_rebounds: 3.2,
      uncontested_rebounds: 3.0,
      rebound_chances: 8.5
    },
    season: season,
    last_updated: new Date().toISOString()
  });

  const createMockGameLog = (): PlayerGameLog[] => [
    {
      game_id: "0022400001",
      game_date: "2024-01-15",
      matchup: "GSW vs. LAL",
      wl: "W",
      min: 35,
      pts: 24,
      reb: 7,
      ast: 5,
      stl: 2,
      blk: 1,
      tov: 3,
      fg_pct: 0.520,
      fg3_pct: 0.400,
      ft_pct: 0.857,
      plus_minus: 12,
      video_available: true
    },
    {
      game_id: "0022400002",
      game_date: "2024-01-12",
      matchup: "GSW @ BOS",
      wl: "L",
      min: 32,
      pts: 16,
      reb: 5,
      ast: 3,
      stl: 1,
      blk: 0,
      tov: 4,
      fg_pct: 0.385,
      fg3_pct: 0.250,
      ft_pct: 0.750,
      plus_minus: -8,
      video_available: true
    }
  ];

  if (loading) {
    return <PlayerProfileSkeleton />;
  }

  if (error || !playerData) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center gap-4 mb-6">
          <Link href="/players">
            <Button variant="outline" size="sm">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Players
            </Button>
          </Link>
        </div>
        <Card className="p-6 text-center">
          <div className="space-y-4">
            <AlertTriangle className="w-12 h-12 text-red-500 mx-auto" />
            <h3 className="text-lg font-semibold">Unable to load player data</h3>
            <p className="text-muted-foreground">{error || 'Player not found'}</p>
            <Link href="/players">
              <Button>Return to Players</Button>
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  const renderStatCard = (title: string, value: string | number, subtitle?: string, trend?: 'up' | 'down' | 'neutral', icon?: React.ReactNode) => (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon && <div className="h-4 w-4 text-muted-foreground">{icon}</div>}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {subtitle && (
          <p className={`text-xs ${
            trend === 'up' ? 'text-green-600' :
            trend === 'down' ? 'text-red-600' :
            'text-muted-foreground'
          }`}>
            {subtitle}
          </p>
        )}
      </CardContent>
    </Card>
  );

  return (
    <div className="container mx-auto px-4 py-8 space-y-6">
      {/* Navigation Header */}
      <div className="flex items-center gap-4">
        <Link href="/players">
          <Button variant="outline" size="sm">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Players
          </Button>
        </Link>
        {error && (
          <Badge variant="destructive" className="text-xs">
            Using fallback data
          </Badge>
        )}
      </div>

      {/* Player Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center gap-6">
        <Avatar className="w-24 h-24 border-4 border-primary/20">
          <AvatarImage
            src={`https://cdn.nba.com/headshots/nba/latest/1040x760/${playerId}.png`}
            alt={playerData.bio.player_name}
          />
          <AvatarFallback className="text-2xl font-bold">
            {playerData.bio.first_name[0]}{playerData.bio.last_name[0]}
          </AvatarFallback>
        </Avatar>

        <div className="space-y-2">
          <h1 className="text-3xl font-bold">{playerData.bio.player_name}</h1>
          <div className="flex flex-wrap items-center gap-4 text-muted-foreground">
            <div className="flex items-center gap-1">
              <Users className="w-4 h-4" />
              <span>{playerData.bio.team_name}</span>
            </div>
            <div className="flex items-center gap-1">
              <Badge variant="outline">#{playerData.bio.jersey}</Badge>
              <span>{playerData.bio.position}</span>
            </div>
            <div className="flex items-center gap-1">
              <MapPin className="w-4 h-4" />
              <span>{playerData.bio.height}, {playerData.bio.weight} lbs</span>
            </div>
            <div className="flex items-center gap-1">
              <Calendar className="w-4 h-4" />
              <span>{playerData.bio.season_exp} years exp</span>
            </div>
          </div>
          <div className="flex gap-2">
            <Badge variant="secondary">{playerData.bio.school}</Badge>
            <Badge variant="outline">Draft: {playerData.bio.draft_year} Rd {playerData.bio.draft_round}</Badge>
          </div>
        </div>

        <div className="ml-auto flex gap-2">
          <Button variant="outline" size="sm">
            <GitCompare className="w-4 h-4 mr-2" />
            Compare
          </Button>
          <Button variant="outline" size="sm">
            <ExternalLink className="w-4 h-4 mr-2" />
            NBA.com
          </Button>
        </div>
      </div>

      {/* Key Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {renderStatCard(
          "Points Per Game",
          playerData.basic_stats.points_per_game.toFixed(1),
          "+2.3 from last season",
          "up",
          <Target className="h-4 w-4" />
        )}
        {renderStatCard(
          "Rebounds Per Game",
          playerData.basic_stats.rebounds_per_game.toFixed(1),
          "League rank: 45th",
          "neutral",
          <Activity className="h-4 w-4" />
        )}
        {renderStatCard(
          "Assists Per Game",
          playerData.basic_stats.assists_per_game.toFixed(1),
          "+0.8 from last season",
          "up",
          <Users className="h-4 w-4" />
        )}
        {renderStatCard(
          "Player Efficiency",
          playerData.advanced_stats.player_efficiency_rating.toFixed(1),
          "Above league average",
          "up",
          <BarChart3 className="h-4 w-4" />
        )}
      </div>

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-7">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="stats">Statistics</TabsTrigger>
          <TabsTrigger value="shooting">Shooting</TabsTrigger>
          <TabsTrigger value="defense">Defense</TabsTrigger>
          <TabsTrigger value="games">Game Log</TabsTrigger>
          <TabsTrigger value="advanced">Advanced</TabsTrigger>
          <TabsTrigger value="analytics">ML Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          {/* Overview content will be added in the next part */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Season Averages</CardTitle>
                <CardDescription>{season} Regular Season</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex justify-between">
                    <span>Games Played</span>
                    <span className="font-medium">{playerData.basic_stats.games_played}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Minutes</span>
                    <span className="font-medium">{playerData.basic_stats.minutes_per_game.toFixed(1)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Field Goal %</span>
                    <span className="font-medium">{(playerData.basic_stats.field_goal_percentage * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>3-Point %</span>
                    <span className="font-medium">{(playerData.basic_stats.three_point_percentage * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Free Throw %</span>
                    <span className="font-medium">{(playerData.basic_stats.free_throw_percentage * 100).toFixed(1)}%</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Advanced Metrics</CardTitle>
                <CardDescription>Efficiency and impact metrics</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span>True Shooting %</span>
                      <span className="font-medium">{(playerData.advanced_stats.true_shooting_percentage * 100).toFixed(1)}%</span>
                    </div>
                    <Progress value={(playerData.advanced_stats.true_shooting_percentage * 100)} className="h-2" />
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span>Usage Rate</span>
                      <span className="font-medium">{(playerData.advanced_stats.usage_rate * 100).toFixed(1)}%</span>
                    </div>
                    <Progress value={(playerData.advanced_stats.usage_rate * 100)} className="h-2" />
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span>Win Shares</span>
                      <span className="font-medium">{playerData.advanced_stats.win_shares.toFixed(1)}</span>
                    </div>
                    <Progress value={(playerData.advanced_stats.win_shares / 15) * 100} className="h-2" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Other tab contents will be implemented in subsequent parts */}
        <TabsContent value="stats">
          <Card>
            <CardHeader>
              <CardTitle>Detailed Statistics</CardTitle>
            </CardHeader>
            <CardContent>
              <p>Detailed statistics content coming soon...</p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="shooting">
          <PlayerShotChart playerId={playerId} season={season} />
        </TabsContent>

        <TabsContent value="defense">
          <Card>
            <CardHeader>
              <CardTitle>Defensive Metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <p>Defensive metrics content coming soon...</p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="games">
          <Card>
            <CardHeader>
              <CardTitle>Game Log</CardTitle>
              <CardDescription>Recent game performances</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Matchup</TableHead>
                      <TableHead>Result</TableHead>
                      <TableHead className="text-right">MIN</TableHead>
                      <TableHead className="text-right">PTS</TableHead>
                      <TableHead className="text-right">REB</TableHead>
                      <TableHead className="text-right">AST</TableHead>
                      <TableHead className="text-right">FG%</TableHead>
                      <TableHead className="text-right">+/-</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {gameLog.slice(0, 10).map((game, index) => (
                      <TableRow key={game.game_id}>
                        <TableCell>{new Date(game.game_date).toLocaleDateString()}</TableCell>
                        <TableCell>{game.matchup}</TableCell>
                        <TableCell>
                          <Badge variant={game.wl === 'W' ? 'default' : 'destructive'}>
                            {game.wl}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">{game.min}</TableCell>
                        <TableCell className="text-right">{game.pts}</TableCell>
                        <TableCell className="text-right">{game.reb}</TableCell>
                        <TableCell className="text-right">{game.ast}</TableCell>
                        <TableCell className="text-right">{(game.fg_pct * 100).toFixed(1)}%</TableCell>
                        <TableCell className={`text-right ${game.plus_minus >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {game.plus_minus >= 0 ? '+' : ''}{game.plus_minus}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="advanced">
          <Card>
            <CardHeader>
              <CardTitle>Advanced Analytics</CardTitle>
            </CardHeader>
            <CardContent>
              <p>Advanced analytics content coming soon...</p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="analytics">
          <AdvancedAnalyticsDashboard
            playerId={playerId}
            season={season}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function PlayerProfileSkeleton() {
  return (
    <div className="container mx-auto px-4 py-8 space-y-6">
      {/* Navigation skeleton */}
      <div className="flex items-center gap-4">
        <div className="h-9 w-32 bg-gray-200 rounded animate-pulse" />
      </div>

      {/* Header skeleton */}
      <div className="flex items-center gap-6">
        <div className="w-24 h-24 bg-gray-200 rounded-full animate-pulse" />
        <div className="space-y-2">
          <div className="h-8 w-64 bg-gray-200 rounded animate-pulse" />
          <div className="h-4 w-48 bg-gray-200 rounded animate-pulse" />
          <div className="h-4 w-32 bg-gray-200 rounded animate-pulse" />
        </div>
      </div>

      {/* Stats cards skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="border rounded-lg p-4 space-y-3 animate-pulse">
            <div className="h-4 w-20 bg-gray-200 rounded" />
            <div className="h-8 w-16 bg-gray-200 rounded" />
            <div className="h-3 w-24 bg-gray-200 rounded" />
          </div>
        ))}
      </div>

      {/* Content skeleton */}
      <div className="h-64 w-full bg-gray-200 rounded animate-pulse" />
    </div>
  );
}
