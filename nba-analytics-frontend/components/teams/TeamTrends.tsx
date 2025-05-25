'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { nbaDataService, type EnhancedTeam } from '@/lib/services/NBADataService';
import { cn } from '@/lib/utils';
import { 
  TrendingUp, 
  TrendingDown, 
  BarChart3,
  Target,
  Zap,
  Shield,
  Activity,
  AlertTriangle,
  CheckCircle
} from 'lucide-react';

interface TeamTrendsProps {
  className?: string;
}

interface TrendData {
  metric: string;
  current: number;
  trend: 'up' | 'down' | 'stable';
  change: number;
  rank: number;
  status: 'excellent' | 'good' | 'average' | 'poor' | 'critical';
}

export function TeamTrends({ className }: TeamTrendsProps) {
  const [teams, setTeams] = useState<EnhancedTeam[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [trends, setTrends] = useState<TrendData[]>([]);

  useEffect(() => {
    loadTeams();
  }, []);

  useEffect(() => {
    if (selectedTeam) {
      generateTrends();
    }
  }, [selectedTeam, teams]);

  const loadTeams = async () => {
    try {
      const teamsData = await nbaDataService.getEnhancedTeams();
      setTeams(teamsData);
      if (teamsData.length > 0) {
        setSelectedTeam(teamsData[0].id);
      }
    } catch (error) {
      console.error('Error loading teams:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateTrends = () => {
    const team = teams.find(t => t.id === selectedTeam);
    if (!team) return;

    // Generate mock trend data based on current stats
    const mockTrends: TrendData[] = [
      {
        metric: 'Offensive Rating',
        current: team.offensiveRating,
        trend: team.offensiveRating > 115 ? 'up' : team.offensiveRating < 110 ? 'down' : 'stable',
        change: Math.random() * 4 - 2, // Random change between -2 and +2
        rank: team.rankings.offense,
        status: team.offensiveRating > 118 ? 'excellent' : 
                team.offensiveRating > 115 ? 'good' : 
                team.offensiveRating > 112 ? 'average' : 
                team.offensiveRating > 108 ? 'poor' : 'critical'
      },
      {
        metric: 'Defensive Rating',
        current: team.defensiveRating,
        trend: team.defensiveRating < 110 ? 'up' : team.defensiveRating > 115 ? 'down' : 'stable',
        change: Math.random() * 4 - 2,
        rank: team.rankings.defense,
        status: team.defensiveRating < 108 ? 'excellent' : 
                team.defensiveRating < 112 ? 'good' : 
                team.defensiveRating < 115 ? 'average' : 
                team.defensiveRating < 118 ? 'poor' : 'critical'
      },
      {
        metric: 'Net Rating',
        current: team.netRating,
        trend: team.netRating > 5 ? 'up' : team.netRating < -2 ? 'down' : 'stable',
        change: Math.random() * 3 - 1.5,
        rank: Math.floor(Math.random() * 30) + 1,
        status: team.netRating > 8 ? 'excellent' : 
                team.netRating > 4 ? 'good' : 
                team.netRating > 0 ? 'average' : 
                team.netRating > -4 ? 'poor' : 'critical'
      },
      {
        metric: 'True Shooting %',
        current: team.trueShootingPct,
        trend: team.trueShootingPct > 58 ? 'up' : team.trueShootingPct < 55 ? 'down' : 'stable',
        change: Math.random() * 2 - 1,
        rank: Math.floor(Math.random() * 30) + 1,
        status: team.trueShootingPct > 60 ? 'excellent' : 
                team.trueShootingPct > 58 ? 'good' : 
                team.trueShootingPct > 56 ? 'average' : 
                team.trueShootingPct > 54 ? 'poor' : 'critical'
      },
      {
        metric: 'Pace',
        current: team.pace,
        trend: 'stable',
        change: Math.random() * 2 - 1,
        rank: Math.floor(Math.random() * 30) + 1,
        status: 'average'
      }
    ];

    setTrends(mockTrends);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'excellent': return 'bg-green-500';
      case 'good': return 'bg-blue-500';
      case 'average': return 'bg-yellow-500';
      case 'poor': return 'bg-orange-500';
      case 'critical': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'excellent': return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'good': return <TrendingUp className="w-4 h-4 text-blue-500" />;
      case 'average': return <Target className="w-4 h-4 text-yellow-500" />;
      case 'poor': return <TrendingDown className="w-4 h-4 text-orange-500" />;
      case 'critical': return <AlertTriangle className="w-4 h-4 text-red-500" />;
      default: return <Activity className="w-4 h-4 text-gray-500" />;
    }
  };

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'up': return <TrendingUp className="w-4 h-4 text-green-500" />;
      case 'down': return <TrendingDown className="w-4 h-4 text-red-500" />;
      default: return <Target className="w-4 h-4 text-gray-500" />;
    }
  };

  const getMetricIcon = (metric: string) => {
    if (metric.includes('Offensive')) return <Zap className="w-4 h-4 text-orange-500" />;
    if (metric.includes('Defensive')) return <Shield className="w-4 h-4 text-blue-500" />;
    if (metric.includes('Net')) return <BarChart3 className="w-4 h-4 text-purple-500" />;
    return <Target className="w-4 h-4 text-gray-500" />;
  };

  const selectedTeamData = teams.find(t => t.id === selectedTeam);

  if (loading) {
    return (
      <div className={cn("space-y-6", className)}>
        <div className="text-center py-8">
          <h2 className="text-xl font-semibold mb-4">Loading Team Trends...</h2>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex flex-col space-y-4">
        <h1 className="text-3xl font-bold">Team Performance Trends</h1>
        
        {/* Team Selector */}
        <div className="w-full max-w-md">
          <Select value={selectedTeam} onValueChange={setSelectedTeam}>
            <SelectTrigger>
              <SelectValue placeholder="Select a team" />
            </SelectTrigger>
            <SelectContent>
              {teams.map((team) => (
                <SelectItem key={team.id} value={team.id}>
                  <div className="flex items-center space-x-2">
                    <img src={team.logo} alt={team.name} className="w-5 h-5" />
                    <span>{team.name}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Selected Team Header */}
      {selectedTeamData && (
        <Card>
          <CardHeader>
            <div className="flex items-center space-x-4">
              <img src={selectedTeamData.logo} alt={selectedTeamData.name} className="w-16 h-16" />
              <div>
                <CardTitle className="text-2xl">{selectedTeamData.name}</CardTitle>
                <p className="text-muted-foreground">
                  {selectedTeamData.record.wins}-{selectedTeamData.record.losses} • 
                  #{selectedTeamData.rankings.conference} in {selectedTeamData.conference}ern Conference
                </p>
              </div>
            </div>
          </CardHeader>
        </Card>
      )}

      {/* Trends Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {trends.map((trend) => (
          <Card key={trend.metric}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  {getMetricIcon(trend.metric)}
                  <CardTitle className="text-lg">{trend.metric}</CardTitle>
                </div>
                {getTrendIcon(trend.trend)}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Current Value */}
              <div className="text-center">
                <div className="text-3xl font-bold">{trend.current.toFixed(1)}</div>
                <div className="text-sm text-muted-foreground">Current Value</div>
              </div>

              {/* Status and Rank */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  {getStatusIcon(trend.status)}
                  <Badge variant="outline" className="capitalize">
                    {trend.status}
                  </Badge>
                </div>
                <div className="text-right">
                  <div className="font-bold">#{trend.rank}</div>
                  <div className="text-xs text-muted-foreground">League Rank</div>
                </div>
              </div>

              {/* Change Indicator */}
              <div className="flex items-center justify-center space-x-2 p-2 bg-muted rounded-lg">
                {trend.change > 0 ? (
                  <TrendingUp className="w-4 h-4 text-green-500" />
                ) : trend.change < 0 ? (
                  <TrendingDown className="w-4 h-4 text-red-500" />
                ) : (
                  <Target className="w-4 h-4 text-gray-500" />
                )}
                <span className={cn(
                  "font-medium",
                  trend.change > 0 ? "text-green-600" : 
                  trend.change < 0 ? "text-red-600" : "text-gray-600"
                )}>
                  {trend.change > 0 ? '+' : ''}{trend.change.toFixed(1)} vs last 10 games
                </span>
              </div>

              {/* Status Bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span>Performance Level</span>
                  <span className="capitalize">{trend.status}</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className={cn("h-2 rounded-full", getStatusColor(trend.status))}
                    style={{ 
                      width: trend.status === 'excellent' ? '100%' :
                             trend.status === 'good' ? '80%' :
                             trend.status === 'average' ? '60%' :
                             trend.status === 'poor' ? '40%' : '20%'
                    }}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Summary Insights */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Activity className="w-5 h-5" />
            <span>Performance Summary</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <div className="text-2xl font-bold text-green-600">
                {trends.filter(t => t.status === 'excellent' || t.status === 'good').length}
              </div>
              <div className="text-sm text-green-700">Strong Areas</div>
            </div>
            
            <div className="text-center p-4 bg-yellow-50 rounded-lg">
              <div className="text-2xl font-bold text-yellow-600">
                {trends.filter(t => t.status === 'average').length}
              </div>
              <div className="text-sm text-yellow-700">Average Areas</div>
            </div>
            
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <div className="text-2xl font-bold text-red-600">
                {trends.filter(t => t.status === 'poor' || t.status === 'critical').length}
              </div>
              <div className="text-sm text-red-700">Areas for Improvement</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
