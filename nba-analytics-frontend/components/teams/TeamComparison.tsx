'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { nbaDataService, type EnhancedTeam } from '@/lib/services/NBADataService';
import { cn } from '@/lib/utils';
import { 
  TrendingUp, 
  TrendingDown, 
  Shield, 
  Zap, 
  Users,
  BarChart3,
  Target,
  Trophy,
  Minus
} from 'lucide-react';

interface TeamComparisonProps {
  className?: string;
}

export function TeamComparison({ className }: TeamComparisonProps) {
  const [teams, setTeams] = useState<EnhancedTeam[]>([]);
  const [selectedTeam1, setSelectedTeam1] = useState<string>('');
  const [selectedTeam2, setSelectedTeam2] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [comparisonData, setComparisonData] = useState<any>(null);

  useEffect(() => {
    loadTeams();
  }, []);

  useEffect(() => {
    if (selectedTeam1 && selectedTeam2) {
      loadComparison();
    }
  }, [selectedTeam1, selectedTeam2]);

  const loadTeams = async () => {
    try {
      const teamsData = await nbaDataService.getEnhancedTeams();
      setTeams(teamsData);
    } catch (error) {
      console.error('Error loading teams:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadComparison = async () => {
    if (!selectedTeam1 || !selectedTeam2) return;
    
    try {
      const comparison = await nbaDataService.compareTeams([selectedTeam1, selectedTeam2]);
      setComparisonData(comparison);
    } catch (error) {
      console.error('Error loading comparison:', error);
    }
  };

  const getTeamById = (id: string) => teams.find(t => t.id === id);

  const getMetricComparison = (metric: string, team1Value: number, team2Value: number) => {
    const isLowerBetter = ['defensiveRating', 'turnoverRate'].includes(metric);
    const team1Better = isLowerBetter ? team1Value < team2Value : team1Value > team2Value;
    
    return {
      team1Better,
      team2Better: !team1Better,
      difference: Math.abs(team1Value - team2Value)
    };
  };

  const formatMetric = (metric: string, value: number) => {
    if (metric.includes('Pct') || metric.includes('Rate')) {
      return `${value.toFixed(1)}%`;
    }
    return value.toFixed(1);
  };

  const getMetricIcon = (metric: string) => {
    switch (metric) {
      case 'offensiveRating': return <Zap className="w-4 h-4 text-orange-500" />;
      case 'defensiveRating': return <Shield className="w-4 h-4 text-blue-500" />;
      case 'netRating': return <TrendingUp className="w-4 h-4 text-green-500" />;
      case 'pace': return <BarChart3 className="w-4 h-4 text-purple-500" />;
      default: return <Target className="w-4 h-4 text-gray-500" />;
    }
  };

  const getMetricName = (metric: string) => {
    const names: Record<string, string> = {
      offensiveRating: 'Offensive Rating',
      defensiveRating: 'Defensive Rating',
      netRating: 'Net Rating',
      pace: 'Pace',
      trueShootingPct: 'True Shooting %',
      effectiveFgPct: 'Effective FG %',
      turnoverRate: 'Turnover Rate',
      reboundRate: 'Rebound Rate'
    };
    return names[metric] || metric;
  };

  if (loading) {
    return (
      <div className={cn("space-y-6", className)}>
        <div className="text-center py-8">
          <h2 className="text-xl font-semibold mb-4">Loading Team Comparison...</h2>
        </div>
      </div>
    );
  }

  const team1 = getTeamById(selectedTeam1);
  const team2 = getTeamById(selectedTeam2);

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex flex-col space-y-4">
        <h1 className="text-3xl font-bold">Team Comparison</h1>
        
        {/* Team Selectors */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Team 1</label>
            <Select value={selectedTeam1} onValueChange={setSelectedTeam1}>
              <SelectTrigger>
                <SelectValue placeholder="Select first team" />
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
          
          <div className="space-y-2">
            <label className="text-sm font-medium">Team 2</label>
            <Select value={selectedTeam2} onValueChange={setSelectedTeam2}>
              <SelectTrigger>
                <SelectValue placeholder="Select second team" />
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
      </div>

      {/* Comparison Results */}
      {team1 && team2 && (
        <div className="space-y-6">
          {/* Team Headers */}
          <div className="grid grid-cols-2 gap-4">
            <Card>
              <CardHeader className="text-center">
                <div className="flex items-center justify-center space-x-3">
                  <img src={team1.logo} alt={team1.name} className="w-12 h-12" />
                  <div>
                    <CardTitle className="text-xl">{team1.name}</CardTitle>
                    <p className="text-sm text-muted-foreground">
                      {team1.record.wins}-{team1.record.losses} ({(team1.record.winPct * 100).toFixed(1)}%)
                    </p>
                  </div>
                </div>
              </CardHeader>
            </Card>
            
            <Card>
              <CardHeader className="text-center">
                <div className="flex items-center justify-center space-x-3">
                  <img src={team2.logo} alt={team2.name} className="w-12 h-12" />
                  <div>
                    <CardTitle className="text-xl">{team2.name}</CardTitle>
                    <p className="text-sm text-muted-foreground">
                      {team2.record.wins}-{team2.record.losses} ({(team2.record.winPct * 100).toFixed(1)}%)
                    </p>
                  </div>
                </div>
              </CardHeader>
            </Card>
          </div>

          {/* Metrics Comparison */}
          {comparisonData && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <BarChart3 className="w-5 h-5" />
                  <span>Advanced Metrics Comparison</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {comparisonData.comparison.map((metric: any) => {
                    const team1Value = metric.values.find((v: any) => v.teamId === selectedTeam1)?.value || 0;
                    const team2Value = metric.values.find((v: any) => v.teamId === selectedTeam2)?.value || 0;
                    const comparison = getMetricComparison(metric.metric, team1Value, team2Value);
                    
                    return (
                      <div key={metric.metric} className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            {getMetricIcon(metric.metric)}
                            <span className="font-medium">{getMetricName(metric.metric)}</span>
                          </div>
                        </div>
                        
                        <div className="grid grid-cols-3 gap-4 items-center">
                          <div className={cn(
                            "text-center p-3 rounded-lg",
                            comparison.team1Better ? "bg-green-50 border border-green-200" : "bg-gray-50"
                          )}>
                            <div className="font-bold text-lg">{formatMetric(metric.metric, team1Value)}</div>
                            <div className="text-xs text-muted-foreground">{team1.abbreviation}</div>
                            {comparison.team1Better && <Badge variant="default" className="mt-1 text-xs">Better</Badge>}
                          </div>
                          
                          <div className="text-center">
                            <Minus className="w-4 h-4 mx-auto text-muted-foreground" />
                          </div>
                          
                          <div className={cn(
                            "text-center p-3 rounded-lg",
                            comparison.team2Better ? "bg-green-50 border border-green-200" : "bg-gray-50"
                          )}>
                            <div className="font-bold text-lg">{formatMetric(metric.metric, team2Value)}</div>
                            <div className="text-xs text-muted-foreground">{team2.abbreviation}</div>
                            {comparison.team2Better && <Badge variant="default" className="mt-1 text-xs">Better</Badge>}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
