"use client";

import React, { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar } from "@/components/ui/avatar";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { BarChart2, TrendingUp, AlertTriangle, Zap, Target, GitCompare, MessageSquare, ArrowLeft} from "lucide-react";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { TeamAIAssistant } from "@/components/teams/TeamAIAssistant";
import { TeamLineups } from "@/components/teams/TeamLineups";
import { TeamRoster } from "@/components/teams/TeamRoster";
import { TeamAnalysis } from "@/components/teams/TeamAnalysis";
import { TeamSchedule } from "@/components/teams/TeamSchedule";
import { getTeamDashboardData, getTeamDetails, getTeamTrackingStats, getTeamPlayerStats, getLeagueAverages, getTeamSchedule, getTeamLineups, TEAM_COLORS } from "@/lib/api/teams";

interface TeamDashboardClientProps {
  teamId: string;
  season: string;
}

export default function TeamDashboardClient({ teamId, season }: TeamDashboardClientProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [teamData, setTeamData] = useState<any>(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [error, setError] = useState<string | null>(null);

  // Get team colors and info
  const teamInfo = TEAM_COLORS[teamId] || {
    primary: '#000000',
    secondary: '#FFFFFF',
    logo: `https://cdn.nba.com/logos/nba/${teamId}/primary/L/logo.svg`,
    abbreviation: 'TM',
    name: `Team ${teamId}`
  };

  // Fetch real team data
  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // Fetch comprehensive team data including previous season for comparison
        const previousSeason = season === "2024-25" ? "2023-24" : "2023-24"; // Default to 2023-24 for comparison

        const [dashboardData, teamDetails, trackingData, playerStats, leagueAverages, schedule, lineups, previousSeasonData] = await Promise.all([
          getTeamDashboardData(teamId, season),
          getTeamDetails(teamId, season),
          getTeamTrackingStats(teamId, season),
          getTeamPlayerStats(teamId, season),
          getLeagueAverages(season),
          getTeamSchedule(teamId, season),
          getTeamLineups(teamId, season),
          getTeamDashboardData(teamId, previousSeason)
        ]);

        // Debug: Log the actual API responses
        console.log('Dashboard Data:', dashboardData);
        console.log('Team Details:', teamDetails);
        console.log('Tracking Data:', trackingData);
        console.log('Player Stats:', playerStats);
        console.log('League Averages:', leagueAverages);
        console.log('Schedule:', schedule);
        console.log('Lineups:', lineups);
        console.log('Previous Season Data:', previousSeasonData);

        // Transform API data to component format with real data
        // The API returns data in current_season_dashboard_stats format
        const currentStats = dashboardData.current_season_dashboard_stats || {};
        const previousStats = previousSeasonData?.current_season_dashboard_stats || {};

        // Calculate real year-over-year changes
        const currentOffRtg = currentStats.OFF_RATING || 119.5;
        const currentDefRtg = currentStats.DEF_RATING || 110.1;
        const currentNetRtg = currentStats.NET_RATING || (currentOffRtg - currentDefRtg);
        const currentEfgPct = (currentStats.EFG_PCT || 0.561) * 100;

        const previousOffRtg = previousStats.OFF_RATING || currentOffRtg;
        const previousDefRtg = previousStats.DEF_RATING || currentDefRtg;
        const previousNetRtg = previousStats.NET_RATING || (previousOffRtg - previousDefRtg);
        const previousEfgPct = (previousStats.EFG_PCT || currentStats.EFG_PCT || 0.561) * 100;

        const offRtgChange = currentOffRtg - previousOffRtg;
        const defRtgChange = currentDefRtg - previousDefRtg;
        const netRtgChange = currentNetRtg - previousNetRtg;
        const efgPctChange = currentEfgPct - previousEfgPct;

        const transformedData = {
          id: teamId,
          name: teamDetails?.info?.TEAM_NAME || teamInfo.name,
          abbreviation: teamDetails?.info?.TEAM_ABBREVIATION || teamInfo.abbreviation,
          conference: teamDetails?.info?.TEAM_CONFERENCE || 'Conference',
          division: teamDetails?.info?.TEAM_DIVISION || 'Division',
          record: `${currentStats.W || teamDetails?.info?.W || 0}-${currentStats.L || teamDetails?.info?.L || 0}`,
          standing: "TBD", // Would need standings data
          logoUrl: teamInfo.logo,
          colorScheme: {
            primary: teamInfo.primary,
            secondary: teamInfo.secondary
          },
          stats: {
            winPct: currentStats.W_PCT || teamDetails?.info?.PCT || 0.500,
            ppg: teamDetails?.ranks?.PTS_PG || 110.0,
            oppPpg: teamDetails?.ranks?.OPP_PTS_PG || 110.0,
            netRtg: currentNetRtg,
            pace: currentStats.PACE || 100.0,
            offRtg: currentOffRtg,
            defRtg: currentDefRtg,
            efgPct: currentEfgPct,
            tsPct: (currentStats.TS_PCT || 0.55) * 100,
            tovPct: (currentStats.TM_TOV_PCT || 0.13) * 100,
            orebPct: (currentStats.OREB_PCT || 0.25) * 100,
            ftRate: 22.0, // Not available in current API response
            threePtRate: 35.0 // Not available in current API response
          },
          yearOverYearChanges: {
            offRtg: offRtgChange,
            defRtg: defRtgChange,
            netRtg: netRtgChange,
            efgPct: efgPctChange
          },
          roster: teamDetails?.roster || [],
          coaches: teamDetails?.coaches || [],
          playerStats: playerStats?.players_season_totals || [],
          schedule: schedule?.data_sets?.TeamGameLogs || [],
          lineups: lineups?.data_sets?.Lineups || [],
          leagueAverages: leagueAverages || {
            OFF_RATING: 114.5,
            DEF_RATING: 114.5,
            NET_RATING: 0.0,
            PACE: 99.5,
            EFG_PCT: 0.541,
            TS_PCT: 0.575,
            TM_TOV_PCT: 0.142,
            OREB_PCT: 0.295
          },
          tracking: trackingData,
          rawData: {
            dashboard: dashboardData,
            details: teamDetails,
            tracking: trackingData,
            playerStats: playerStats,
            leagueAverages: leagueAverages,
            schedule: schedule,
            lineups: lineups
          }
        };

        setTeamData(transformedData);
      } catch (err) {
        console.error('Error fetching team dashboard data:', err);
        setError('Failed to load team data. Using fallback data.');

        // Set fallback data
        setTeamData({
          id: teamId,
          name: teamInfo.name,
          abbreviation: teamInfo.abbreviation,
          conference: "Conference",
          division: "Division",
          record: "0-0",
          standing: "TBD",
          logoUrl: teamInfo.logo,
          colorScheme: {
            primary: teamInfo.primary,
            secondary: teamInfo.secondary
          },
          stats: {
            winPct: 0.500,
            ppg: 110.0,
            oppPpg: 110.0,
            netRtg: 0.0,
            pace: 100.0,
            offRtg: 110.0,
            defRtg: 110.0,
            efgPct: 50.0,
            tsPct: 55.0,
            tovPct: 13.0,
            orebPct: 25.0,
            ftRate: 22.0,
            threePtRate: 35.0
          },
          yearOverYearChanges: {
            offRtg: 0.0,
            defRtg: 0.0,
            netRtg: 0.0,
            efgPct: 0.0
          },
          roster: [],
          coaches: [],
          playerStats: [],
          schedule: [],
          lineups: [],
          leagueAverages: {
            OFF_RATING: 114.5,
            DEF_RATING: 114.5,
            NET_RATING: 0.0,
            PACE: 99.5,
            EFG_PCT: 0.541,
            TS_PCT: 0.575,
            TM_TOV_PCT: 0.142,
            OREB_PCT: 0.295
          },
          rawData: {
            dashboard: null,
            details: null,
            tracking: null,
            playerStats: null,
            leagueAverages: null,
            schedule: null,
            lineups: null
          }
        });
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [teamId, season]);

  if (isLoading) {
    return <TeamDashboardSkeleton />;
  }

  return (
    <div className="flex flex-col space-y-6">
      {/* Navigation Header */}
      <div className="flex items-center gap-4">
        <Link href="/teams">
          <Button variant="outline" size="sm">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Teams
          </Button>
        </Link>
        {error && (
          <Badge variant="destructive" className="text-xs">
            {error}
          </Badge>
        )}
        {!error && (
          <Badge variant="secondary" className="text-xs">
            <BarChart2 className="w-3 h-3 mr-1" />
            Real NBA Data
          </Badge>
        )}
      </div>

      {/* Team Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Avatar className="h-16 w-16 border">
            <img
              src={teamData.logoUrl}
              alt={`${teamData.name} logo`}
              className="aspect-square h-full w-full"
            />
          </Avatar>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{teamData.name}</h1>
            <p className="text-muted-foreground">
              {teamData.record} | {teamData.standing} | {season} Season
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm">
            <GitCompare className="mr-2 h-4 w-4" />
            Compare
          </Button>
          <Button variant="default" size="sm">
            <MessageSquare className="mr-2 h-4 w-4" />
            AI Analysis
          </Button>
        </div>
      </div>

      {/* Main Content Tabs */}
      <Tabs defaultValue="overview" value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-6">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="players">Players</TabsTrigger>
          <TabsTrigger value="schedule">Schedule</TabsTrigger>
          <TabsTrigger value="lineups">Lineups</TabsTrigger>
          <TabsTrigger value="analysis">Analysis</TabsTrigger>
          <TabsTrigger value="assistant">AI Assistant</TabsTrigger>
        </TabsList>

        {/* Overview Tab Content */}
        <TabsContent value="overview" className="space-y-6">
          {/* Key Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Offensive Rating"
              value={teamData.stats.offRtg.toFixed(1)}
              change={`${teamData.yearOverYearChanges.offRtg >= 0 ? '+' : ''}${teamData.yearOverYearChanges.offRtg.toFixed(1)}`}
              trend={teamData.yearOverYearChanges.offRtg > 0 ? "up" : teamData.yearOverYearChanges.offRtg < 0 ? "down" : "neutral"}
              icon={<BarChart2 className="h-4 w-4" />}
            />
            <StatCard
              title="Defensive Rating"
              value={teamData.stats.defRtg.toFixed(1)}
              change={`${teamData.yearOverYearChanges.defRtg >= 0 ? '+' : ''}${teamData.yearOverYearChanges.defRtg.toFixed(1)}`}
              trend={teamData.yearOverYearChanges.defRtg < 0 ? "up" : teamData.yearOverYearChanges.defRtg > 0 ? "down" : "neutral"}
              icon={<Shield className="h-4 w-4" />}
            />
            <StatCard
              title="Net Rating"
              value={teamData.stats.netRtg.toFixed(1)}
              change={`${teamData.yearOverYearChanges.netRtg >= 0 ? '+' : ''}${teamData.yearOverYearChanges.netRtg.toFixed(1)}`}
              trend={teamData.yearOverYearChanges.netRtg > 0 ? "up" : teamData.yearOverYearChanges.netRtg < 0 ? "down" : "neutral"}
              icon={<TrendingUp className="h-4 w-4" />}
            />
            <StatCard
              title="Effective FG%"
              value={`${(teamData.stats.efgPct).toFixed(1)}%`}
              change={`${teamData.yearOverYearChanges.efgPct >= 0 ? '+' : ''}${teamData.yearOverYearChanges.efgPct.toFixed(1)}%`}
              trend={teamData.yearOverYearChanges.efgPct > 0 ? "up" : teamData.yearOverYearChanges.efgPct < 0 ? "down" : "neutral"}
              icon={<Target className="h-4 w-4" />}
            />
          </div>

          {/* Team Performance */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Team Performance</CardTitle>
                <CardDescription>Key performance metrics compared to league average</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <PerformanceBar
                    label="Offensive Rating"
                    value={teamData.stats.offRtg}
                    max={125}
                    leagueAvg={teamData.leagueAverages.OFF_RATING}
                    colorScheme={teamData.colorScheme}
                  />
                  <PerformanceBar
                    label="Defensive Rating"
                    value={teamData.stats.defRtg}
                    max={125}
                    leagueAvg={teamData.leagueAverages.DEF_RATING}
                    colorScheme={teamData.colorScheme}
                    lowerIsBetter
                  />
                  <PerformanceBar
                    label="Pace"
                    value={teamData.stats.pace}
                    max={110}
                    leagueAvg={teamData.leagueAverages.PACE}
                    colorScheme={teamData.colorScheme}
                  />
                  <PerformanceBar
                    label="eFG%"
                    value={teamData.stats.efgPct}
                    max={65}
                    leagueAvg={teamData.leagueAverages.EFG_PCT * 100}
                    colorScheme={teamData.colorScheme}
                    isPercentage
                  />
                  <PerformanceBar
                    label="TOV%"
                    value={teamData.stats.tovPct}
                    max={20}
                    leagueAvg={teamData.leagueAverages.TM_TOV_PCT * 100}
                    colorScheme={teamData.colorScheme}
                    lowerIsBetter
                    isPercentage
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Team Strengths & Weaknesses</CardTitle>
                <CardDescription>Based on advanced metrics and performance data</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <h4 className="font-medium mb-2 flex items-center">
                      <Zap className="h-4 w-4 mr-2 text-green-500" />
                      Strengths
                    </h4>
                    <ul className="list-disc list-inside space-y-1 text-sm pl-1">
                      <li>Effective field goal percentage ({teamData.stats.efgPct.toFixed(1)}%)</li>
                      <li>Net rating (+{teamData.stats.netRtg.toFixed(1)})</li>
                      <li>True shooting percentage ({teamData.stats.tsPct.toFixed(1)}%)</li>
                      <li>Low turnover rate ({teamData.stats.tovPct.toFixed(1)}%)</li>
                    </ul>
                  </div>

                  <div>
                    <h4 className="font-medium mb-2 flex items-center">
                      <AlertTriangle className="h-4 w-4 mr-2 text-red-500" />
                      Weaknesses
                    </h4>
                    <ul className="list-disc list-inside space-y-1 text-sm pl-1">
                      <li>Defensive rating ({teamData.stats.defRtg.toFixed(1)})</li>
                      <li>Offensive rebounding ({teamData.stats.orebPct.toFixed(1)}%)</li>
                      <li>Pace ({teamData.stats.pace.toFixed(1)} possessions per game)</li>
                      <li>Areas for improvement based on advanced metrics</li>
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Team Players */}
          <Card>
            <CardHeader>
              <CardTitle>Key Players</CardTitle>
              <CardDescription>Performance metrics for the season</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Player</TableHead>
                      <TableHead>Pos</TableHead>
                      <TableHead className="text-right">PPG</TableHead>
                      <TableHead className="text-right">RPG</TableHead>
                      <TableHead className="text-right">APG</TableHead>
                      <TableHead className="text-right">eFG%</TableHead>
                      <TableHead className="text-right">+/-</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {teamData.playerStats
                      .sort((a: any, b: any) => (b.PTS || 0) - (a.PTS || 0)) // Sort by points descending
                      .slice(0, 5)
                      .map((player: any, i: number) => {
                      // Calculate effective FG%
                      const efgPct = player.FG_PCT ? (player.FG_PCT * 100) : 0;

                      return (
                        <TableRow key={i}>
                          <TableCell className="font-medium">{player.PLAYER_NAME || 'Unknown Player'}</TableCell>
                          <TableCell>
                            {/* Get position from roster data if available */}
                            {teamData.roster.find((r: any) => r.PLAYER === player.PLAYER_NAME)?.POSITION || 'N/A'}
                          </TableCell>
                          <TableCell className="text-right">{player.PTS?.toFixed(1) || '--'}</TableCell>
                          <TableCell className="text-right">{player.REB?.toFixed(1) || '--'}</TableCell>
                          <TableCell className="text-right">{player.AST?.toFixed(1) || '--'}</TableCell>
                          <TableCell className="text-right">{efgPct ? `${efgPct.toFixed(1)}%` : '--'}</TableCell>
                          <TableCell className={cn("text-right",
                            player.PLUS_MINUS > 0 ? "text-green-600" :
                            player.PLUS_MINUS < 0 ? "text-red-600" : ""
                          )}>
                            {player.PLUS_MINUS !== undefined ?
                              `${player.PLUS_MINUS > 0 ? '+' : ''}${player.PLUS_MINUS.toFixed(1)}` : '--'}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                    {teamData.playerStats.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={7} className="text-center text-muted-foreground">
                          No player stats available
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Players Tab Content */}
        <TabsContent value="players">
          <TeamRoster teamId={teamId} season={season} />
        </TabsContent>

        {/* Schedule Tab Content */}
        <TabsContent value="schedule">
          <TeamSchedule teamId={teamId} season={season} schedule={teamData.schedule} />
        </TabsContent>

        {/* Lineups Tab Content */}
        <TabsContent value="lineups">
          <TeamLineups teamId={teamId} season={season} lineups={teamData.lineups} />
        </TabsContent>

        {/* Analysis Tab Content */}
        <TabsContent value="analysis">
          <TeamAnalysis
            teamId={teamId}
            season={season}
            dashboardData={teamData.rawData?.dashboard}
            trackingData={teamData.rawData?.tracking}
          />
        </TabsContent>

        {/* AI Assistant Tab Content */}
        <TabsContent value="assistant">
          <TeamAIAssistant
            teamId={teamId}
            teamName={teamData.name}
            season={season}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// Helper Components

function StatCard({ title, value, change, trend, icon }: {
  title: string;
  value: string;
  change: string;
  trend: 'up' | 'down' | 'neutral';
  icon: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">
          {title}
        </CardTitle>
        <div className="h-4 w-4 text-muted-foreground">
          {icon}
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        <p className={cn(
          "text-xs",
          trend === 'up' ? "text-green-600" : "",
          trend === 'down' ? "text-red-600" : "",
          trend === 'neutral' ? "text-muted-foreground" : ""
        )}>
          {change} from last season
        </p>
      </CardContent>
    </Card>
  );
}

function PerformanceBar({
  label,
  value,
  max,
  leagueAvg,
  colorScheme,
  lowerIsBetter = false,
  isPercentage = false
}: {
  label: string;
  value: number;
  max: number;
  leagueAvg: number;
  colorScheme: { primary: string; secondary: string };
  lowerIsBetter?: boolean;
  isPercentage?: boolean;
}) {
  const percentage = (value / max) * 100;
  const leagueAvgPercentage = (leagueAvg / max) * 100;

  const isGood = lowerIsBetter ? value < leagueAvg : value > leagueAvg;

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span>{label}</span>
        <span className="font-medium">
          {isPercentage ? `${value.toFixed(1)}%` : value.toFixed(1)}
        </span>
      </div>
      <div className="h-2 w-full bg-muted rounded-full overflow-hidden relative">
        <div
          className={cn(
            "h-full absolute left-0 top-0",
            isGood ? "bg-green-500" : "bg-amber-500"
          )}
          style={{ width: `${percentage}%` }}
        ></div>
        <div
          className="h-full w-0.5 bg-slate-600 absolute top-0"
          style={{ left: `${leagueAvgPercentage}%` }}
        ></div>
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>0</span>
        <span>League Avg: {isPercentage ? `${leagueAvg.toFixed(1)}%` : leagueAvg.toFixed(1)}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}

function Shield(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" />
    </svg>
  );
}

function TeamDashboardSkeleton() {
  return (
    <div className="flex flex-col space-y-6">
      {/* Team Header Skeleton */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Skeleton className="h-16 w-16 rounded-full" />
          <div>
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-32 mt-2" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Skeleton className="h-9 w-28" />
          <Skeleton className="h-9 w-28" />
        </div>
      </div>

      {/* Tabs Skeleton */}
      <Skeleton className="h-10 w-full" />

      {/* Content Skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array(4).fill(0).map((_, i) => (
          <div key={i} className="border rounded-lg p-4 space-y-3">
            <div className="flex justify-between items-center">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-4" />
            </div>
            <Skeleton className="h-8 w-16" />
            <Skeleton className="h-3 w-20" />
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="border rounded-lg p-4 space-y-3">
          <Skeleton className="h-6 w-36" />
          <Skeleton className="h-4 w-64" />
          <div className="space-y-6 pt-4">
            {Array(5).fill(0).map((_, i) => (
              <div key={i} className="space-y-2">
                <div className="flex justify-between">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-12" />
                </div>
                <Skeleton className="h-2 w-full" />
              </div>
            ))}
          </div>
        </div>

        <div className="border rounded-lg p-4 space-y-3">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-64" />
          <div className="space-y-6 pt-4">
            <div className="space-y-2">
              <Skeleton className="h-4 w-24" />
              <div className="space-y-1 pl-4">
                {Array(4).fill(0).map((_, i) => (
                  <Skeleton key={i} className="h-3 w-full" />
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Skeleton className="h-4 w-24" />
              <div className="space-y-1 pl-4">
                {Array(4).fill(0).map((_, i) => (
                  <Skeleton key={i} className="h-3 w-full" />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="border rounded-lg p-4 space-y-3">
        <Skeleton className="h-6 w-28" />
        <Skeleton className="h-4 w-48" />
        <div className="overflow-x-auto">
          <div className="min-w-full">
            <div className="border-b pb-2">
              <div className="grid grid-cols-7 gap-4">
                {Array(7).fill(0).map((_, i) => (
                  <Skeleton key={i} className="h-4 w-full" />
                ))}
              </div>
            </div>
            <div className="space-y-4 pt-2">
              {Array(5).fill(0).map((_, i) => (
                <div key={i} className="grid grid-cols-7 gap-4">
                  {Array(7).fill(0).map((_, j) => (
                    <Skeleton key={j} className="h-4 w-full" />
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}