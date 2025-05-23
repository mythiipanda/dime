"use client";

import React, { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar } from "@/components/ui/avatar";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { BarChart2, Users, TrendingUp, AlertTriangle, Zap, Target, GitCompare, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import { TeamAIAssistant } from "@/components/teams/TeamAIAssistant";
import { TeamLineups } from "@/components/teams/TeamLineups";
import { TeamRoster } from "@/components/teams/TeamRoster";
import { TeamAnalysis } from "@/components/teams/TeamAnalysis";

interface TeamDashboardClientProps {
  teamId: string;
  season: string;
}

export default function TeamDashboardClient({ teamId, season }: TeamDashboardClientProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [teamData, setTeamData] = useState<any>(null);
  const [activeTab, setActiveTab] = useState("overview");
  
  // Simulate loading data
  useEffect(() => {
    const fetchData = async () => {
      // In a real app, this would be an API call
      // For now, we'll simulate a delay and use placeholder data
      setTimeout(() => {
        setTeamData({
          id: teamId,
          name: "Golden State Warriors",
          abbreviation: "GSW",
          conference: "West",
          division: "Pacific",
          record: "12-10",
          standing: "6th in West",
          logoUrl: "https://cdn.nba.com/logos/nba/1610612744/global/L/logo.svg",
          colorScheme: {
            primary: "#1D428A",
            secondary: "#FFC72C"
          },
          stats: {
            winPct: 0.545,
            ppg: 118.2,
            oppPpg: 115.6,
            netRtg: 2.6,
            pace: 101.2,
            offRtg: 116.8,
            defRtg: 114.2,
            efgPct: 56.2,
            tsPct: 58.7,
            tovPct: 12.5,
            orebPct: 25.8,
            ftRate: 22.1,
            threePtRate: 43.5
          }
        });
        setIsLoading(false);
      }, 1000);
    };
    
    fetchData();
  }, [teamId, season]);
  
  if (isLoading) {
    return <TeamDashboardSkeleton />;
  }
  
  return (
    <div className="flex flex-col space-y-6">
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
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="players">Players</TabsTrigger>
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
              change="+2.1"
              trend="up"
              icon={<BarChart2 className="h-4 w-4" />}
            />
            <StatCard 
              title="Defensive Rating" 
              value={teamData.stats.defRtg.toFixed(1)} 
              change="-0.8"
              trend="down"
              icon={<Shield className="h-4 w-4" />}
            />
            <StatCard 
              title="Net Rating" 
              value={teamData.stats.netRtg.toFixed(1)} 
              change="+1.3"
              trend="up"
              icon={<TrendingUp className="h-4 w-4" />}
            />
            <StatCard 
              title="Effective FG%" 
              value={`${(teamData.stats.efgPct).toFixed(1)}%`} 
              change="+0.5%"
              trend="up"
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
                    max={120} 
                    leagueAvg={112.5} 
                    colorScheme={teamData.colorScheme}
                  />
                  <PerformanceBar 
                    label="Defensive Rating" 
                    value={teamData.stats.defRtg} 
                    max={120} 
                    leagueAvg={112.5} 
                    colorScheme={teamData.colorScheme}
                    lowerIsBetter
                  />
                  <PerformanceBar 
                    label="Pace" 
                    value={teamData.stats.pace} 
                    max={105} 
                    leagueAvg={99.5} 
                    colorScheme={teamData.colorScheme}
                  />
                  <PerformanceBar 
                    label="eFG%" 
                    value={teamData.stats.efgPct} 
                    max={65} 
                    leagueAvg={54.1} 
                    colorScheme={teamData.colorScheme}
                    isPercentage
                  />
                  <PerformanceBar 
                    label="TOV%" 
                    value={teamData.stats.tovPct} 
                    max={20} 
                    leagueAvg={13.2} 
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
                      <li>Elite 3-point shooting (38.2%, 3rd in NBA)</li>
                      <li>Ball movement (28.5 assists per game, 1st in NBA)</li>
                      <li>Transition offense (16.8 fast break points, 4th in NBA)</li>
                      <li>Low turnover rate (12.5%, 6th in NBA)</li>
                    </ul>
                  </div>
                  
                  <div>
                    <h4 className="font-medium mb-2 flex items-center">
                      <AlertTriangle className="h-4 w-4 mr-2 text-red-500" />
                      Weaknesses
                    </h4>
                    <ul className="list-disc list-inside space-y-1 text-sm pl-1">
                      <li>Defensive rebounding (72.4%, 22nd in NBA)</li>
                      <li>Interior defense (48.2 paint points allowed, 24th in NBA)</li>
                      <li>Free throw attempts (19.8 per game, 27th in NBA)</li>
                      <li>Bench scoring (28.5 points per game, 20th in NBA)</li>
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
                    {[
                      { name: "Stephen Curry", position: "PG", ppg: 26.8, rpg: 4.2, apg: 6.5, efg: 58.7, plusMinus: 5.2 },
                      { name: "Klay Thompson", position: "SG", ppg: 17.9, rpg: 3.3, apg: 2.3, efg: 53.5, plusMinus: 2.8 },
                      { name: "Andrew Wiggins", position: "SF", ppg: 12.7, rpg: 4.3, apg: 1.7, efg: 50.2, plusMinus: 1.5 },
                      { name: "Draymond Green", position: "PF", ppg: 8.8, rpg: 7.2, apg: 6.0, efg: 52.1, plusMinus: 4.2 },
                      { name: "Kevon Looney", position: "C", ppg: 5.5, rpg: 6.8, apg: 2.5, efg: 58.3, plusMinus: 2.1 },
                    ].map((player, i) => (
                      <TableRow key={i}>
                        <TableCell className="font-medium">{player.name}</TableCell>
                        <TableCell>{player.position}</TableCell>
                        <TableCell className="text-right">{player.ppg.toFixed(1)}</TableCell>
                        <TableCell className="text-right">{player.rpg.toFixed(1)}</TableCell>
                        <TableCell className="text-right">{player.apg.toFixed(1)}</TableCell>
                        <TableCell className="text-right">{player.efg.toFixed(1)}%</TableCell>
                        <TableCell className={cn("text-right", player.plusMinus > 0 ? "text-green-600" : "text-red-600")}>
                          {player.plusMinus > 0 ? "+" : ""}{player.plusMinus.toFixed(1)}
                        </TableCell>
                      </TableRow>
                    ))}
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
        
        {/* Lineups Tab Content */}
        <TabsContent value="lineups">
          <TeamLineups teamId={teamId} season={season} />
        </TabsContent>
        
        {/* Analysis Tab Content */}
        <TabsContent value="analysis">
          <TeamAnalysis teamId={teamId} season={season} />
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