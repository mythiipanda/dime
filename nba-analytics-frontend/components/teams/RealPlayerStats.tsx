'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { nbaDataService, type PlayerStats } from '@/lib/services/NBADataService';
import { cn } from '@/lib/utils';
import { 
  Search, 
  TrendingUp, 
  TrendingDown, 
  Target,
  Trophy,
  User,
  BarChart3,
  RefreshCw
} from 'lucide-react';

interface RealPlayerStatsProps {
  className?: string;
}

export function RealPlayerStats({ className }: RealPlayerStatsProps) {
  const [players, setPlayers] = useState<PlayerStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('PTS');
  const [filterTeam, setFilterTeam] = useState('all');
  const [filterPosition, setFilterPosition] = useState('all');

  useEffect(() => {
    loadPlayerStats();
  }, []);

  const loadPlayerStats = async () => {
    try {
      setLoading(true);
      // Fetch real player stats from backend
      const playerStats = await nbaDataService.getLeaguePlayerStats('2024-25', 'Base');
      setPlayers(playerStats);
    } catch (error) {
      console.error('Error loading player stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredAndSortedPlayers = players
    .filter(player => {
      const nameMatch = player.PLAYER_NAME.toLowerCase().includes(searchQuery.toLowerCase());
      const teamMatch = filterTeam === 'all' || player.TEAM_ABBREVIATION === filterTeam;
      return nameMatch && teamMatch;
    })
    .sort((a, b) => {
      const aValue = (a as any)[sortBy] || 0;
      const bValue = (b as any)[sortBy] || 0;
      return bValue - aValue; // Descending order
    })
    .slice(0, 50); // Limit to top 50 for performance

  const getUniqueTeams = () => {
    const teams = [...new Set(players.map(p => p.TEAM_ABBREVIATION))].sort();
    return teams;
  };

  const getStatColor = (value: number, stat: string) => {
    // Define thresholds for different stats
    const thresholds: Record<string, { excellent: number; good: number }> = {
      PTS: { excellent: 25, good: 15 },
      REB: { excellent: 10, good: 6 },
      AST: { excellent: 8, good: 5 },
      FG_PCT: { excellent: 0.5, good: 0.45 },
      FG3_PCT: { excellent: 0.4, good: 0.35 },
      FT_PCT: { excellent: 0.85, good: 0.75 }
    };

    const threshold = thresholds[stat];
    if (!threshold) return 'text-gray-600';

    if (value >= threshold.excellent) return 'text-green-600 font-bold';
    if (value >= threshold.good) return 'text-blue-600';
    return 'text-gray-600';
  };

  const formatStat = (value: number, stat: string) => {
    if (stat.includes('PCT')) {
      return (value * 100).toFixed(1) + '%';
    }
    return value.toFixed(1);
  };

  if (loading) {
    return (
      <div className={cn("space-y-6", className)}>
        <div className="text-center py-8">
          <h2 className="text-xl font-semibold mb-4">Loading Player Statistics...</h2>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex flex-col space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">NBA Player Statistics (2024-25)</h1>
          <Button onClick={loadPlayerStats} variant="outline" size="sm">
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>
        
        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
            <Input
              placeholder="Search players..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
          
          <Select value={filterTeam} onValueChange={setFilterTeam}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="Filter by team" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Teams</SelectItem>
              {getUniqueTeams().map((team) => (
                <SelectItem key={team} value={team}>
                  {team}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="PTS">Points</SelectItem>
              <SelectItem value="REB">Rebounds</SelectItem>
              <SelectItem value="AST">Assists</SelectItem>
              <SelectItem value="FG_PCT">FG%</SelectItem>
              <SelectItem value="FG3_PCT">3P%</SelectItem>
              <SelectItem value="MIN">Minutes</SelectItem>
              <SelectItem value="STL">Steals</SelectItem>
              <SelectItem value="BLK">Blocks</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">{players.length}</div>
            <div className="text-sm text-muted-foreground">Total Players</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-green-600">
              {getUniqueTeams().length}
            </div>
            <div className="text-sm text-muted-foreground">Teams</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-orange-600">
              {filteredAndSortedPlayers.length}
            </div>
            <div className="text-sm text-muted-foreground">Filtered Results</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-purple-600">
              {players.filter(p => p.GP >= 20).length}
            </div>
            <div className="text-sm text-muted-foreground">Active Players (20+ GP)</div>
          </CardContent>
        </Card>
      </div>

      {/* Player Stats Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <BarChart3 className="w-5 h-5" />
            <span>Player Statistics</span>
            <Badge variant="outline">{filteredAndSortedPlayers.length} players</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left p-2">Player</th>
                  <th className="text-left p-2">Team</th>
                  <th className="text-center p-2">GP</th>
                  <th className="text-center p-2">MIN</th>
                  <th className="text-center p-2">PTS</th>
                  <th className="text-center p-2">REB</th>
                  <th className="text-center p-2">AST</th>
                  <th className="text-center p-2">FG%</th>
                  <th className="text-center p-2">3P%</th>
                  <th className="text-center p-2">FT%</th>
                  <th className="text-center p-2">STL</th>
                  <th className="text-center p-2">BLK</th>
                </tr>
              </thead>
              <tbody>
                {filteredAndSortedPlayers.map((player, index) => (
                  <tr key={player.PLAYER_ID} className="border-b hover:bg-muted/50">
                    <td className="p-2">
                      <div className="flex items-center space-x-2">
                        <div className="w-6 h-6 bg-muted rounded-full flex items-center justify-center text-xs font-bold">
                          {index + 1}
                        </div>
                        <div>
                          <div className="font-medium">{player.PLAYER_NAME}</div>
                          <div className="text-xs text-muted-foreground">Age: {player.AGE}</div>
                        </div>
                      </div>
                    </td>
                    <td className="p-2">
                      <Badge variant="outline">{player.TEAM_ABBREVIATION}</Badge>
                    </td>
                    <td className="text-center p-2">{player.GP}</td>
                    <td className="text-center p-2">{player.MIN.toFixed(1)}</td>
                    <td className={cn("text-center p-2", getStatColor(player.PTS, 'PTS'))}>
                      {player.PTS.toFixed(1)}
                    </td>
                    <td className={cn("text-center p-2", getStatColor(player.REB, 'REB'))}>
                      {player.REB.toFixed(1)}
                    </td>
                    <td className={cn("text-center p-2", getStatColor(player.AST, 'AST'))}>
                      {player.AST.toFixed(1)}
                    </td>
                    <td className={cn("text-center p-2", getStatColor(player.FG_PCT, 'FG_PCT'))}>
                      {formatStat(player.FG_PCT, 'FG_PCT')}
                    </td>
                    <td className={cn("text-center p-2", getStatColor(player.FG3_PCT, 'FG3_PCT'))}>
                      {formatStat(player.FG3_PCT, 'FG3_PCT')}
                    </td>
                    <td className={cn("text-center p-2", getStatColor(player.FT_PCT, 'FT_PCT'))}>
                      {formatStat(player.FT_PCT, 'FT_PCT')}
                    </td>
                    <td className="text-center p-2">{player.STL.toFixed(1)}</td>
                    <td className="text-center p-2">{player.BLK.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {filteredAndSortedPlayers.length === 0 && (
        <Card>
          <CardContent className="p-8 text-center">
            <User className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
            <h3 className="text-lg font-semibold mb-2">No Players Found</h3>
            <p className="text-muted-foreground">
              No players match your current search and filter criteria.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
