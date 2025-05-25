'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { nbaDataService, type EnhancedTeam } from '@/lib/services/NBADataService';
import { cn } from '@/lib/utils';
import { 
  TrendingUp, 
  TrendingDown, 
  DollarSign,
  Users,
  Target,
  AlertTriangle,
  CheckCircle,
  ArrowRightLeft,
  Calculator,
  BarChart3
} from 'lucide-react';

interface TradeAnalysisProps {
  className?: string;
}

interface TradeScenario {
  id: string;
  team1: string;
  team2: string;
  team1Assets: string[];
  team2Assets: string[];
  salaryMatch: boolean;
  winnerTeam: string;
  impact: 'high' | 'medium' | 'low';
  likelihood: number;
  reasoning: string;
}

export function TradeAnalysis({ className }: TradeAnalysisProps) {
  const [teams, setTeams] = useState<EnhancedTeam[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [tradeScenarios, setTradeScenarios] = useState<TradeScenario[]>([]);

  useEffect(() => {
    loadTeams();
  }, []);

  useEffect(() => {
    if (selectedTeam) {
      generateTradeScenarios();
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

  const generateTradeScenarios = () => {
    const team = teams.find(t => t.id === selectedTeam);
    if (!team) return;

    // Generate realistic trade scenarios based on team needs
    const scenarios: TradeScenario[] = [
      {
        id: '1',
        team1: team.id,
        team2: getRandomTeamId(),
        team1Assets: ['D\'Angelo Russell', '2025 1st Round Pick'],
        team2Assets: ['Dejounte Murray'],
        salaryMatch: true,
        winnerTeam: team.id,
        impact: 'high',
        likelihood: 75,
        reasoning: 'Addresses playmaking needs while maintaining salary flexibility'
      },
      {
        id: '2',
        team1: team.id,
        team2: getRandomTeamId(),
        team1Assets: ['Role Player', 'Future 2nd Round Pick'],
        team2Assets: ['Veteran Center'],
        salaryMatch: true,
        winnerTeam: 'neutral',
        impact: 'medium',
        likelihood: 60,
        reasoning: 'Fills depth needs without major roster disruption'
      },
      {
        id: '3',
        team1: team.id,
        team2: getRandomTeamId(),
        team1Assets: ['Young Player', 'Multiple Picks'],
        team2Assets: ['All-Star Player'],
        salaryMatch: false,
        winnerTeam: team.id,
        impact: 'high',
        likelihood: 25,
        reasoning: 'High-risk, high-reward move for championship push'
      }
    ];

    setTradeScenarios(scenarios);
  };

  const getRandomTeamId = () => {
    const otherTeams = teams.filter(t => t.id !== selectedTeam);
    return otherTeams[Math.floor(Math.random() * otherTeams.length)]?.id || '';
  };

  const getTeamById = (id: string) => teams.find(t => t.id === id);

  const getImpactColor = (impact: string) => {
    switch (impact) {
      case 'high': return 'bg-red-500';
      case 'medium': return 'bg-yellow-500';
      case 'low': return 'bg-green-500';
      default: return 'bg-gray-500';
    }
  };

  const getLikelihoodColor = (likelihood: number) => {
    if (likelihood >= 70) return 'text-green-600';
    if (likelihood >= 40) return 'text-yellow-600';
    return 'text-red-600';
  };

  const selectedTeamData = teams.find(t => t.id === selectedTeam);

  if (loading) {
    return (
      <div className={cn("space-y-6", className)}>
        <div className="text-center py-8">
          <h2 className="text-xl font-semibold mb-4">Loading Trade Analysis...</h2>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex flex-col space-y-4">
        <h1 className="text-3xl font-bold">NBA Trade Analysis</h1>
        
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

      {/* Selected Team Analysis */}
      {selectedTeamData && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Target className="w-5 h-5" />
                <span>Team Needs</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {selectedTeamData.defensiveRating > 115 && (
                  <Badge variant="destructive" className="w-full justify-center">
                    Defensive Improvement
                  </Badge>
                )}
                {selectedTeamData.offensiveRating < 110 && (
                  <Badge variant="destructive" className="w-full justify-center">
                    Offensive Firepower
                  </Badge>
                )}
                {selectedTeamData.rankings.conference > 8 && (
                  <Badge variant="secondary" className="w-full justify-center">
                    Playoff Push
                  </Badge>
                )}
                <Badge variant="outline" className="w-full justify-center">
                  Depth & Versatility
                </Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <DollarSign className="w-5 h-5" />
                <span>Salary Cap</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm">Cap Space</span>
                  <span className="font-bold">$12.5M</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Luxury Tax</span>
                  <Badge variant="outline">Under</Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Trade Exception</span>
                  <span className="font-bold">$8.2M</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <BarChart3 className="w-5 h-5" />
                <span>Trade Assets</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm">Future 1st Picks</span>
                  <span className="font-bold">3</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Young Players</span>
                  <span className="font-bold">5</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Expiring Contracts</span>
                  <span className="font-bold">2</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Trade Scenarios */}
      <div className="space-y-4">
        <h2 className="text-2xl font-bold">Potential Trade Scenarios</h2>
        
        {tradeScenarios.map((scenario) => {
          const team1 = getTeamById(scenario.team1);
          const team2 = getTeamById(scenario.team2);
          
          return (
            <Card key={scenario.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center space-x-2">
                    <ArrowRightLeft className="w-5 h-5" />
                    <span>Trade Scenario #{scenario.id}</span>
                  </CardTitle>
                  <div className="flex items-center space-x-2">
                    <Badge 
                      variant="outline" 
                      className={cn("text-white", getImpactColor(scenario.impact))}
                    >
                      {scenario.impact.toUpperCase()} Impact
                    </Badge>
                    <span className={cn("font-bold", getLikelihoodColor(scenario.likelihood))}>
                      {scenario.likelihood}% Likely
                    </span>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {/* Trade Details */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <div className="flex items-center space-x-2">
                        {team1 && <img src={team1.logo} alt={team1.name} className="w-6 h-6" />}
                        <span className="font-semibold">{team1?.name} Sends:</span>
                      </div>
                      <div className="space-y-1">
                        {scenario.team1Assets.map((asset, index) => (
                          <Badge key={index} variant="outline" className="block w-fit">
                            {asset}
                          </Badge>
                        ))}
                      </div>
                    </div>

                    <div className="flex items-center justify-center">
                      <ArrowRightLeft className="w-8 h-8 text-muted-foreground" />
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center space-x-2">
                        {team2 && <img src={team2.logo} alt={team2.name} className="w-6 h-6" />}
                        <span className="font-semibold">{team2?.name} Sends:</span>
                      </div>
                      <div className="space-y-1">
                        {scenario.team2Assets.map((asset, index) => (
                          <Badge key={index} variant="outline" className="block w-fit">
                            {asset}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Trade Analysis */}
                  <div className="border-t pt-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="flex items-center space-x-2">
                        {scenario.salaryMatch ? (
                          <CheckCircle className="w-5 h-5 text-green-500" />
                        ) : (
                          <AlertTriangle className="w-5 h-5 text-red-500" />
                        )}
                        <span className="text-sm">
                          Salary {scenario.salaryMatch ? 'Matches' : 'Mismatch'}
                        </span>
                      </div>

                      <div className="flex items-center space-x-2">
                        {scenario.winnerTeam === selectedTeam ? (
                          <TrendingUp className="w-5 h-5 text-green-500" />
                        ) : scenario.winnerTeam === 'neutral' ? (
                          <Target className="w-5 h-5 text-yellow-500" />
                        ) : (
                          <TrendingDown className="w-5 h-5 text-red-500" />
                        )}
                        <span className="text-sm">
                          {scenario.winnerTeam === selectedTeam ? 'Favors Team' : 
                           scenario.winnerTeam === 'neutral' ? 'Fair Trade' : 'Favors Other Team'}
                        </span>
                      </div>

                      <div className="flex items-center space-x-2">
                        <Calculator className="w-5 h-5 text-blue-500" />
                        <span className="text-sm">Trade Value: Balanced</span>
                      </div>
                    </div>

                    <div className="mt-3 p-3 bg-muted rounded-lg">
                      <p className="text-sm text-muted-foreground">
                        <strong>Analysis:</strong> {scenario.reasoning}
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Trade Deadline Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <AlertTriangle className="w-5 h-5 text-orange-500" />
            <span>Trade Deadline Information</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="text-center p-4 bg-orange-50 rounded-lg">
              <div className="text-2xl font-bold text-orange-600">45</div>
              <div className="text-sm text-orange-700">Days Until Deadline</div>
            </div>
            
            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <div className="text-2xl font-bold text-blue-600">12</div>
              <div className="text-sm text-blue-700">Active Trade Rumors</div>
            </div>
            
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <div className="text-2xl font-bold text-green-600">8</div>
              <div className="text-sm text-green-700">Teams Likely to Trade</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
