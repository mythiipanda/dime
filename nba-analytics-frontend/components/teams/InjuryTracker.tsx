'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Progress } from '@/components/ui/progress';
import { nbaDataService, type EnhancedTeam } from '@/lib/services/NBADataService';
import { cn } from '@/lib/utils';
import { 
  AlertTriangle, 
  Clock, 
  TrendingUp, 
  TrendingDown,
  Activity,
  Heart,
  Shield,
  Target,
  Calendar,
  User,
  RefreshCw
} from 'lucide-react';

interface InjuryTrackerProps {
  className?: string;
}

interface InjuryReport {
  playerId: string;
  playerName: string;
  team: string;
  position: string;
  injury: string;
  bodyPart: string;
  severity: 'minor' | 'moderate' | 'major' | 'season-ending';
  status: 'day-to-day' | 'week-to-week' | 'out' | 'questionable' | 'probable';
  estimatedReturn: string;
  daysOut: number;
  impactRating: number; // 1-10
  lastUpdate: Date;
  description: string;
}

export function InjuryTracker({ className }: InjuryTrackerProps) {
  const [teams, setTeams] = useState<EnhancedTeam[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<string>('all');
  const [loading, setLoading] = useState(true);
  const [injuries, setInjuries] = useState<InjuryReport[]>([]);
  const [filterSeverity, setFilterSeverity] = useState<string>('all');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const teamsData = await nbaDataService.getEnhancedTeams();
      setTeams(teamsData);
      generateMockInjuries(teamsData);
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateMockInjuries = (teamsData: EnhancedTeam[]) => {
    const mockInjuries: InjuryReport[] = [
      {
        playerId: 'kawhi-leonard',
        playerName: 'Kawhi Leonard',
        team: 'Clippers',
        position: 'SF',
        injury: 'Right Knee Inflammation',
        bodyPart: 'knee',
        severity: 'moderate',
        status: 'week-to-week',
        estimatedReturn: '2-3 weeks',
        daysOut: 12,
        impactRating: 9,
        lastUpdate: new Date(Date.now() - 86400000),
        description: 'Ongoing knee management, load management expected'
      },
      {
        playerId: 'zion-williamson',
        playerName: 'Zion Williamson',
        team: 'Pelicans',
        position: 'PF',
        injury: 'Left Hamstring Strain',
        bodyPart: 'hamstring',
        severity: 'minor',
        status: 'day-to-day',
        estimatedReturn: '3-5 days',
        daysOut: 2,
        impactRating: 8,
        lastUpdate: new Date(Date.now() - 43200000),
        description: 'Grade 1 hamstring strain, progressing well'
      },
      {
        playerId: 'ben-simmons',
        playerName: 'Ben Simmons',
        team: 'Nets',
        position: 'PG',
        injury: 'Lower Back Soreness',
        bodyPart: 'back',
        severity: 'moderate',
        status: 'questionable',
        estimatedReturn: 'Game-time decision',
        daysOut: 5,
        impactRating: 6,
        lastUpdate: new Date(Date.now() - 21600000),
        description: 'Chronic back issues, day-to-day monitoring'
      },
      {
        playerId: 'ja-morant',
        playerName: 'Ja Morant',
        team: 'Grizzlies',
        position: 'PG',
        injury: 'Right Shoulder Subluxation',
        bodyPart: 'shoulder',
        severity: 'major',
        status: 'out',
        estimatedReturn: '6-8 weeks',
        daysOut: 18,
        impactRating: 10,
        lastUpdate: new Date(Date.now() - 172800000),
        description: 'Shoulder subluxation, surgery avoided but extended recovery'
      }
    ];

    setInjuries(mockInjuries);
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'minor': return 'bg-yellow-500';
      case 'moderate': return 'bg-orange-500';
      case 'major': return 'bg-red-500';
      case 'season-ending': return 'bg-gray-800';
      default: return 'bg-gray-500';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'probable': return 'text-green-600';
      case 'questionable': return 'text-yellow-600';
      case 'day-to-day': return 'text-blue-600';
      case 'week-to-week': return 'text-orange-600';
      case 'out': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const getImpactIcon = (rating: number) => {
    if (rating >= 8) return <AlertTriangle className="w-4 h-4 text-red-500" />;
    if (rating >= 6) return <TrendingDown className="w-4 h-4 text-orange-500" />;
    return <Activity className="w-4 h-4 text-yellow-500" />;
  };

  const filteredInjuries = injuries.filter(injury => {
    const teamMatch = selectedTeam === 'all' || injury.team === selectedTeam;
    const severityMatch = filterSeverity === 'all' || injury.severity === filterSeverity;
    return teamMatch && severityMatch;
  });

  const getTeamInjuryCount = (teamName: string) => {
    return injuries.filter(injury => injury.team === teamName).length;
  };

  const formatTimeAgo = (date: Date) => {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / 3600000);
    
    if (diffHours < 1) return 'Just updated';
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  if (loading) {
    return (
      <div className={cn("space-y-6", className)}>
        <div className="text-center py-8">
          <h2 className="text-xl font-semibold mb-4">Loading Injury Reports...</h2>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex flex-col space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">NBA Injury Tracker</h1>
          <Button onClick={loadData} variant="outline" size="sm">
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>
        
        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <Select value={selectedTeam} onValueChange={setSelectedTeam}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Select team" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Teams</SelectItem>
              {teams.map((team) => (
                <SelectItem key={team.id} value={team.name}>
                  <div className="flex items-center space-x-2">
                    <img src={team.logo} alt={team.name} className="w-4 h-4" />
                    <span>{team.name}</span>
                    <Badge variant="outline" className="ml-2">
                      {getTeamInjuryCount(team.name)}
                    </Badge>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          <Select value={filterSeverity} onValueChange={setFilterSeverity}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Filter by severity" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Severities</SelectItem>
              <SelectItem value="minor">Minor</SelectItem>
              <SelectItem value="moderate">Moderate</SelectItem>
              <SelectItem value="major">Major</SelectItem>
              <SelectItem value="season-ending">Season-Ending</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-red-600">{injuries.length}</div>
            <div className="text-sm text-muted-foreground">Total Injuries</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-orange-600">
              {injuries.filter(i => i.severity === 'major' || i.severity === 'season-ending').length}
            </div>
            <div className="text-sm text-muted-foreground">Major Injuries</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">
              {injuries.filter(i => i.impactRating >= 8).length}
            </div>
            <div className="text-sm text-muted-foreground">High Impact</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-green-600">
              {Math.round(injuries.reduce((sum, i) => sum + i.daysOut, 0) / injuries.length)}
            </div>
            <div className="text-sm text-muted-foreground">Avg Days Out</div>
          </CardContent>
        </Card>
      </div>

      {/* Injury Reports */}
      <div className="space-y-4">
        <h2 className="text-2xl font-bold">Current Injury Reports ({filteredInjuries.length})</h2>
        
        {filteredInjuries.map((injury) => (
          <Card key={injury.playerId}>
            <CardContent className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center space-x-4">
                  <div className="flex items-center space-x-2">
                    <User className="w-8 h-8 text-muted-foreground" />
                    <div>
                      <div className="font-bold text-lg">{injury.playerName}</div>
                      <div className="text-sm text-muted-foreground">
                        {injury.team} • {injury.position}
                      </div>
                    </div>
                  </div>
                </div>
                
                <div className="flex items-center space-x-2">
                  {getImpactIcon(injury.impactRating)}
                  <Badge 
                    variant="outline" 
                    className={cn("text-white", getSeverityColor(injury.severity))}
                  >
                    {injury.severity.toUpperCase()}
                  </Badge>
                  <Badge variant="outline" className={getStatusColor(injury.status)}>
                    {injury.status.toUpperCase()}
                  </Badge>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                <div>
                  <div className="text-sm text-muted-foreground">Injury</div>
                  <div className="font-medium">{injury.injury}</div>
                </div>
                
                <div>
                  <div className="text-sm text-muted-foreground">Estimated Return</div>
                  <div className="font-medium">{injury.estimatedReturn}</div>
                </div>
                
                <div>
                  <div className="text-sm text-muted-foreground">Days Out</div>
                  <div className="font-medium">{injury.daysOut} days</div>
                </div>
                
                <div>
                  <div className="text-sm text-muted-foreground">Impact Rating</div>
                  <div className="flex items-center space-x-2">
                    <Progress value={injury.impactRating * 10} className="w-16 h-2" />
                    <span className="font-medium">{injury.impactRating}/10</span>
                  </div>
                </div>
              </div>

              <div className="border-t pt-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">{injury.description}</p>
                  <div className="flex items-center space-x-2 text-xs text-muted-foreground">
                    <Clock className="w-3 h-3" />
                    <span>Updated {formatTimeAgo(injury.lastUpdate)}</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {filteredInjuries.length === 0 && (
        <Card>
          <CardContent className="p-8 text-center">
            <Heart className="w-12 h-12 mx-auto mb-4 text-green-500" />
            <h3 className="text-lg font-semibold mb-2">No Injuries Found</h3>
            <p className="text-muted-foreground">
              {selectedTeam === 'all' 
                ? 'No injuries match your current filters.' 
                : `No current injuries reported for ${selectedTeam}.`}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
