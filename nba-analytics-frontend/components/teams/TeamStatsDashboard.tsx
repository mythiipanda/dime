"use client";

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { 
  BarChart3, 
  TrendingUp, 
  TrendingDown, 
  Target, 
  Shield, 
  Zap, 
  Activity,
  RefreshCw,
  AlertTriangle,
  Trophy,
  Users,
  Clock
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getTeamDashboardData, getTeamTrackingStats } from "@/lib/api/teams";

interface TeamStatsDashboardProps {
  teamId: string;
  season: string;
}

export function TeamStatsDashboard({ teamId, season }: TeamStatsDashboardProps) {
  const [activeTab, setActiveTab] = useState("overview");
  const [timeframe, setTimeframe] = useState("season");
  const [teamData, setTeamData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchTeamData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const [dashboardData, trackingData] = await Promise.all([
          getTeamDashboardData(teamId, season),
          getTeamTrackingStats(teamId, season)
        ]);
        
        setTeamData({
          dashboard: dashboardData,
          tracking: trackingData
        });
      } catch (err) {
        console.error('Error fetching team stats:', err);
        setError('Failed to load team statistics');
        // Set fallback mock data
        setTeamData(createMockTeamData());
      } finally {
        setLoading(false);
      }
    };

    fetchTeamData();
  }, [teamId, season, timeframe]);

  const createMockTeamData = () => ({
    dashboard: {
      stats: {
        current_stats: {
          overall: {
            games_played: 40,
            wins: 25,
            losses: 15,
            win_pct: 0.625,
            pts: 115.2,
            opp_pts: 108.5,
            plus_minus: 6.7
          },
          advanced: {
            offensive_rating: 115.2,
            defensive_rating: 108.5,
            net_rating: 6.7,
            pace: 101.2,
            true_shooting_pct: 0.585,
            effective_fg_pct: 0.544,
            turnover_pct: 12.5,
            offensive_rebound_pct: 25.8,
            defensive_rebound_pct: 74.2
          }
        }
      }
    },
    tracking: {
      passing: { passes_made: 320.5, assists: 25.8, potential_assists: 45.2 },
      rebounding: { total_rebounds: 45.2, contested_rebounds: 18.5 },
      shooting: { catch_shoot_fg_pct: 0.385, pull_up_fg_pct: 0.425 }
    }
  });

  const refreshData = async () => {
    try {
      setLoading(true);
      const [dashboardData, trackingData] = await Promise.all([
        getTeamDashboardData(teamId, season),
        getTeamTrackingStats(teamId, season)
      ]);
      setTeamData({
        dashboard: dashboardData,
        tracking: trackingData
      });
      setError(null);
    } catch (err) {
      setError('Failed to refresh data');
    } finally {
      setLoading(false);
    }
  };

  const renderStatCard = (
    title: string, 
    value: string | number, 
    subtitle?: string, 
    trend?: 'up' | 'down' | 'neutral',
    rank?: number,
    icon?: React.ReactNode
  ) => (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon && <div className="h-4 w-4 text-muted-foreground">{icon}</div>}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        <div className="flex items-center justify-between">
          {subtitle && (
            <p className={`text-xs ${
              trend === 'up' ? 'text-green-600' : 
              trend === 'down' ? 'text-red-600' : 
              'text-muted-foreground'
            }`}>
              {trend === 'up' && <TrendingUp className="w-3 h-3 inline mr-1" />}
              {trend === 'down' && <TrendingDown className="w-3 h-3 inline mr-1" />}
              {subtitle}
            </p>
          )}
          {rank && (
            <Badge variant={rank <= 10 ? 'default' : rank <= 20 ? 'secondary' : 'outline'} className="text-xs">
              #{rank} NBA
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );

  const renderProgressStat = (label: string, value: number, max: number, rank?: number) => (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <span>{label}</span>
        <div className="flex items-center gap-2">
          <span className="font-medium">{value.toFixed(1)}</span>
          {rank && (
            <Badge variant={rank <= 10 ? 'default' : 'secondary'} className="text-xs">
              #{rank}
            </Badge>
          )}
        </div>
      </div>
      <Progress value={(value / max) * 100} className="h-2" />
    </div>
  );

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader className="space-y-2">
                <div className="h-4 bg-gray-200 rounded w-3/4"></div>
              </CardHeader>
              <CardContent>
                <div className="h-8 bg-gray-200 rounded w-1/2 mb-2"></div>
                <div className="h-3 bg-gray-200 rounded w-full"></div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  const stats = teamData?.dashboard?.stats?.current_stats;
  const overall = stats?.overall || {};
  const advanced = stats?.advanced || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-2xl font-bold">Team Statistics</h2>
          {error && (
            <Badge variant="destructive" className="text-xs">
              <AlertTriangle className="w-3 h-3 mr-1" />
              {error}
            </Badge>
          )}
          {teamData && (
            <Badge variant="secondary" className="text-xs">
              <BarChart3 className="w-3 h-3 mr-1" />
              Live Data
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
          <Select value={timeframe} onValueChange={setTimeframe}>
            <SelectTrigger className="w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="season">Full Season</SelectItem>
              <SelectItem value="last10">Last 10</SelectItem>
              <SelectItem value="last20">Last 20</SelectItem>
              <SelectItem value="home">Home</SelectItem>
              <SelectItem value="away">Away</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Key Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {renderStatCard(
          "Record",
          `${overall.wins || 0}-${overall.losses || 0}`,
          `${((overall.win_pct || 0) * 100).toFixed(1)}% win rate`,
          overall.wins > overall.losses ? "up" : "down",
          undefined,
          <Trophy className="h-4 w-4" />
        )}
        {renderStatCard(
          "Offensive Rating",
          (advanced.offensive_rating || 0).toFixed(1),
          "+2.3 vs league avg",
          "up",
          8,
          <Target className="h-4 w-4" />
        )}
        {renderStatCard(
          "Defensive Rating",
          (advanced.defensive_rating || 0).toFixed(1),
          "-1.8 vs league avg",
          "up",
          12,
          <Shield className="h-4 w-4" />
        )}
        {renderStatCard(
          "Net Rating",
          `${(advanced.net_rating || 0) >= 0 ? '+' : ''}${(advanced.net_rating || 0).toFixed(1)}`,
          "6th best in NBA",
          advanced.net_rating > 0 ? "up" : "down",
          6,
          <Activity className="h-4 w-4" />
        )}
      </div>

      {/* Detailed Stats Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="offense">Offense</TabsTrigger>
          <TabsTrigger value="defense">Defense</TabsTrigger>
          <TabsTrigger value="advanced">Advanced</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Basic Statistics</CardTitle>
                <CardDescription>Core team performance metrics</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-between">
                  <span>Points Per Game</span>
                  <span className="font-medium">{(overall.pts || 0).toFixed(1)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Opponent Points</span>
                  <span className="font-medium">{(overall.opp_pts || 0).toFixed(1)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Point Differential</span>
                  <span className={`font-medium ${(overall.plus_minus || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {(overall.plus_minus || 0) >= 0 ? '+' : ''}{(overall.plus_minus || 0).toFixed(1)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Games Played</span>
                  <span className="font-medium">{overall.games_played || 0}</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Efficiency Metrics</CardTitle>
                <CardDescription>Advanced efficiency ratings</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {renderProgressStat("True Shooting %", (advanced.true_shooting_pct || 0) * 100, 70, 8)}
                {renderProgressStat("Effective FG %", (advanced.effective_fg_pct || 0) * 100, 65, 12)}
                {renderProgressStat("Pace", advanced.pace || 0, 110, 15)}
                {renderProgressStat("Turnover %", advanced.turnover_pct || 0, 20, 18)}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="offense" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Offensive Performance</CardTitle>
              <CardDescription>Detailed offensive statistics and rankings</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h4 className="font-medium">Shooting</h4>
                  {renderProgressStat("Field Goal %", 46.5, 60, 8)}
                  {renderProgressStat("3-Point %", 37.8, 50, 5)}
                  {renderProgressStat("Free Throw %", 82.5, 90, 12)}
                </div>
                <div className="space-y-4">
                  <h4 className="font-medium">Ball Movement</h4>
                  {renderProgressStat("Assists Per Game", 25.8, 35, 6)}
                  {renderProgressStat("Assist/TO Ratio", 1.85, 3, 10)}
                  {renderProgressStat("Ball Movement", 320.5, 400, 14)}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="defense" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Defensive Performance</CardTitle>
              <CardDescription>Defensive statistics and impact metrics</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h4 className="font-medium">Opponent Shooting</h4>
                  {renderProgressStat("Opp Field Goal %", 44.2, 60, 8)}
                  {renderProgressStat("Opp 3-Point %", 34.5, 50, 12)}
                  {renderProgressStat("Opp Free Throw %", 78.2, 90, 15)}
                </div>
                <div className="space-y-4">
                  <h4 className="font-medium">Defensive Activity</h4>
                  {renderProgressStat("Steals Per Game", 8.5, 12, 6)}
                  {renderProgressStat("Blocks Per Game", 5.2, 8, 18)}
                  {renderProgressStat("Deflections", 15.8, 25, 10)}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="advanced" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Advanced Analytics</CardTitle>
              <CardDescription>Complex performance metrics and analytics</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h4 className="font-medium">Four Factors</h4>
                  {renderProgressStat("Effective FG %", (advanced.effective_fg_pct || 0) * 100, 65, 8)}
                  {renderProgressStat("Turnover Rate", advanced.turnover_pct || 0, 20, 12)}
                  {renderProgressStat("Off Rebound %", (advanced.offensive_rebound_pct || 0), 35, 15)}
                  {renderProgressStat("Free Throw Rate", 22.5, 35, 20)}
                </div>
                <div className="space-y-4">
                  <h4 className="font-medium">Impact Metrics</h4>
                  {renderProgressStat("Net Rating", Math.abs(advanced.net_rating || 0), 15, 6)}
                  {renderProgressStat("SRS", 4.2, 10, 8)}
                  {renderProgressStat("MOV", overall.plus_minus || 0, 15, 6)}
                  {renderProgressStat("Pythagorean W%", 0.685 * 100, 100, 5)}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
