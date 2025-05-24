"use client";

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { RefreshCw, AlertTriangle, Trophy, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface StandingsProps {
  season?: string;
}

interface TeamStanding {
  TeamID: number;
  TeamCity: string;
  TeamName: string;
  TeamSlug: string;
  Conference: string;
  ConferenceRecord: string;
  PlayoffRank: number;
  ClinchIndicator: string;
  Division: string;
  DivisionRecord: string;
  DivisionRank: number;
  WINS: number;
  LOSSES: number;
  WinPCT: number;
  Record: string;
  HOME: string;
  ROAD: string;
  L10: string;
  strCurrentStreak: string;
  ConferenceGamesBack: number;
  DivisionGamesBack: number;
  PointsPG: number;
  OppPointsPG: number;
  DiffPointsPG: number;
  ClinchedConferenceTitle: number;
  ClinchedDivisionTitle: number;
  ClinchedPlayoffBirth: number;
  ClinchedPlayIn: number;
  GB: number;
  WinPct: number;
  STRK: string;
}

export function NBAStandings({ season = "2024-25" }: StandingsProps) {
  const [standings, setStandings] = useState<TeamStanding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("east");

  useEffect(() => {
    fetchStandings();
  }, [season]);

  const fetchStandings = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`/api/v1/league/standings?season=${season}`);
      if (!response.ok) {
        throw new Error('Failed to fetch standings');
      }
      
      const data = await response.json();
      setStandings(data.standings || []);
    } catch (err) {
      console.error('Error fetching standings:', err);
      setError('Failed to load standings');
    } finally {
      setLoading(false);
    }
  };

  const eastStandings = standings.filter(team => team.Conference === "East");
  const westStandings = standings.filter(team => team.Conference === "West");

  const getPlayoffIndicator = (team: TeamStanding) => {
    if (team.ClinchedConferenceTitle) {
      return <Badge variant="default" className="bg-yellow-500"><Trophy className="w-3 h-3 mr-1" />Conference</Badge>;
    }
    if (team.ClinchedDivisionTitle) {
      return <Badge variant="default" className="bg-blue-500">Division</Badge>;
    }
    if (team.ClinchedPlayoffBirth) {
      return <Badge variant="default" className="bg-green-500">Playoffs</Badge>;
    }
    if (team.ClinchedPlayIn) {
      return <Badge variant="secondary">Play-In</Badge>;
    }
    if (team.ClinchIndicator.includes("o")) {
      return <Badge variant="destructive">Eliminated</Badge>;
    }
    return null;
  };

  const getStreakIcon = (streak: string) => {
    if (streak.startsWith("W")) {
      return <TrendingUp className="w-3 h-3 text-green-500" />;
    } else if (streak.startsWith("L")) {
      return <TrendingDown className="w-3 h-3 text-red-500" />;
    }
    return null;
  };

  const StandingsTable = ({ teams, conference }: { teams: TeamStanding[], conference: string }) => (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8">#</TableHead>
            <TableHead>Team</TableHead>
            <TableHead className="text-center">W</TableHead>
            <TableHead className="text-center">L</TableHead>
            <TableHead className="text-center">PCT</TableHead>
            <TableHead className="text-center">GB</TableHead>
            <TableHead className="text-center">HOME</TableHead>
            <TableHead className="text-center">ROAD</TableHead>
            <TableHead className="text-center">L10</TableHead>
            <TableHead className="text-center">STRK</TableHead>
            <TableHead className="text-center">DIFF</TableHead>
            <TableHead className="text-center">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {teams.map((team, index) => (
            <TableRow key={team.TeamID} className="hover:bg-muted/50">
              <TableCell className="font-medium text-center">
                {team.PlayoffRank}
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 bg-muted rounded-full flex items-center justify-center text-xs font-bold">
                    {team.TeamCity.charAt(0)}
                  </div>
                  <div>
                    <div className="font-medium">{team.TeamCity} {team.TeamName}</div>
                    <div className="text-xs text-muted-foreground">{team.Division}</div>
                  </div>
                </div>
              </TableCell>
              <TableCell className="text-center font-medium">{team.WINS}</TableCell>
              <TableCell className="text-center font-medium">{team.LOSSES}</TableCell>
              <TableCell className="text-center">{team.WinPCT.toFixed(3)}</TableCell>
              <TableCell className="text-center">
                {team.GB === 0 ? "-" : team.GB.toFixed(1)}
              </TableCell>
              <TableCell className="text-center text-sm">{team.HOME}</TableCell>
              <TableCell className="text-center text-sm">{team.ROAD}</TableCell>
              <TableCell className="text-center text-sm">{team.L10}</TableCell>
              <TableCell className="text-center">
                <div className="flex items-center justify-center gap-1">
                  {getStreakIcon(team.STRK)}
                  <span className="text-sm">{team.STRK}</span>
                </div>
              </TableCell>
              <TableCell className={cn(
                "text-center font-medium",
                team.DiffPointsPG > 0 ? "text-green-600" : "text-red-600"
              )}>
                {team.DiffPointsPG > 0 ? "+" : ""}{team.DiffPointsPG.toFixed(1)}
              </TableCell>
              <TableCell className="text-center">
                {getPlayoffIndicator(team)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-10 w-24" />
        </div>
        <div className="space-y-4">
          {Array.from({ length: 15 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <div className="text-center">
            <AlertTriangle className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-muted-foreground">{error}</p>
            <Button onClick={fetchStandings} variant="outline" className="mt-4">
              <RefreshCw className="w-4 h-4 mr-2" />
              Try Again
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">NBA Standings</h1>
          <p className="text-muted-foreground">{season} Season</p>
        </div>
        <Button onClick={fetchStandings} variant="outline" disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="east">Eastern Conference</TabsTrigger>
          <TabsTrigger value="west">Western Conference</TabsTrigger>
          <TabsTrigger value="league">League</TabsTrigger>
        </TabsList>

        <TabsContent value="east" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Trophy className="w-5 h-5" />
                Eastern Conference
              </CardTitle>
              <CardDescription>
                {eastStandings.length} teams • Updated with real NBA data
              </CardDescription>
            </CardHeader>
            <CardContent>
              <StandingsTable teams={eastStandings} conference="East" />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="west" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Trophy className="w-5 h-5" />
                Western Conference
              </CardTitle>
              <CardDescription>
                {westStandings.length} teams • Updated with real NBA data
              </CardDescription>
            </CardHeader>
            <CardContent>
              <StandingsTable teams={westStandings} conference="West" />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="league" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Eastern Conference</CardTitle>
                <CardDescription>{eastStandings.length} teams</CardDescription>
              </CardHeader>
              <CardContent>
                <StandingsTable teams={eastStandings.slice(0, 8)} conference="East" />
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>Western Conference</CardTitle>
                <CardDescription>{westStandings.length} teams</CardDescription>
              </CardHeader>
              <CardContent>
                <StandingsTable teams={westStandings.slice(0, 8)} conference="West" />
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Best Record</CardTitle>
          </CardHeader>
          <CardContent>
            {standings.length > 0 && (
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 bg-muted rounded-full flex items-center justify-center text-xs font-bold">
                  {standings[0]?.TeamCity?.charAt(0)}
                </div>
                <div>
                  <p className="font-medium">{standings[0]?.TeamCity} {standings[0]?.TeamName}</p>
                  <p className="text-sm text-muted-foreground">{standings[0]?.Record}</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Playoff Race</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              <div className="flex justify-between text-sm">
                <span>Clinched Playoffs:</span>
                <span className="font-medium">
                  {standings.filter(t => t.ClinchedPlayoffBirth).length}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Play-In Position:</span>
                <span className="font-medium">
                  {standings.filter(t => t.ClinchedPlayIn && !t.ClinchedPlayoffBirth).length}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">League Leaders</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              <div className="flex justify-between text-sm">
                <span>Highest Scoring:</span>
                <span className="font-medium">
                  {standings.length > 0 && 
                    standings.reduce((prev, current) => 
                      prev.PointsPG > current.PointsPG ? prev : current
                    )?.PointsPG?.toFixed(1)
                  }
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Best Defense:</span>
                <span className="font-medium">
                  {standings.length > 0 && 
                    standings.reduce((prev, current) => 
                      prev.OppPointsPG < current.OppPointsPG ? prev : current
                    )?.OppPointsPG?.toFixed(1)
                  }
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
