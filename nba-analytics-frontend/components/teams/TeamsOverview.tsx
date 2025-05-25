'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Search, TrendingUp, TrendingDown, Trophy, Target, Zap, Shield, BarChart3, GitCompare, Activity } from 'lucide-react';
import { nbaDataService, type EnhancedTeam } from '@/lib/services/NBADataService';
import { TeamComparison } from './TeamComparison';
import { LiveStandings } from './LiveStandings';
import { TeamTrends } from './TeamTrends';
import { InjuryTracker } from './InjuryTracker';
import { RealPlayerStats } from './RealPlayerStats';
import { LiveGameData } from './LiveGameData';
import { AdvancedAnalyticsDashboard } from '../analytics/AdvancedAnalyticsDashboard';
import { cn } from '@/lib/utils';

interface TeamsOverviewProps {
  className?: string;
}

export function TeamsOverview({ className }: TeamsOverviewProps) {
  const [teams, setTeams] = useState<EnhancedTeam[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedConference, setSelectedConference] = useState<'all' | 'East' | 'West'>('all');
  const [sortBy, setSortBy] = useState<'record' | 'netRating' | 'offense' | 'defense'>('record');
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards');

  useEffect(() => {
    loadTeams();
  }, []);

  const loadTeams = async () => {
    try {
      setLoading(true);
      console.log('Loading teams data...');
      const teamsData = await nbaDataService.getEnhancedTeams();
      console.log('Teams data loaded:', teamsData.length, 'teams');
      console.log('First team:', teamsData[0]);
      setTeams(teamsData);
    } catch (error) {
      console.error('Error loading teams:', error);
      console.error('Error details:', error);
      // Set empty array to show error state
      setTeams([]);
    } finally {
      setLoading(false);
    }
  };

  const filteredAndSortedTeams = React.useMemo(() => {
    let filtered = teams;

    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(team =>
        team.name.toLowerCase().includes(query) ||
        team.abbreviation.toLowerCase().includes(query)
      );
    }

    // Filter by conference
    if (selectedConference !== 'all') {
      filtered = filtered.filter(team => team.conference === selectedConference);
    }

    // Sort teams
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'record':
          return b.record.winPct - a.record.winPct;
        case 'netRating':
          return b.netRating - a.netRating;
        case 'offense':
          return b.offensiveRating - a.offensiveRating;
        case 'defense':
          return a.defensiveRating - b.defensiveRating; // Lower is better
        default:
          return b.record.winPct - a.record.winPct;
      }
    });

    return filtered;
  }, [teams, searchQuery, selectedConference, sortBy]);

  const getTeamStatusColor = (team: EnhancedTeam) => {
    if (team.rankings.conference <= 6) return 'bg-green-500';
    if (team.rankings.conference <= 10) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getTeamStatusText = (team: EnhancedTeam) => {
    if (team.rankings.conference <= 6) return 'Playoff Bound';
    if (team.rankings.conference <= 10) return 'Play-In';
    return 'Lottery';
  };

  const formatRating = (rating: number) => rating.toFixed(1);

  if (loading) {
    return (
      <div className={cn("space-y-6", className)}>
        <div className="text-center py-8">
          <h2 className="text-xl font-semibold mb-4">Loading NBA Teams...</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-6 w-3/4" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-20 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (!loading && teams.length === 0) {
    return (
      <div className={cn("space-y-6", className)}>
        <div className="text-center py-8">
          <h2 className="text-xl font-semibold mb-4">No Teams Data Available</h2>
          <p className="text-muted-foreground mb-4">
            Unable to load NBA teams data. Please check your connection and try again.
          </p>
          <Button onClick={loadTeams}>
            Retry Loading Teams
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex flex-col space-y-4">
        <h1 className="text-3xl font-bold">NBA Teams Dashboard</h1>
      </div>

      {/* Main Tabs */}
      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-8 gap-1 p-1 h-auto">
          <TabsTrigger value="overview" className="flex-col h-16 text-xs p-1">
            <Trophy className="w-4 h-4 mb-1" />
            Teams Overview
          </TabsTrigger>
          <TabsTrigger value="standings" className="flex-col h-16 text-xs p-1">
            <BarChart3 className="w-4 h-4 mb-1" />
            Live Standings
          </TabsTrigger>
          <TabsTrigger value="games" className="flex-col h-16 text-xs p-1">
            <Zap className="w-4 h-4 mb-1" />
            Live Games
          </TabsTrigger>
          <TabsTrigger value="players" className="flex-col h-16 text-xs p-1">
            <Target className="w-4 h-4 mb-1" />
            Player Stats
          </TabsTrigger>
          <TabsTrigger value="analytics" className="flex-col h-16 text-xs p-1">
            <TrendingUp className="w-4 h-4 mb-1" />
            Advanced Analytics
          </TabsTrigger>
          <TabsTrigger value="comparison" className="flex-col h-16 text-xs p-1">
            <GitCompare className="w-4 h-4 mb-1" />
            Team Comparison
          </TabsTrigger>
          <TabsTrigger value="trends" className="flex-col h-16 text-xs p-1">
            <Activity className="w-4 h-4 mb-1" />
            Performance Trends
          </TabsTrigger>
          <TabsTrigger value="injuries" className="flex-col h-16 text-xs p-1">
            <Shield className="w-4 h-4 mb-1" />
            Injury Tracker
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <div className="flex flex-col space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold">Teams Overview ({teams.length})</h2>
              <div className="flex items-center space-x-2">
                <Button
                  variant={viewMode === 'cards' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setViewMode('cards')}
                >
                  Cards
                </Button>
                <Button
                  variant={viewMode === 'table' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setViewMode('table')}
                >
                  Table
                </Button>
              </div>
            </div>

            {/* Filters */}
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
                <Input
                  placeholder="Search teams..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
              <Select value={selectedConference} onValueChange={(value: any) => setSelectedConference(value)}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Conference" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Conferences</SelectItem>
                  <SelectItem value="East">Eastern</SelectItem>
                  <SelectItem value="West">Western</SelectItem>
                </SelectContent>
              </Select>
              <Select value={sortBy} onValueChange={(value: any) => setSortBy(value)}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Sort by" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="record">Win Percentage</SelectItem>
                  <SelectItem value="netRating">Net Rating</SelectItem>
                  <SelectItem value="offense">Offensive Rating</SelectItem>
                  <SelectItem value="defense">Defensive Rating</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Debug Info */}
          <div className="text-sm text-muted-foreground mb-4">
            Debug: {teams.length} teams loaded, {filteredAndSortedTeams.length} after filtering
          </div>

      {/* Teams Grid */}
      {viewMode === 'cards' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredAndSortedTeams.map((team) => (
            <Card key={team.id} className="hover:shadow-lg transition-shadow cursor-pointer">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <img
                      src={team.logo}
                      alt={team.name}
                      className="w-8 h-8"
                      onError={(e) => {
                        e.currentTarget.style.display = 'none';
                      }}
                    />
                    <div>
                      <CardTitle className="text-lg">{team.abbreviation}</CardTitle>
                      <p className="text-sm text-muted-foreground">{team.name}</p>
                    </div>
                  </div>
                  <Badge
                    className={cn("text-white", getTeamStatusColor(team))}
                  >
                    #{team.rankings.conference}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Record */}
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Record</span>
                  <span className="font-bold">{team.record.wins}-{team.record.losses}</span>
                </div>

                {/* Win Percentage */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Win %</span>
                    <span className="font-bold">{(team.record.winPct * 100).toFixed(1)}%</span>
                  </div>
                  <Progress value={team.record.winPct * 100} className="h-2" />
                </div>

                {/* Advanced Stats */}
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="flex items-center space-x-2">
                    <Zap className="h-4 w-4 text-orange-500" />
                    <div>
                      <p className="text-muted-foreground">Off Rating</p>
                      <p className="font-bold">{formatRating(team.offensiveRating)}</p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Shield className="h-4 w-4 text-blue-500" />
                    <div>
                      <p className="text-muted-foreground">Def Rating</p>
                      <p className="font-bold">{formatRating(team.defensiveRating)}</p>
                    </div>
                  </div>
                </div>

                {/* Net Rating */}
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Net Rating</span>
                  <div className="flex items-center space-x-1">
                    {team.netRating > 0 ? (
                      <TrendingUp className="h-4 w-4 text-green-500" />
                    ) : (
                      <TrendingDown className="h-4 w-4 text-red-500" />
                    )}
                    <span className={cn(
                      "font-bold",
                      team.netRating > 0 ? "text-green-600" : "text-red-600"
                    )}>
                      {team.netRating > 0 ? '+' : ''}{formatRating(team.netRating)}
                    </span>
                  </div>
                </div>

                {/* Streak */}
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Streak</span>
                  <Badge variant={team.streak.type === 'W' ? 'default' : 'destructive'}>
                    {team.streak.type}{team.streak.count}
                  </Badge>
                </div>

                {/* Status */}
                <div className="pt-2 border-t">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Status</span>
                    <span className="text-sm font-bold">{getTeamStatusText(team)}</span>
                  </div>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-xs text-muted-foreground">Playoff Odds</span>
                    <span className="text-xs font-bold">{team.playoffOdds}%</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        // Table view would go here
        <div className="text-center py-8">
          <p className="text-muted-foreground">Table view coming soon...</p>
        </div>
      )}

          {/* Results Summary */}
          <div className="text-center text-sm text-muted-foreground">
            Showing {filteredAndSortedTeams.length} of {teams.length} teams
          </div>
        </TabsContent>

        <TabsContent value="standings" className="space-y-6">
          <LiveStandings />
        </TabsContent>

        <TabsContent value="games" className="space-y-6">
          <LiveGameData />
        </TabsContent>

        <TabsContent value="players" className="space-y-6">
          <RealPlayerStats />
        </TabsContent>

        <TabsContent value="analytics" className="space-y-6">
          <AdvancedAnalyticsDashboard season="2024-25" />
        </TabsContent>

        <TabsContent value="comparison" className="space-y-6">
          <TeamComparison />
        </TabsContent>

        <TabsContent value="trends" className="space-y-6">
          <TeamTrends />
        </TabsContent>

        <TabsContent value="injuries" className="space-y-6">
          <InjuryTracker />
        </TabsContent>
      </Tabs>
    </div>
  );
}
