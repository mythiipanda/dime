'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { nbaDataService, type EnhancedTeam } from '@/lib/services/NBADataService';
import { cn } from '@/lib/utils';
import {
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Trophy,
  Target,
  Clock,
  Zap,
  Shield
} from 'lucide-react';

interface LiveStandingsProps {
  className?: string;
}

export function LiveStandings({ className }: LiveStandingsProps) {
  const [teams, setTeams] = useState<EnhancedTeam[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [autoRefresh, setAutoRefresh] = useState(false);

  useEffect(() => {
    loadStandings();
  }, []);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (autoRefresh) {
      interval = setInterval(() => {
        loadStandings();
      }, 30000); // Refresh every 30 seconds
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  const loadStandings = async () => {
    try {
      setLoading(true);
      // Fetch real standings and team stats data from backend
      const [standingsData, advancedStats] = await Promise.all([
        nbaDataService.getLeagueStandings('2024-25'),
        nbaDataService.getLeagueTeamStats('2024-25', 'Advanced')
      ]);

      // Transform standings data to enhanced teams format
      const enhancedTeams = standingsData.map(standing => {
        const teamInfo = nbaDataService.getTeamInfo(standing.TeamID.toString());
        const teamStats = advancedStats.find(stat => stat.TEAM_ID === standing.TeamID);

        return {
          id: standing.TeamID.toString(),
          name: teamInfo?.name || standing.TeamName,
          abbreviation: teamInfo?.abbreviation || standing.TeamName.substring(0, 3).toUpperCase(),
          conference: standing.Conference as 'East' | 'West',
          division: standing.Division,
          logo: teamInfo?.logo || `https://cdn.nba.com/logos/nba/${standing.TeamID}/primary/L/logo.svg`,
          primaryColor: teamInfo?.primary || '#000000',
          secondaryColor: teamInfo?.secondary || '#FFFFFF',
          record: {
            wins: standing.WINS,
            losses: standing.LOSSES,
            winPct: standing.WinPct
          },
          // Use real advanced stats if available
          offensiveRating: teamStats?.OFF_RATING || 110,
          defensiveRating: teamStats?.DEF_RATING || 110,
          netRating: teamStats?.NET_RATING || 0,
          pace: teamStats?.PACE || 100,
          trueShootingPct: teamStats?.TS_PCT || 0.55,
          effectiveFgPct: teamStats?.EFG_PCT || 0.52,
          turnoverRate: teamStats?.TM_TOV_PCT || 0.14,
          reboundRate: teamStats?.REB_PCT || 0.50,
          streak: {
            type: standing.STRK.charAt(0) as 'W' | 'L',
            count: parseInt(standing.STRK.substring(1)) || 1
          },
          playoffOdds: standing.PlayoffRank <= 10 ? 0.8 + Math.random() * 0.2 : Math.random() * 0.3,
          strengthOfSchedule: Math.random(),
          rankings: {
            overall: standing.PlayoffRank,
            conference: standing.PlayoffRank,
            division: 1,
            offense: Math.floor(Math.random() * 30) + 1,
            defense: Math.floor(Math.random() * 30) + 1
          }
        };
      });

      setTeams(enhancedTeams);
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Error loading standings:', error);
    } finally {
      setLoading(false);
    }
  };

  const getConferenceTeams = (conference: 'East' | 'West') => {
    return teams
      .filter(team => team.conference === conference)
      .sort((a, b) => b.record.winPct - a.record.winPct);
  };

  const getPlayoffStatus = (rank: number) => {
    if (rank <= 6) return { status: 'Guaranteed', color: 'bg-green-500' };
    if (rank <= 10) return { status: 'Play-In', color: 'bg-yellow-500' };
    if (rank <= 12) return { status: 'Bubble', color: 'bg-orange-500' };
    return { status: 'Eliminated', color: 'bg-red-500' };
  };

  const formatTimeAgo = (date: Date) => {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  const renderConferenceStandings = (conference: 'East' | 'West') => {
    const conferenceTeams = getConferenceTeams(conference);

    return (
      <div className="space-y-2">
        {conferenceTeams.map((team, index) => {
          const rank = index + 1;
          const playoffStatus = getPlayoffStatus(rank);

          return (
            <Card key={team.id} className="p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="flex items-center space-x-2">
                    <div className={cn("w-2 h-8 rounded", playoffStatus.color)} />
                    <span className="font-bold text-lg w-6">{rank}</span>
                  </div>

                  <img src={team.logo} alt={team.name} className="w-8 h-8" />

                  <div>
                    <div className="font-semibold">{team.name}</div>
                    <div className="text-sm text-muted-foreground">{team.abbreviation}</div>
                  </div>
                </div>

                <div className="flex items-center space-x-6 text-sm">
                  <div className="text-center">
                    <div className="font-bold">{team.record.wins}-{team.record.losses}</div>
                    <div className="text-muted-foreground">Record</div>
                  </div>

                  <div className="text-center">
                    <div className="font-bold">{(team.record.winPct * 100).toFixed(1)}%</div>
                    <div className="text-muted-foreground">Win %</div>
                  </div>

                  <div className="text-center">
                    <Badge variant={team.streak.type === 'W' ? 'default' : 'destructive'}>
                      {team.streak.type}{team.streak.count}
                    </Badge>
                    <div className="text-muted-foreground">Streak</div>
                  </div>

                  <div className="text-center">
                    <div className="flex items-center space-x-1">
                      {team.netRating > 0 ? (
                        <TrendingUp className="w-3 h-3 text-green-500" />
                      ) : (
                        <TrendingDown className="w-3 h-3 text-red-500" />
                      )}
                      <span className={cn(
                        "font-bold text-xs",
                        team.netRating > 0 ? "text-green-600" : "text-red-600"
                      )}>
                        {team.netRating > 0 ? '+' : ''}{team.netRating.toFixed(1)}
                      </span>
                    </div>
                    <div className="text-muted-foreground">Net Rtg</div>
                  </div>

                  <div className="text-center">
                    <Badge variant="outline" className="text-xs">
                      {playoffStatus.status}
                    </Badge>
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    );
  };

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Live NBA Standings</h1>
          <div className="flex items-center space-x-2 text-sm text-muted-foreground mt-1">
            <Clock className="w-4 h-4" />
            <span>Last updated: {formatTimeAgo(lastUpdated)}</span>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={autoRefresh ? "bg-green-50 border-green-200" : ""}
          >
            <RefreshCw className={cn("w-4 h-4 mr-2", autoRefresh && "animate-spin")} />
            {autoRefresh ? 'Auto Refresh On' : 'Auto Refresh Off'}
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={loadStandings}
            disabled={loading}
          >
            <RefreshCw className={cn("w-4 h-4 mr-2", loading && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Playoff Legend */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Playoff Picture Legend</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4 text-sm">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-green-500 rounded" />
              <span>Guaranteed Playoffs (1-6)</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-yellow-500 rounded" />
              <span>Play-In Tournament (7-10)</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-orange-500 rounded" />
              <span>Playoff Bubble (11-12)</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-red-500 rounded" />
              <span>Eliminated (13-15)</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Conference Standings */}
      <Tabs defaultValue="east" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="east">Eastern Conference</TabsTrigger>
          <TabsTrigger value="west">Western Conference</TabsTrigger>
          <TabsTrigger value="league">League Leaders</TabsTrigger>
        </TabsList>

        <TabsContent value="east" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Trophy className="w-5 h-5 text-blue-600" />
                <span>Eastern Conference</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="text-center py-8">Loading Eastern Conference...</div>
              ) : (
                renderConferenceStandings('East')
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="west" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Trophy className="w-5 h-5 text-red-600" />
                <span>Western Conference</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="text-center py-8">Loading Western Conference...</div>
              ) : (
                renderConferenceStandings('West')
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="league" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Zap className="w-5 h-5 text-orange-500" />
                  <span>Best Offense</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {teams
                    .sort((a, b) => b.offensiveRating - a.offensiveRating)
                    .slice(0, 5)
                    .map((team, index) => (
                      <div key={team.id} className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <span className="font-bold w-4">{index + 1}</span>
                          <img src={team.logo} alt={team.name} className="w-6 h-6" />
                          <span className="font-medium">{team.abbreviation}</span>
                        </div>
                        <span className="font-bold">{team.offensiveRating.toFixed(1)}</span>
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Shield className="w-5 h-5 text-blue-500" />
                  <span>Best Defense</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {teams
                    .sort((a, b) => a.defensiveRating - b.defensiveRating)
                    .slice(0, 5)
                    .map((team, index) => (
                      <div key={team.id} className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <span className="font-bold w-4">{index + 1}</span>
                          <img src={team.logo} alt={team.name} className="w-6 h-6" />
                          <span className="font-medium">{team.abbreviation}</span>
                        </div>
                        <span className="font-bold">{team.defensiveRating.toFixed(1)}</span>
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
