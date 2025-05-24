"use client";

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import {
  Brain,
  TrendingUp,
  Target,
  Zap,
  BarChart3,
  RefreshCw,
  AlertTriangle,
  Trophy,
  Users,
  Activity,
  Cpu,
  Database
} from "lucide-react";
import { cn } from "@/lib/utils";
import { RAPTORModel, EPMModel, TeamChemistryModel, type PlayerImpactMetrics, type TeamImpactMetrics } from "@/lib/analytics/advanced-metrics";
import { PlayerEvaluationEngine, type PlayerEvaluationResult } from "@/lib/analytics/player-evaluation";
import { FormulaDocumentation } from "./FormulaDocumentation";

interface AdvancedAnalyticsDashboardProps {
  teamId?: string;
  playerId?: string;
  season: string;
}

export function AdvancedAnalyticsDashboard({ teamId, playerId, season }: AdvancedAnalyticsDashboardProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeModel, setActiveModel] = useState<string>("raptor");
  const [playerMetrics, setPlayerMetrics] = useState<PlayerImpactMetrics[]>([]);
  const [teamMetrics, setTeamMetrics] = useState<TeamImpactMetrics | null>(null);
  const [teamChemistry, setTeamChemistry] = useState<any>(null);

  useEffect(() => {
    const fetchAdvancedMetrics = async () => {
      try {
        setLoading(true);
        setError(null);

        // Simulate fetching real data and calculating advanced metrics
        const mockPlayerData = generateMockPlayerData();
        const mockTeamData = generateMockTeamData();

        // Calculate RAPTOR metrics
        const raptorMetrics = mockPlayerData.map(player => {
          const raptor = RAPTORModel.calculateRAPTOR(player);
          return {
            ...player,
            offensiveRAPTOR: raptor.offensive,
            defensiveRAPTOR: raptor.defensive,
            totalRAPTOR: raptor.total
          };
        });

        // Calculate EPM metrics
        const epmMetrics = raptorMetrics.map(player => {
          const epm = EPMModel.calculateEPM(player, mockTeamData);
          return {
            ...player,
            offensiveEPM: epm.offensive,
            defensiveEPM: epm.defensive,
            totalEPM: epm.total
          };
        });

        // Calculate team chemistry
        const chemistry = TeamChemistryModel.calculateTeamChemistry(mockTeamData, epmMetrics);

        setPlayerMetrics(epmMetrics);
        setTeamMetrics(mockTeamData);
        setTeamChemistry(chemistry);
      } catch (err) {
        console.error('Error fetching advanced metrics:', err);
        setError('Failed to load advanced analytics');
      } finally {
        setLoading(false);
      }
    };

    fetchAdvancedMetrics();
  }, [teamId, playerId, season, activeModel]);

  const generateMockPlayerData = (): any[] => {
    return [
      {
        playerId: "1",
        playerName: "Stephen Curry",
        team: "GSW",
        position: "PG",
        minutesPlayed: 2200,
        gamesPlayed: 74,
        points: 26.4,
        assists: 5.1,
        rebounds: 4.5,
        steals: 0.9,
        blocks: 0.4,
        turnovers: 3.1,
        fieldGoalAttempts: 20.1,
        trueShooting: 0.599,
        usageRate: 0.331,
        assistRatio: 0.24,
        turnoverRatio: 0.14,
        defensiveRating: 115.2,
        threePtAttempts: 11.7,
        threePtPct: 0.427,
        experience: 15,
        clutchPerformance: 1.2
      },
      {
        playerId: "2",
        playerName: "Draymond Green",
        team: "GSW",
        position: "PF",
        minutesPlayed: 2100,
        gamesPlayed: 71,
        points: 8.5,
        assists: 6.0,
        rebounds: 7.2,
        steals: 0.8,
        blocks: 0.8,
        turnovers: 2.8,
        fieldGoalAttempts: 7.1,
        trueShooting: 0.641,
        usageRate: 0.155,
        assistRatio: 0.31,
        turnoverRatio: 0.18,
        defensiveRating: 108.9,
        threePtAttempts: 3.1,
        threePtPct: 0.312,
        experience: 12,
        clutchPerformance: 0.8
      }
    ];
  };

  const generateMockTeamData = (): any => {
    return {
      teamId: "1610612744",
      teamName: "Golden State Warriors",
      season: season,
      offensiveRating: 116.3,
      defensiveRating: 116.8,
      netRating: -0.5,
      pace: 102.1,
      assistRatio: 0.63,
      passesPerGame: 312,
      secondaryAssists: 12,
      deflections: 18,
      contestedShots: 52,
      helpDefense: 23,
      effectiveFieldGoalPct: 0.566,
      turnoverRate: 0.142,
      offensiveReboundPct: 0.231,
      freeThrowRate: 0.198
    };
  };

  const getMetricColor = (value: number, isPositive: boolean = true): string => {
    if (isPositive) {
      if (value > 2) return "text-green-600";
      if (value > 0) return "text-yellow-600";
      return "text-red-600";
    } else {
      if (value < -2) return "text-green-600";
      if (value < 0) return "text-yellow-600";
      return "text-red-600";
    }
  };

  const getPercentileColor = (percentile: number): string => {
    if (percentile >= 90) return "text-green-600";
    if (percentile >= 75) return "text-blue-600";
    if (percentile >= 50) return "text-yellow-600";
    if (percentile >= 25) return "text-orange-600";
    return "text-red-600";
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-10 w-32" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Brain className="w-6 h-6 text-blue-500" />
            Advanced Analytics Dashboard
          </h2>
          {error && (
            <Badge variant="destructive" className="text-xs">
              <AlertTriangle className="w-3 h-3 mr-1" />
              {error}
            </Badge>
          )}
          <Badge variant="secondary" className="text-xs">
            <Cpu className="w-3 h-3 mr-1" />
            ML Models Active
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.location.reload()}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh Models
          </Button>
          <Select value={activeModel} onValueChange={setActiveModel}>
            <SelectTrigger className="w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="raptor">RAPTOR</SelectItem>
              <SelectItem value="epm">EPM</SelectItem>
              <SelectItem value="lebron">LEBRON</SelectItem>
              <SelectItem value="composite">Composite</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <Tabs defaultValue="player-impact" className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="player-impact">Player Impact</TabsTrigger>
          <TabsTrigger value="team-metrics">Team Metrics</TabsTrigger>
          <TabsTrigger value="chemistry">Team Chemistry</TabsTrigger>
          <TabsTrigger value="predictions">Predictions</TabsTrigger>
          <TabsTrigger value="formulas">Formulas</TabsTrigger>
        </TabsList>

        {/* Player Impact Tab */}
        <TabsContent value="player-impact" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {playerMetrics.map((player, index) => (
              <Card key={index}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-lg">{player.playerName}</CardTitle>
                      <CardDescription>{player.position} • {player.team}</CardDescription>
                    </div>
                    <Badge variant="outline">{player.gamesPlayed} GP</Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {/* RAPTOR Metrics */}
                    <div>
                      <h4 className="font-semibold mb-2 flex items-center gap-2">
                        <Target className="w-4 h-4" />
                        RAPTOR Ratings
                      </h4>
                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div className="text-center">
                          <div className={`text-lg font-bold ${getMetricColor(player.offensiveRAPTOR)}`}>
                            {player.offensiveRAPTOR?.toFixed(1) || "0.0"}
                          </div>
                          <div className="text-muted-foreground">Offense</div>
                        </div>
                        <div className="text-center">
                          <div className={`text-lg font-bold ${getMetricColor(player.defensiveRAPTOR)}`}>
                            {player.defensiveRAPTOR?.toFixed(1) || "0.0"}
                          </div>
                          <div className="text-muted-foreground">Defense</div>
                        </div>
                        <div className="text-center">
                          <div className={`text-lg font-bold ${getMetricColor(player.totalRAPTOR)}`}>
                            {player.totalRAPTOR?.toFixed(1) || "0.0"}
                          </div>
                          <div className="text-muted-foreground">Total</div>
                        </div>
                      </div>
                    </div>

                    {/* EPM Metrics */}
                    <div>
                      <h4 className="font-semibold mb-2 flex items-center gap-2">
                        <Activity className="w-4 h-4" />
                        EPM Ratings
                      </h4>
                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div className="text-center">
                          <div className={`text-lg font-bold ${getMetricColor(player.offensiveEPM)}`}>
                            {player.offensiveEPM?.toFixed(1) || "0.0"}
                          </div>
                          <div className="text-muted-foreground">Offense</div>
                        </div>
                        <div className="text-center">
                          <div className={`text-lg font-bold ${getMetricColor(player.defensiveEPM)}`}>
                            {player.defensiveEPM?.toFixed(1) || "0.0"}
                          </div>
                          <div className="text-muted-foreground">Defense</div>
                        </div>
                        <div className="text-center">
                          <div className={`text-lg font-bold ${getMetricColor(player.totalEPM)}`}>
                            {player.totalEPM?.toFixed(1) || "0.0"}
                          </div>
                          <div className="text-muted-foreground">Total</div>
                        </div>
                      </div>
                    </div>

                    {/* Impact Visualization */}
                    <div>
                      <h4 className="font-semibold mb-2">Impact Percentiles</h4>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span>Overall Impact</span>
                          <span className={getPercentileColor(85)}>85th percentile</span>
                        </div>
                        <Progress value={85} className="h-2" />

                        <div className="flex items-center justify-between text-sm">
                          <span>Offensive Impact</span>
                          <span className={getPercentileColor(92)}>92nd percentile</span>
                        </div>
                        <Progress value={92} className="h-2" />

                        <div className="flex items-center justify-between text-sm">
                          <span>Defensive Impact</span>
                          <span className={getPercentileColor(45)}>45th percentile</span>
                        </div>
                        <Progress value={45} className="h-2" />
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Team Metrics Tab */}
        <TabsContent value="team-metrics" className="space-y-6">
          {teamMetrics && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {/* Four Factors */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="w-5 h-5" />
                    Four Factors
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-sm">Effective FG%</span>
                      <span className="font-medium">{(teamMetrics.effectiveFieldGoalPct * 100).toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Turnover Rate</span>
                      <span className="font-medium">{(teamMetrics.turnoverRate * 100).toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Off. Rebound %</span>
                      <span className="font-medium">{(teamMetrics.offensiveReboundPct * 100).toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Free Throw Rate</span>
                      <span className="font-medium">{(teamMetrics.freeThrowRate * 100).toFixed(1)}%</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Advanced Ratings */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="w-5 h-5" />
                    Advanced Ratings
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-sm">Offensive Rating</span>
                      <span className={`font-medium ${getMetricColor(teamMetrics.offensiveRating - 112)}`}>
                        {teamMetrics.offensiveRating.toFixed(1)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Defensive Rating</span>
                      <span className={`font-medium ${getMetricColor(112 - teamMetrics.defensiveRating)}`}>
                        {teamMetrics.defensiveRating.toFixed(1)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Net Rating</span>
                      <span className={`font-medium ${getMetricColor(teamMetrics.netRating)}`}>
                        {teamMetrics.netRating > 0 ? '+' : ''}{teamMetrics.netRating.toFixed(1)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Pace</span>
                      <span className="font-medium">{teamMetrics.pace.toFixed(1)}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Predictive Metrics */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Zap className="w-5 h-5" />
                    Predictive Metrics
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-sm">Projected Wins</span>
                      <span className="font-medium">42.3</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Playoff Probability</span>
                      <span className="font-medium text-yellow-600">67%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Championship Odds</span>
                      <span className="font-medium text-blue-600">8.2%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">SOS Rank</span>
                      <span className="font-medium">12th</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* Team Chemistry Tab */}
        <TabsContent value="chemistry" className="space-y-6">
          {teamChemistry && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Users className="w-5 h-5" />
                    Team Chemistry Analysis
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div>
                      <div className="flex justify-between mb-2">
                        <span className="text-sm">Ball Movement</span>
                        <span className="font-medium">{teamChemistry.ballMovement.toFixed(1)}</span>
                      </div>
                      <Progress value={teamChemistry.ballMovement} className="h-2" />
                    </div>

                    <div>
                      <div className="flex justify-between mb-2">
                        <span className="text-sm">Defensive Rotations</span>
                        <span className="font-medium">{teamChemistry.defensiveRotations.toFixed(1)}</span>
                      </div>
                      <Progress value={teamChemistry.defensiveRotations} className="h-2" />
                    </div>

                    <div>
                      <div className="flex justify-between mb-2">
                        <span className="text-sm">Lineup Synergy</span>
                        <span className="font-medium">{teamChemistry.lineupSynergy.toFixed(1)}</span>
                      </div>
                      <Progress value={teamChemistry.lineupSynergy} className="h-2" />
                    </div>

                    <div>
                      <div className="flex justify-between mb-2">
                        <span className="text-sm">Leadership Impact</span>
                        <span className="font-medium">{teamChemistry.leadershipImpact.toFixed(1)}</span>
                      </div>
                      <Progress value={teamChemistry.leadershipImpact} className="h-2" />
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Overall Chemistry Score</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-center">
                    <div className="text-4xl font-bold text-blue-600 mb-2">
                      {teamChemistry.overallChemistry.toFixed(1)}
                    </div>
                    <div className="text-muted-foreground mb-4">out of 100</div>
                    <Progress value={teamChemistry.overallChemistry} className="h-4" />
                    <div className="mt-4 text-sm text-muted-foreground">
                      {teamChemistry.overallChemistry > 80 ? "Excellent chemistry" :
                       teamChemistry.overallChemistry > 60 ? "Good chemistry" :
                       teamChemistry.overallChemistry > 40 ? "Average chemistry" : "Needs improvement"}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* Predictions Tab */}
        <TabsContent value="predictions" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Trophy className="w-5 h-5" />
                  Season Projections
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="text-center">
                    <div className="text-2xl font-bold">42-40</div>
                    <div className="text-sm text-muted-foreground">Projected Record</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-yellow-600">67%</div>
                    <div className="text-sm text-muted-foreground">Playoff Odds</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">8.2%</div>
                    <div className="text-sm text-muted-foreground">Championship Odds</div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="w-5 h-5" />
                  Model Confidence
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-sm">RAPTOR Model</span>
                      <span className="text-sm">94%</span>
                    </div>
                    <Progress value={94} className="h-2" />
                  </div>
                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-sm">EPM Model</span>
                      <span className="text-sm">87%</span>
                    </div>
                    <Progress value={87} className="h-2" />
                  </div>
                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-sm">Chemistry Model</span>
                      <span className="text-sm">91%</span>
                    </div>
                    <Progress value={91} className="h-2" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Key Insights</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  <div className="flex items-start gap-2">
                    <div className="w-2 h-2 bg-green-500 rounded-full mt-1.5"></div>
                    <span>Strong offensive chemistry with high ball movement</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <div className="w-2 h-2 bg-yellow-500 rounded-full mt-1.5"></div>
                    <span>Defensive consistency needs improvement</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <div className="w-2 h-2 bg-blue-500 rounded-full mt-1.5"></div>
                    <span>Veteran leadership provides stability</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <div className="w-2 h-2 bg-red-500 rounded-full mt-1.5"></div>
                    <span>Injury risk elevated for key players</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Formulas Tab */}
        <TabsContent value="formulas" className="space-y-6">
          <FormulaDocumentation />
        </TabsContent>
      </Tabs>
    </div>
  );
}
