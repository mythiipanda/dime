"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { 
  BarChart3, 
  Users, 
  TrendingUp, 
  Trophy, 
  LineChart, 
  Users2, 
  DollarSign,
  Clock,
  Target,
  Zap,
  Brain,
  Shield,
  Swords,
  Crown,
  Activity,
  TrendingDown,
  Star,
  AlertTriangle
} from "lucide-react";

// Advanced League Analytics Data Structures
interface TeamChemistry {
  teamId: string;
  teamName: string;
  teamAbbr: string;
  
  // Chemistry Metrics
  ballMovement: number; // Passes per possession
  teamAssists: number; // Team assist %
  ballSticking: number; // Time of possession
  synergy: number; // How well players complement each other
  
  // Cohesion Indicators
  lineupStability: number; // How consistent lineups are
  roleClarity: number; // How defined player roles are
  sacrifice: number; // Players taking reduced roles for team success
  
  // On-court Chemistry
  netRatingBest5: number; // Best 5-man lineup net rating
  netRatingWorst5: number; // Worst 5-man lineup net rating
  chemistryRating: number; // Overall chemistry score (0-100)
}

interface SalaryCapEfficiency {
  teamId: string;
  teamName: string;
  teamAbbr: string;
  
  // Financial Metrics
  totalSalary: number;
  capSpace: number;
  luxuryTaxBill: number;
  
  // Efficiency Metrics
  winsPerDollar: number; // Wins divided by salary
  valueAboveReplacement: number; // VAR per dollar spent
  contractEfficiency: number; // Performance vs contract value
  
  // Future Outlook
  futureCapFlexibility: number; // Cap space projection
  contractOptimization: number; // How well contracts are structured
  sustainabilityRating: number; // Long-term financial health
}

interface ClutchAnalysis {
  teamId: string;
  teamName: string;
  teamAbbr: string;
  
  // Clutch Performance (Last 5 minutes, 5 point game)
  clutchRecord: string; // W-L in clutch games
  clutchNetRating: number;
  clutchOffRating: number;
  clutchDefRating: number;
  
  // Clutch Factors
  starPerformance: number; // How stars perform in clutch
  coaching: number; // Late game coaching decisions
  execution: number; // How well they execute plays
  mentalToughness: number; // Performance under pressure
  
  // Situational Clutch
  homeClutch: number; // Home clutch performance
  roadClutch: number; // Away clutch performance
  clutchTier: 'Elite' | 'Good' | 'Average' | 'Poor';
}

interface CoachingImpact {
  teamId: string;
  teamName: string;
  teamAbbr: string;
  coachName: string;
  
  // Strategic Impact
  adjustmentRating: number; // In-game adjustments
  playDesign: number; // Quality of play calls
  timeoutUsage: number; // Strategic timeout usage
  rotationOptimization: number; // How well rotations are managed
  
  // Player Development
  playerImprovement: number; // How much players improve
  rookieIntegration: number; // How well rookies are developed
  veteranManagement: number; // Managing veteran players
  
  // System Implementation
  offensiveSystem: number; // How effective the system is
  defensiveSystem: number; // Defensive scheme effectiveness
  cultureBuilding: number; // Team culture and morale
  
  overallImpact: number; // Overall coaching grade (0-100)
}

interface PlayStyle {
  teamId: string;
  teamName: string;
  teamAbbr: string;
  
  // Offensive Style
  pace: number;
  threePointRate: number; // % of shots that are 3s
  assistRate: number;
  turnoverRate: number;
  offensiveReboundRate: number;
  
  // Defensive Style
  stealRate: number;
  blockRate: number;
  foulRate: number;
  defensiveReboundRate: number;
  
  // Style Classification
  offensiveStyle: 'Fast-Paced' | 'Methodical' | 'Balanced';
  defensiveStyle: 'Aggressive' | 'Disciplined' | 'Switch-Heavy';
  overallIdentity: string;
  
  // Effectiveness vs League
  winProbabilityVsPace: number; // How their style correlates with wins
  matchupAdvantages: string[]; // What styles they beat
  matchupDisadvantages: string[]; // What styles give them trouble
}

// Mock API Functions
const mockTeamChemistryAPI = async (season: string): Promise<TeamChemistry[]> => {
  await new Promise(resolve => setTimeout(resolve, 600));
  
  return [
    {
      teamId: "1", teamName: "Boston Celtics", teamAbbr: "BOS",
      ballMovement: 312, teamAssists: 0.647, ballSticking: 2.8, synergy: 92,
      lineupStability: 87, roleClarity: 91, sacrifice: 89,
      netRatingBest5: 16.2, netRatingWorst5: -8.3, chemistryRating: 94
    },
    {
      teamId: "2", teamName: "Denver Nuggets", teamAbbr: "DEN", 
      ballMovement: 328, teamAssists: 0.672, ballSticking: 2.6, synergy: 96,
      lineupStability: 91, roleClarity: 94, sacrifice: 92,
      netRatingBest5: 18.7, netRatingWorst5: -5.1, chemistryRating: 97
    },
    {
      teamId: "3", teamName: "Minnesota Timberwolves", teamAbbr: "MIN",
      ballMovement: 298, teamAssists: 0.598, ballSticking: 3.2, synergy: 85,
      lineupStability: 78, roleClarity: 81, sacrifice: 88,
      netRatingBest5: 14.1, netRatingWorst5: -12.7, chemistryRating: 82
    },
    {
      teamId: "4", teamName: "Oklahoma City Thunder", teamAbbr: "OKC",
      ballMovement: 305, teamAssists: 0.634, ballSticking: 2.9, synergy: 88,
      lineupStability: 83, roleClarity: 86, sacrifice: 90,
      netRatingBest5: 15.8, netRatingWorst5: -7.9, chemistryRating: 89
    },
    {
      teamId: "5", teamName: "Los Angeles Lakers", teamAbbr: "LAL",
      ballMovement: 284, teamAssists: 0.571, ballSticking: 3.4, synergy: 76,
      lineupStability: 68, roleClarity: 73, sacrifice: 71,
      netRatingBest5: 8.2, netRatingWorst5: -18.5, chemistryRating: 71
    }
  ];
};

const mockSalaryCapEfficiencyAPI = async (season: string): Promise<SalaryCapEfficiency[]> => {
  await new Promise(resolve => setTimeout(resolve, 650));
  
  return [
    {
      teamId: "1", teamName: "Oklahoma City Thunder", teamAbbr: "OKC",
      totalSalary: 142800000, capSpace: 27200000, luxuryTaxBill: 0,
      winsPerDollar: 0.000398, valueAboveReplacement: 8.2, contractEfficiency: 94,
      futureCapFlexibility: 91, contractOptimization: 88, sustainabilityRating: 97
    },
    {
      teamId: "2", teamName: "San Antonio Spurs", teamAbbr: "SAS",
      totalSalary: 128600000, capSpace: 41400000, luxuryTaxBill: 0,
      winsPerDollar: 0.000171, valueAboveReplacement: 3.1, contractEfficiency: 72,
      futureCapFlexibility: 95, contractOptimization: 89, sustainabilityRating: 89
    },
    {
      teamId: "3", teamName: "Boston Celtics", teamAbbr: "BOS",
      totalSalary: 181700000, capSpace: -11700000, luxuryTaxBill: 52800000,
      winsPerDollar: 0.000352, valueAboveReplacement: 12.8, contractEfficiency: 91,
      futureCapFlexibility: 34, contractOptimization: 76, sustainabilityRating: 68
    },
    {
      teamId: "4", teamName: "Denver Nuggets", teamAbbr: "DEN",
      totalSalary: 173200000, capSpace: -3200000, luxuryTaxBill: 28900000,
      winsPerDollar: 0.000329, valueAboveReplacement: 11.4, contractEfficiency: 87,
      futureCapFlexibility: 42, contractOptimization: 82, sustainabilityRating: 74
    },
    {
      teamId: "5", teamName: "Phoenix Suns", teamAbbr: "PHX",
      totalSalary: 189400000, capSpace: -19400000, luxuryTaxBill: 87300000,
      winsPerDollar: 0.000238, valueAboveReplacement: 6.7, contractEfficiency: 63,
      futureCapFlexibility: 12, contractOptimization: 45, sustainabilityRating: 28
    }
  ];
};

const mockClutchAnalysisAPI = async (season: string): Promise<ClutchAnalysis[]> => {
  await new Promise(resolve => setTimeout(resolve, 550));
  
  return [
    {
      teamId: "1", teamName: "Denver Nuggets", teamAbbr: "DEN",
      clutchRecord: "11-3", clutchNetRating: 9.2, clutchOffRating: 118.7, clutchDefRating: 109.5,
      starPerformance: 96, coaching: 92, execution: 89, mentalToughness: 94,
      homeClutch: 7.8, roadClutch: 11.1, clutchTier: 'Elite'
    },
    {
      teamId: "2", teamName: "Boston Celtics", teamAbbr: "BOS",
      clutchRecord: "9-4", clutchNetRating: 6.8, clutchOffRating: 115.2, clutchDefRating: 108.4,
      starPerformance: 88, coaching: 91, execution: 86, mentalToughness: 89,
      homeClutch: 9.2, roadClutch: 4.1, clutchTier: 'Elite'
    },
    {
      teamId: "3", teamName: "Oklahoma City Thunder", teamAbbr: "OKC",
      clutchRecord: "8-5", clutchNetRating: 4.1, clutchOffRating: 112.8, clutchDefRating: 108.7,
      starPerformance: 91, coaching: 84, execution: 82, mentalToughness: 87,
      homeClutch: 6.7, roadClutch: 1.2, clutchTier: 'Good'
    },
    {
      teamId: "4", teamName: "Milwaukee Bucks", teamAbbr: "MIL",
      clutchRecord: "5-8", clutchNetRating: -3.2, clutchOffRating: 108.1, clutchDefRating: 111.3,
      starPerformance: 76, coaching: 67, execution: 71, mentalToughness: 69,
      homeClutch: 1.2, roadClutch: -7.8, clutchTier: 'Poor'
    },
    {
      teamId: "5", teamName: "Los Angeles Lakers", teamAbbr: "LAL",
      clutchRecord: "6-7", clutchNetRating: -1.8, clutchOffRating: 109.4, clutchDefRating: 111.2,
      starPerformance: 82, coaching: 73, execution: 69, mentalToughness: 74,
      homeClutch: 2.8, roadClutch: -6.1, clutchTier: 'Average'
    }
  ];
};

const mockCoachingImpactAPI = async (season: string): Promise<CoachingImpact[]> => {
  await new Promise(resolve => setTimeout(resolve, 700));
  
  return [
    {
      teamId: "1", teamName: "San Antonio Spurs", teamAbbr: "SAS", coachName: "Gregg Popovich",
      adjustmentRating: 98, playDesign: 94, timeoutUsage: 91, rotationOptimization: 89,
      playerImprovement: 96, rookieIntegration: 97, veteranManagement: 99,
      offensiveSystem: 85, defensiveSystem: 92, cultureBuilding: 99,
      overallImpact: 95
    },
    {
      teamId: "2", teamName: "Denver Nuggets", teamAbbr: "DEN", coachName: "Michael Malone",
      adjustmentRating: 91, playDesign: 89, timeoutUsage: 88, rotationOptimization: 93,
      playerImprovement: 89, rookieIntegration: 86, veteranManagement: 92,
      offensiveSystem: 96, defensiveSystem: 87, cultureBuilding: 91,
      overallImpact: 91
    },
    {
      teamId: "3", teamName: "Boston Celtics", teamAbbr: "BOS", coachName: "Joe Mazzulla",
      adjustmentRating: 85, playDesign: 91, timeoutUsage: 83, rotationOptimization: 88,
      playerImprovement: 84, rookieIntegration: 79, veteranManagement: 86,
      offensiveSystem: 93, defensiveSystem: 95, cultureBuilding: 87,
      overallImpact: 88
    },
    {
      teamId: "4", teamName: "Oklahoma City Thunder", teamAbbr: "OKC", coachName: "Mark Daigneault",
      adjustmentRating: 89, playDesign: 92, timeoutUsage: 90, rotationOptimization: 94,
      playerImprovement: 95, rookieIntegration: 93, veteranManagement: 85,
      offensiveSystem: 89, defensiveSystem: 91, cultureBuilding: 93,
      overallImpact: 92
    },
    {
      teamId: "5", teamName: "Los Angeles Lakers", teamAbbr: "LAL", coachName: "Darvin Ham",
      adjustmentRating: 72, playDesign: 76, timeoutUsage: 71, rotationOptimization: 68,
      playerImprovement: 74, rookieIntegration: 71, veteranManagement: 79,
      offensiveSystem: 78, defensiveSystem: 73, cultureBuilding: 76,
      overallImpact: 74
    }
  ];
};

const mockPlayStyleAPI = async (season: string): Promise<PlayStyle[]> => {
  await new Promise(resolve => setTimeout(resolve, 500));
  
  return [
    {
      teamId: "1", teamName: "Boston Celtics", teamAbbr: "BOS",
      pace: 99.8, threePointRate: 0.524, assistRate: 0.647, turnoverRate: 0.128, offensiveReboundRate: 0.234,
      stealRate: 0.089, blockRate: 0.071, foulRate: 0.198, defensiveReboundRate: 0.789,
      offensiveStyle: 'Fast-Paced', defensiveStyle: 'Switch-Heavy', overallIdentity: 'Modern Versatile',
      winProbabilityVsPace: 0.68, 
      matchupAdvantages: ['Slow Traditional Teams', 'Poor 3pt Defense'],
      matchupDisadvantages: ['Elite Athletic Teams', 'Strong Rim Protection']
    },
    {
      teamId: "2", teamName: "Denver Nuggets", teamAbbr: "DEN",
      pace: 98.2, threePointRate: 0.412, assistRate: 0.672, turnoverRate: 0.135, offensiveReboundRate: 0.267,
      stealRate: 0.076, blockRate: 0.058, foulRate: 0.189, defensiveReboundRate: 0.801,
      offensiveStyle: 'Methodical', defensiveStyle: 'Disciplined', overallIdentity: 'Cerebral Execution',
      winProbabilityVsPace: 0.71,
      matchupAdvantages: ['Impatient Teams', 'Poor Interior Defense'],
      matchupDisadvantages: ['High-Pressure Defense', 'Elite Perimeter Teams']
    },
    {
      teamId: "3", teamName: "Oklahoma City Thunder", teamAbbr: "OKC",
      pace: 100.5, threePointRate: 0.489, assistRate: 0.634, turnoverRate: 0.142, offensiveReboundRate: 0.289,
      stealRate: 0.098, blockRate: 0.084, foulRate: 0.203, defensiveReboundRate: 0.752,
      offensiveStyle: 'Fast-Paced', defensiveStyle: 'Aggressive', overallIdentity: 'Young Athletic',
      winProbabilityVsPace: 0.63,
      matchupAdvantages: ['Veteran Teams', 'Low Energy Teams'],
      matchupDisadvantages: ['Experienced Playoff Teams', 'Strong Half-Court Offense']
    },
    {
      teamId: "4", teamName: "Minnesota Timberwolves", teamAbbr: "MIN",
      pace: 97.1, threePointRate: 0.456, assistRate: 0.598, turnoverRate: 0.146, offensiveReboundRate: 0.245,
      stealRate: 0.085, blockRate: 0.092, foulRate: 0.215, defensiveReboundRate: 0.823,
      offensiveStyle: 'Methodical', defensiveStyle: 'Aggressive', overallIdentity: 'Defense-First',
      winProbabilityVsPace: 0.59,
      matchupAdvantages: ['High-Pace Teams', 'Poor Shooting Teams'],
      matchupDisadvantages: ['Elite Shooting Teams', 'Creative Offenses']
    },
    {
      teamId: "5", teamName: "Los Angeles Lakers", teamAbbr: "LAL",
      pace: 101.3, threePointRate: 0.398, assistRate: 0.571, turnoverRate: 0.154, offensiveReboundRate: 0.298,
      stealRate: 0.081, blockRate: 0.063, foulRate: 0.207, defensiveReboundRate: 0.724,
      offensiveStyle: 'Balanced', defensiveStyle: 'Switch-Heavy', overallIdentity: 'Star-Dependent',
      winProbabilityVsPace: 0.51,
      matchupAdvantages: ['Size-Disadvantaged Teams', 'Interior-Focused Teams'],
      matchupDisadvantages: ['Deep Teams', 'High-Energy Teams']
    }
  ];
};

export default function DeepDiveAnalyticsHub() {
  const [currentSeason, setCurrentSeason] = useState("2023-24");

  // Team Chemistry State
  const [teamChemistry, setTeamChemistry] = useState<TeamChemistry[]>([]);
  const [isLoadingChemistry, setIsLoadingChemistry] = useState(false);

  // Salary Cap Efficiency State
  const [salaryEfficiency, setSalaryEfficiency] = useState<SalaryCapEfficiency[]>([]);
  const [isLoadingSalary, setIsLoadingSalary] = useState(false);

  // Clutch Analysis State
  const [clutchAnalysis, setClutchAnalysis] = useState<ClutchAnalysis[]>([]);
  const [isLoadingClutch, setIsLoadingClutch] = useState(false);

  // Coaching Impact State
  const [coachingImpact, setCoachingImpact] = useState<CoachingImpact[]>([]);
  const [isLoadingCoaching, setIsLoadingCoaching] = useState(false);

  // Play Style State
  const [playStyles, setPlayStyles] = useState<PlayStyle[]>([]);
  const [isLoadingStyles, setIsLoadingStyles] = useState(false);

  useEffect(() => {
    const fetchAllData = async () => {
      setIsLoadingChemistry(true);
      setIsLoadingSalary(true);
      setIsLoadingClutch(true);
      setIsLoadingCoaching(true);
      setIsLoadingStyles(true);

      try {
        const [chemistry, salary, clutch, coaching, styles] = await Promise.all([
          mockTeamChemistryAPI(currentSeason),
          mockSalaryCapEfficiencyAPI(currentSeason),
          mockClutchAnalysisAPI(currentSeason),
          mockCoachingImpactAPI(currentSeason),
          mockPlayStyleAPI(currentSeason)
        ]);

        setTeamChemistry(chemistry);
        setSalaryEfficiency(salary);
        setClutchAnalysis(clutch);
        setCoachingImpact(coaching);
        setPlayStyles(styles);
      } catch (error) {
        console.error('Error fetching analytics data:', error);
      } finally {
        setIsLoadingChemistry(false);
        setIsLoadingSalary(false);
        setIsLoadingClutch(false);
        setIsLoadingCoaching(false);
        setIsLoadingStyles(false);
      }
    };

    fetchAllData();
  }, [currentSeason]);

  const getClutchTierColor = (tier: string) => {
    switch (tier) {
      case 'Elite': return 'text-green-600';
      case 'Good': return 'text-blue-600';
      case 'Average': return 'text-yellow-600';
      case 'Poor': return 'text-red-600';
      default: return '';
    }
  };

  const getClutchTierBadge = (tier: string) => {
    const variants = {
      'Elite': 'default',
      'Good': 'secondary',
      'Average': 'outline',
      'Poor': 'destructive'
    } as const;
    return <Badge variant={variants[tier as keyof typeof variants]}>{tier}</Badge>;
  };

  return (
    <div className="flex-1 space-y-8 p-4 md:p-6 lg:p-8">
      <div className="flex items-center justify-between space-y-2">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Brain className="h-8 w-8 text-primary" />
            Deep Dive Analytics Hub
          </h1>
          <p className="text-muted-foreground">
            Advanced team analytics for strategic decision making
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Select value={currentSeason} onValueChange={setCurrentSeason}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Select Season" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="2023-24">2023-24 Season</SelectItem>
              <SelectItem value="2022-23">2022-23 Season</SelectItem>
              <SelectItem value="2021-22">2021-22 Season</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <Tabs defaultValue="team_chemistry" className="w-full">
        <TabsList className="grid w-full grid-cols-2 lg:grid-cols-5 gap-1 h-auto">
          <TabsTrigger value="team_chemistry" className="py-2 text-xs">
            <Users2 className="h-4 w-4 mr-1" />
            Chemistry
          </TabsTrigger>
          <TabsTrigger value="salary_efficiency" className="py-2 text-xs">
            <DollarSign className="h-4 w-4 mr-1" />
            Cap Efficiency
          </TabsTrigger>
          <TabsTrigger value="clutch_analysis" className="py-2 text-xs">
            <Clock className="h-4 w-4 mr-1" />
            Clutch Tiers
          </TabsTrigger>
          <TabsTrigger value="coaching_impact" className="py-2 text-xs">
            <Target className="h-4 w-4 mr-1" />
            Coaching
          </TabsTrigger>
          <TabsTrigger value="play_styles" className="py-2 text-xs">
            <Activity className="h-4 w-4 mr-1" />
            Play Styles
          </TabsTrigger>
        </TabsList>

        <TabsContent value="team_chemistry" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users2 className="h-5 w-5" />
                Team Chemistry Analysis
              </CardTitle>
              <CardDescription>
                Comprehensive analysis of team chemistry, ball movement, and player synergy
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoadingChemistry ? (
                <Skeleton className="h-96 w-full" />
              ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Team</TableHead>
                      <TableHead className="text-center">Chemistry</TableHead>
                      <TableHead className="text-center">Ball Movement</TableHead>
                      <TableHead className="text-center">Synergy</TableHead>
                      <TableHead className="text-center">Role Clarity</TableHead>
                      <TableHead className="text-center">Best Lineup</TableHead>
                      <TableHead className="text-center">Worst Lineup</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                    {teamChemistry.map((team) => (
                        <TableRow key={team.teamId}>
                        <TableCell>
                          <div className="font-medium">{team.teamAbbr}</div>
                          <div className="text-xs text-muted-foreground">{team.teamName}</div>
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Progress value={team.chemistryRating} className="w-16 h-2" />
                            <span className="font-mono text-sm">{team.chemistryRating}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-center font-mono">{team.ballMovement}</TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Progress value={team.synergy} className="w-12 h-2" />
                            <span className="font-mono text-sm">{team.synergy}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Progress value={team.roleClarity} className="w-12 h-2" />
                            <span className="font-mono text-sm">{team.roleClarity}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          <span className="font-mono text-green-600">+{team.netRatingBest5.toFixed(1)}</span>
                        </TableCell>
                        <TableCell className="text-center">
                          <span className="font-mono text-red-600">{team.netRatingWorst5.toFixed(1)}</span>
                        </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="salary_efficiency" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="h-5 w-5" />
                Salary Cap Efficiency Rankings
              </CardTitle>
              <CardDescription>
                Analysis of team financial efficiency and future sustainability
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoadingSalary ? (
                <Skeleton className="h-96 w-full" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Team</TableHead>
                      <TableHead className="text-center">Wins/$M</TableHead>
                      <TableHead className="text-center">Contract Eff</TableHead>
                      <TableHead className="text-center">Tax Bill</TableHead>
                      <TableHead className="text-center">Future Flex</TableHead>
                      <TableHead className="text-center">Sustainability</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {salaryEfficiency.map((team) => (
                      <TableRow key={team.teamId}>
                        <TableCell>
                          <div className="font-medium">{team.teamAbbr}</div>
                          <div className="text-xs text-muted-foreground">{team.teamName}</div>
                        </TableCell>
                        <TableCell className="text-center font-mono">
                          {(team.winsPerDollar * 1000000).toFixed(3)}
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Progress value={team.contractEfficiency} className="w-12 h-2" />
                            <span className="font-mono text-sm">{team.contractEfficiency}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          <span className={`font-mono ${team.luxuryTaxBill > 0 ? 'text-red-600' : 'text-green-600'}`}>
                            ${team.luxuryTaxBill > 0 ? (team.luxuryTaxBill / 1000000).toFixed(1) + 'M' : '0'}
                          </span>
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Progress value={team.futureCapFlexibility} className="w-12 h-2" />
                            <span className="font-mono text-sm">{team.futureCapFlexibility}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Progress value={team.sustainabilityRating} className="w-12 h-2" />
                            <span className={`font-mono text-sm ${team.sustainabilityRating > 80 ? 'text-green-600' : team.sustainabilityRating < 50 ? 'text-red-600' : 'text-yellow-600'}`}>
                              {team.sustainabilityRating}
                            </span>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="clutch_analysis" className="space-y-6">
          <Card>
             <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5" />
                Clutch Performance Tiers
              </CardTitle>
              <CardDescription>
                Analysis of late-game performance and clutch situation effectiveness
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoadingClutch ? (
                <Skeleton className="h-96 w-full" />
              ) : (
                    <Table>
                        <TableHeader>
                        <TableRow>
                            <TableHead>Team</TableHead>
                      <TableHead className="text-center">Record</TableHead>
                      <TableHead className="text-center">Net Rtg</TableHead>
                      <TableHead className="text-center">Star Perf</TableHead>
                      <TableHead className="text-center">Coaching</TableHead>
                      <TableHead className="text-center">Mental Tough</TableHead>
                      <TableHead className="text-center">Tier</TableHead>
                        </TableRow>
                        </TableHeader>
                        <TableBody>
                    {clutchAnalysis.map((team) => (
                      <TableRow key={team.teamId}>
                        <TableCell>
                          <div className="font-medium">{team.teamAbbr}</div>
                          <div className="text-xs text-muted-foreground">{team.teamName}</div>
                        </TableCell>
                        <TableCell className="text-center font-mono">{team.clutchRecord}</TableCell>
                        <TableCell className="text-center">
                          <span className={`font-mono ${team.clutchNetRating > 5 ? 'text-green-600' : team.clutchNetRating < 0 ? 'text-red-600' : 'text-yellow-600'}`}>
                            {team.clutchNetRating > 0 ? '+' : ''}{team.clutchNetRating.toFixed(1)}
                          </span>
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Progress value={team.starPerformance} className="w-12 h-2" />
                            <span className="font-mono text-sm">{team.starPerformance}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Progress value={team.coaching} className="w-12 h-2" />
                            <span className="font-mono text-sm">{team.coaching}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Progress value={team.mentalToughness} className="w-12 h-2" />
                            <span className="font-mono text-sm">{team.mentalToughness}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          {getClutchTierBadge(team.clutchTier)}
                        </TableCell>
                            </TableRow>
                        ))}
                        </TableBody>
                    </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="coaching_impact" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5" />
                Coaching Impact Metrics
              </CardTitle>
              <CardDescription>
                Comprehensive analysis of coaching effectiveness across multiple dimensions
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoadingCoaching ? (
                <Skeleton className="h-96 w-full" />
              ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                      <TableHead>Coach/Team</TableHead>
                      <TableHead className="text-center">Overall</TableHead>
                      <TableHead className="text-center">Adjustments</TableHead>
                      <TableHead className="text-center">Development</TableHead>
                      <TableHead className="text-center">System</TableHead>
                      <TableHead className="text-center">Culture</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                    {coachingImpact.map((coach) => (
                      <TableRow key={coach.teamId}>
                        <TableCell>
                          <div className="font-medium">{coach.coachName}</div>
                          <div className="text-xs text-muted-foreground">{coach.teamAbbr}</div>
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Progress value={coach.overallImpact} className="w-16 h-2" />
                            <span className={`font-mono text-sm ${coach.overallImpact > 90 ? 'text-green-600' : coach.overallImpact < 75 ? 'text-red-600' : 'text-yellow-600'}`}>
                              {coach.overallImpact}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Progress value={coach.adjustmentRating} className="w-12 h-2" />
                            <span className="font-mono text-sm">{coach.adjustmentRating}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Progress value={coach.playerImprovement} className="w-12 h-2" />
                            <span className="font-mono text-sm">{coach.playerImprovement}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Progress value={(coach.offensiveSystem + coach.defensiveSystem) / 2} className="w-12 h-2" />
                            <span className="font-mono text-sm">{Math.round((coach.offensiveSystem + coach.defensiveSystem) / 2)}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Progress value={coach.cultureBuilding} className="w-12 h-2" />
                            <span className="font-mono text-sm">{coach.cultureBuilding}</span>
                          </div>
                        </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="play_styles" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5" />
                Play Style Analysis
              </CardTitle>
              <CardDescription>
                Team identity, style classification, and matchup analysis
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoadingStyles ? (
                <Skeleton className="h-96 w-full" />
              ) : (
                <div className="space-y-6">
                  {playStyles.map((team) => (
                    <Card key={team.teamId} className="border-l-4 border-l-blue-400">
                      <CardContent className="pt-4">
                        <div className="flex items-center justify-between mb-4">
                          <div className="flex items-center gap-3">
                            <div>
                              <div className="font-medium text-lg">{team.teamAbbr}</div>
                              <div className="text-sm text-muted-foreground">{team.teamName}</div>
                            </div>
                            <Badge variant="outline">{team.overallIdentity}</Badge>
                          </div>
                          <div className="text-right">
                            <div className="text-lg font-semibold">{(team.winProbabilityVsPace * 100).toFixed(0)}%</div>
                            <div className="text-xs text-muted-foreground">Style Win Rate</div>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                          <div className="text-center">
                            <div className="text-sm font-medium">Pace</div>
                            <div className="text-lg font-semibold">{team.pace.toFixed(1)}</div>
                          </div>
                          <div className="text-center">
                            <div className="text-sm font-medium">3PT Rate</div>
                            <div className="text-lg font-semibold">{(team.threePointRate * 100).toFixed(1)}%</div>
                          </div>
                          <div className="text-center">
                            <div className="text-sm font-medium">AST Rate</div>
                            <div className="text-lg font-semibold">{(team.assistRate * 100).toFixed(1)}%</div>
                          </div>
                          <div className="text-center">
                            <div className="text-sm font-medium">STL Rate</div>
                            <div className="text-lg font-semibold">{(team.stealRate * 100).toFixed(1)}%</div>
                          </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div>
                            <div className="text-sm font-medium mb-2">Style Classification</div>
                            <div className="flex gap-2">
                              <Badge variant="secondary">{team.offensiveStyle}</Badge>
                              <Badge variant="outline">{team.defensiveStyle}</Badge>
                            </div>
                          </div>
                          <div>
                            <div className="text-sm font-medium mb-2">Matchup Profile</div>
                            <div className="text-xs">
                              <div className="flex items-center gap-1 mb-1">
                                <TrendingUp className="h-3 w-3 text-green-500" />
                                <span>Beats: {team.matchupAdvantages.join(', ')}</span>
                              </div>
                              <div className="flex items-center gap-1">
                                <TrendingDown className="h-3 w-3 text-red-500" />
                                <span>Struggles vs: {team.matchupDisadvantages.join(', ')}</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

