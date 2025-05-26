"use client";

import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { 
  Target, 
  Zap, 
  Brain,
  TrendingUp,
  Activity,
  Users,
  BarChart3,
  LineChart,
  PieChart,
  Bot,
  Cog,
  Settings,
  Play,
  Pause,
  RotateCcw,
  FastForward,
  Rewind,
  SkipForward,
  SkipBack,
  Eye,
  EyeOff,
    Clock,  Timer,  Calendar,  MapPin,  Navigation,  Compass,  Route,  Flag,  Trophy,  Star,  Award,  Medal,  Crown,  Flame,  Zap as Lightning,  Rocket,  Gauge,
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  TrendingDown,
  Plus,
  Minus,
  X,
  Check,
  Info,
  AlertTriangle,
  CheckCircle,
  XCircle,
  FileText,
  Database,
  Download,
  Upload,
  RefreshCw,
  Wifi,
  WifiOff,
  Search,
  Filter,
  SortAsc,
  SortDesc,
  MoreHorizontal,
  MoreVertical,
  Grid,
  List,
  Layers,
  GitBranch,
  Network,
  Workflow
} from 'lucide-react';

interface Player {
  id: string;
  name: string;
  position: 'PG' | 'SG' | 'SF' | 'PF' | 'C';
  jerseyNumber: number;
  age: number;
  height: string;
  weight: number;
  experience: number;
  
  minutesPlayed: number;
  points: number;
  rebounds: number;
  assists: number;
  steals: number;
  blocks: number;
  turnovers: number;
  fouls: number;
  fieldGoalPercentage: number;
  threePointPercentage: number;
  freeThrowPercentage: number;
  
  playerEfficiencyRating: number;
  trueShootingPercentage: number;
  usageRate: number;
  assistToTurnoverRatio: number;
  reboundRate: number;
  stealRate: number;
  blockRate: number;
  
  fatigueLevel: number;
  injuryRisk: number;
  condition: 'excellent' | 'good' | 'fair' | 'questionable' | 'injured';
  stamina: number;

  defensiveRating: number;
  offensiveRating: number;
  clutchRating: number;
  leadership: number;
  chemistry: { [playerId: string]: number };
  versatility: number;

  projectedPerformance: number;
  optimalMinutes: number;
  recommendedRole: 'starter' | 'sixth-man' | 'rotation' | 'situational' | 'bench';
  matchupAdvantage: number;
}

interface LineupConfiguration {
  id: string;
  name: string;
  players: Player[];
  type: 'starting' | 'closing' | 'defensive' | 'offensive' | 'small-ball' | 'big-ball' | 'bench';
  expectedEfficiency: number;
  offensiveRating: number;
  defensiveRating: number;
  paceRating: number;
  reboundingRating: number;
  ballMovementRating: number;
  spacing: number;
  chemistry: number;
  matchupRating: number;
  situationalUse: string[];
  strengths: string[];
  weaknesses: string[];
  recommendedMinutes: number;
  optimalGameSituations: string[];
}

interface GameStrategy {
  id: string;
  name: string;
  description: string;
  type: 'offensive' | 'defensive' | 'balanced' | 'pace' | 'specialty';
  effectiveness: number;
  gameContext: {
    quarter: 1 | 2 | 3 | 4 | 'OT';
    timeRemaining: number;
    scoreMargin: number;
    fouls: number;
    timeouts: number;
  };
  playerRequirements: {
    minPlayers: number;
    requiredPositions: string[];
    skillRequirements: string[];
  };
  expectedOutcome: {
    pointsPerPossession: number;
    defensiveStops: number;
    turnoverRate: number;
    reboundRate: number;
  };
  counters: string[];
  weaknesses: string[];
  successRate: number;
}

interface RotationPlan {
  quarter: 1 | 2 | 3 | 4;
  timeSegments: {
    startTime: number;
    endTime: number;
    lineup: string;
    strategy: string;
    priority: 'rest' | 'scoring' | 'defense' | 'momentum' | 'closing';
    playerMinutes: { [playerId: string]: number };
  }[];
  totalMinutes: { [playerId: string]: number };
  restPeriods: { [playerId: string]: number[] };
  keyMoments: {
    time: number;
    action: string;
    reasoning: string;
  }[];
}

interface OpponentAnalysis {
  teamName: string;
  strengths: string[];
  weaknesses: string[];
  preferredPace: number;
  averagePoints: number;
  defensiveRating: number;
  offensiveRating: number;
  keyPlayers: {
    name: string;
    position: string;
    threats: string[];
    counters: string[];
  }[];
  tendencies: {
    situation: string;
    behavior: string;
    frequency: number;
  }[];
  optimalStrategy: string;
  recommendedLineups: string[];
}

interface StrategyOptimizerProps {
  players?: Player[];
  lineups?: LineupConfiguration[];
  strategies?: GameStrategy[];
  opponent?: OpponentAnalysis;
  gameContext?: {
    quarter: number;
    timeRemaining: number;
    score: { home: number; away: number };
    fouls: { home: number; away: number };
    timeouts: { home: number; away: number };
  };
}

const mockPlayers: Player[] = [
  {
    id: 'lebron',
    name: 'LeBron James',
    position: 'SF',
    jerseyNumber: 23,
    age: 39,
    height: "6'9\"",
    weight: 250,
    experience: 21,
    minutesPlayed: 35.2,
    points: 25.8,
    rebounds: 8.1,
    assists: 7.2,
    steals: 1.1,
    blocks: 0.6,
    turnovers: 3.8,
    fouls: 1.8,
    fieldGoalPercentage: 51.2,
    threePointPercentage: 35.4,
    freeThrowPercentage: 74.8,
    playerEfficiencyRating: 24.8,
    trueShootingPercentage: 58.9,
    usageRate: 31.2,
    assistToTurnoverRatio: 1.89,
    reboundRate: 12.4,
    stealRate: 1.5,
    blockRate: 1.2,
    fatigueLevel: 25,
    injuryRisk: 15,
    condition: 'good',
    stamina: 85,
    defensiveRating: 112.8,
    offensiveRating: 118.4,
    clutchRating: 94,
    leadership: 98,
    chemistry: { 'ad': 95, 'austin': 88, 'dlo': 82 },
    versatility: 92,
    projectedPerformance: 89,
    optimalMinutes: 36,
    recommendedRole: 'starter',
    matchupAdvantage: 15
  },
  {
    id: 'ad',
    name: 'Anthony Davis',
    position: 'PF',
    jerseyNumber: 3,
    age: 30,
    height: "6'11\"",
    weight: 253,
    experience: 12,
    minutesPlayed: 34.8,
    points: 24.3,
    rebounds: 12.2,
    assists: 2.4,
    steals: 1.3,
    blocks: 2.1,
    turnovers: 2.1,
    fouls: 2.8,
    fieldGoalPercentage: 52.8,
    threePointPercentage: 33.2,
    freeThrowPercentage: 81.6,
    playerEfficiencyRating: 28.4,
    trueShootingPercentage: 59.7,
    usageRate: 28.9,
    assistToTurnoverRatio: 1.14,
    reboundRate: 18.2,
    stealRate: 1.8,
    blockRate: 4.2,
    fatigueLevel: 30,
    injuryRisk: 35,
    condition: 'good',
    stamina: 82,
    defensiveRating: 108.2,
    offensiveRating: 119.8,
    clutchRating: 87,
    leadership: 78,
    chemistry: { 'lebron': 95, 'austin': 76, 'dlo': 71 },
    versatility: 85,
    projectedPerformance: 91,
    optimalMinutes: 35,
    recommendedRole: 'starter',
    matchupAdvantage: 25
  },
  {
    id: 'austin',
    name: 'Austin Reaves',
    position: 'SG',
    jerseyNumber: 15,
    age: 25,
    height: "6'5\"",
    weight: 197,
    experience: 3,
    minutesPlayed: 32.1,
    points: 17.2,
    rebounds: 4.4,
    assists: 5.8,
    steals: 0.9,
    blocks: 0.2,
    turnovers: 2.3,
    fouls: 2.1,
    fieldGoalPercentage: 46.8,
    threePointPercentage: 38.2,
    freeThrowPercentage: 88.4,
    playerEfficiencyRating: 18.9,
    trueShootingPercentage: 58.1,
    usageRate: 22.4,
    assistToTurnoverRatio: 2.52,
    reboundRate: 7.8,
    stealRate: 1.4,
    blockRate: 0.3,
    fatigueLevel: 15,
    injuryRisk: 8,
    condition: 'excellent',
    stamina: 94,
    defensiveRating: 115.2,
    offensiveRating: 116.8,
    clutchRating: 92,
    leadership: 72,
    chemistry: { 'lebron': 88, 'ad': 76, 'dlo': 85 },
    versatility: 78,
    projectedPerformance: 85,
    optimalMinutes: 33,
    recommendedRole: 'starter',
    matchupAdvantage: 8
  }
];

const mockLineups: LineupConfiguration[] = [
  {
    id: 'starting-five',
    name: 'Starting Five',
    players: mockPlayers.slice(0, 5),
    type: 'starting',
    expectedEfficiency: 118.4,
    offensiveRating: 118.4,
    defensiveRating: 112.8,
    paceRating: 98.2,
    reboundingRating: 52.1,
    ballMovementRating: 24.8,
    spacing: 87,
    chemistry: 89,
    matchupRating: 16,
    situationalUse: ['Game Start', 'Momentum Shifts', 'Crucial Possessions'],
    strengths: ['Versatility', 'Experience', 'Clutch Performance'],
    weaknesses: ['Age', 'Injury Risk', 'Pace'],
    recommendedMinutes: 28,
    optimalGameSituations: ['Opening Quarter', 'Close Games', 'Playoff Situations']
  },
  {
    id: 'small-ball',
    name: 'Small Ball Death Lineup',
    players: mockPlayers.slice(0, 5),
    type: 'small-ball',
    expectedEfficiency: 122.8,
    offensiveRating: 122.8,
    defensiveRating: 115.4,
    paceRating: 105.2,
    reboundingRating: 48.3,
    ballMovementRating: 28.4,
    spacing: 94,
    chemistry: 91,
    matchupRating: 22,
    situationalUse: ['Opponent Big Lineup', 'Need Pace', 'Spacing Issues'],
    strengths: ['Spacing', 'Speed', 'Versatility', 'Ball Movement'],
    weaknesses: ['Rebounding', 'Interior Defense'],
    recommendedMinutes: 8,
    optimalGameSituations: ['4th Quarter', 'Closing Moments', 'vs Traditional Centers']
  }
];

const mockStrategies: GameStrategy[] = [
  {
    id: 'lebron-post',
    name: 'LeBron Post-Up System',
    description: 'Utilize LeBron\'s size and court vision in the post with cutters and shooters',
    type: 'offensive',
    effectiveness: 91,
    gameContext: {
      quarter: 4,
      timeRemaining: 300,
      scoreMargin: -5,
      fouls: 6,
      timeouts: 2
    },
    playerRequirements: {
      minPlayers: 5,
      requiredPositions: ['SF', 'PF'],
      skillRequirements: ['Post-Up', 'Court Vision', '3-Point Shooting']
    },
    expectedOutcome: {
      pointsPerPossession: 1.18,
      defensiveStops: 0,
      turnoverRate: 12.4,
      reboundRate: 48.2
    },
    counters: ['Zone Defense', 'Double Teams'],
    weaknesses: ['Athletic Defenders', 'Quick Hands'],
    successRate: 68.4
  },
  {
    id: 'pick-and-roll',
    name: 'High Pick & Roll',
    description: 'Classic pick and roll with LeBron/AD creating mismatches',
    type: 'offensive',
    effectiveness: 89,
    gameContext: {
      quarter: 1,
      timeRemaining: 720,
      scoreMargin: 0,
      fouls: 2,
      timeouts: 4
    },
    playerRequirements: {
      minPlayers: 5,
      requiredPositions: ['PG', 'C'],
      skillRequirements: ['Ball Handling', 'Screen Setting', 'Roll Finishing']
    },
    expectedOutcome: {
      pointsPerPossession: 1.15,
      defensiveStops: 0,
      turnoverRate: 14.2,
      reboundRate: 51.8
    },
    counters: ['Switch Defense', 'Help Defense'],
    weaknesses: ['Hedge Defense', 'Trap Coverage'],
    successRate: 72.1
  }
];

const mockOpponent: OpponentAnalysis = {
  teamName: 'Boston Celtics',
  strengths: ['3-Point Shooting', 'Ball Movement', 'Defensive Switching', 'Depth'],
  weaknesses: ['Interior Defense', 'Rebounding', 'Turnovers in Pressure'],
  preferredPace: 98.4,
  averagePoints: 118.2,
  defensiveRating: 110.8,
  offensiveRating: 118.2,
  keyPlayers: [
    {
      name: 'Jayson Tatum',
      position: 'SF',
      threats: ['ISO Scoring', '3-Point Shooting', 'Clutch Shots'],
      counters: ['Physical Defense', 'Help Defense', 'Force Left Hand']
    },
    {
      name: 'Jaylen Brown',
      position: 'SG',
      threats: ['Athleticism', 'Transition', 'Mid-Range'],
      counters: ['Contest Shots', 'Limit Transition', 'Body Contact']
    }
  ],
  tendencies: [
    {
      situation: '4th Quarter',
      behavior: 'ISO-Heavy Offense',
      frequency: 78
    },
    {
      situation: 'Double Teams',
      behavior: 'Quick Ball Movement',
      frequency: 84
    }
  ],
  optimalStrategy: 'switch-heavy',
  recommendedLineups: ['small-ball', 'defensive-stopper']
};

export default function TeamStrategyOptimizer({
  players = mockPlayers,
  lineups = mockLineups,
  strategies = mockStrategies,
  opponent = mockOpponent,
  gameContext = {
    quarter: 1,
    timeRemaining: 12 * 60,
    score: { home: 0, away: 0 },
    fouls: { home: 0, away: 0 },
    timeouts: { home: 7, away: 7 }
  }
}: StrategyOptimizerProps) {
  const [selectedTab, setSelectedTab] = useState<'lineups' | 'strategies' | 'rotations' | 'opponent' | 'live'>('lineups');
  const [selectedLineup, setSelectedLineup] = useState<string | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(null);
  const [optimizationMode, setOptimizationMode] = useState<'defensive' | 'offensive' | 'balanced' | 'situational'>('balanced');
  const [autoOptimize, setAutoOptimize] = useState(true);
  const [showAdvancedMetrics, setShowAdvancedMetrics] = useState(true);
  const [timeHorizon, setTimeHorizon] = useState([240]);
  const [riskTolerance, setRiskTolerance] = useState([50]);
  const [priorityWeight, setPriorityWeight] = useState<{ [key: string]: number }>({
    offense: 50,
    defense: 50,
    chemistry: 30,
    health: 70,
    experience: 40
  });

  const calculateLineupEfficiency = (lineup: LineupConfiguration) => {
    const offenseWeight = priorityWeight.offense / 100;
    const defenseWeight = priorityWeight.defense / 100;
    const chemistryWeight = priorityWeight.chemistry / 100;
    
    return (
      lineup.offensiveRating * offenseWeight +
      (120 - lineup.defensiveRating) * defenseWeight +
      lineup.chemistry * chemistryWeight
    ) / (offenseWeight + defenseWeight + chemistryWeight);
  };

  const getOptimalLineup = (situation: string) => {
    return lineups.reduce((best, current) => {
      if (current.optimalGameSituations.includes(situation)) {
        return calculateLineupEfficiency(current) > calculateLineupEfficiency(best) ? current : best;
      }
      return best;
    }, lineups[0]);
  };

  const getFatigueImpact = (player: Player) => {
    const impact = (player.fatigueLevel / 100) * 20;
    return Math.max(0, player.projectedPerformance - impact);
  };

  const getPositionColor = (position: string) => {
    switch (position) {
      case 'PG': return '#3b82f6';
      case 'SG': return '#10b981';
      case 'SF': return '#f59e0b';
      case 'PF': return '#ef4444';
      case 'C': return '#8b5cf6';
      default: return '#6b7280';
    }
  };

  const getConditionColor = (condition: string) => {
    switch (condition) {
      case 'excellent': return '#10b981';
      case 'good': return '#3b82f6';
      case 'fair': return '#f59e0b';
      case 'questionable': return '#ef4444';
      case 'injured': return '#7f1d1d';
      default: return '#6b7280';
    }
  };

  const optimalLineupForSituation = getOptimalLineup('Opening Quarter');
  const recommendedStrategy = strategies[0];

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card className="border-2 border-purple-500">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-xl font-bold flex items-center gap-3">
                <Target className="w-6 h-6 text-purple-500" />
                Comprehensive Team Strategy Optimizer
                <Badge variant="outline" className="flex items-center gap-1">
                  <Brain className="w-3 h-3" />
                  AI-Powered
                </Badge>
              </h3>
              <div className="flex items-center gap-6 mt-2 text-sm text-muted-foreground">
                <span className="text-lg font-bold text-foreground">
                  Q{gameContext.quarter} • {Math.floor(gameContext.timeRemaining / 60)}:{(gameContext.timeRemaining % 60).toString().padStart(2, '0')}
                </span>
                <span>Mode: {optimizationMode.toUpperCase()}</span>
                <span>Auto-Optimize: {autoOptimize ? 'ON' : 'OFF'}</span>
                <span>vs {opponent.teamName}</span>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <Badge variant="outline" className="flex items-center gap-1">
                <Trophy className="w-3 h-3" />
                {optimalLineupForSituation.expectedEfficiency.toFixed(1)} Eff Rating
              </Badge>
              
              <Button
                size="sm"
                variant={autoOptimize ? 'default' : 'outline'}
                onClick={() => setAutoOptimize(!autoOptimize)}
              >
                {autoOptimize ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
                {autoOptimize ? 'Auto' : 'Manual'}
              </Button>
              
              <Button size="sm" variant="outline">
                <Settings className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Quick Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">{players.length}</div>
            <div className="text-sm text-muted-foreground">Available Players</div>
            <div className="text-xs text-green-600 mt-1">
              {players.filter(p => p.condition === 'excellent' || p.condition === 'good').length} ready
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-purple-600">{lineups.length}</div>
            <div className="text-sm text-muted-foreground">Optimized Lineups</div>
            <div className="text-xs text-blue-600 mt-1">
              {Math.max(...lineups.map(l => l.expectedEfficiency)).toFixed(1)} max efficiency
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-orange-600">{strategies.length}</div>
            <div className="text-sm text-muted-foreground">Game Strategies</div>
            <div className="text-xs text-green-600 mt-1">
              {Math.max(...strategies.map(s => s.effectiveness)).toFixed(1)}% max effectiveness
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-red-600">
              {Math.round(players.reduce((sum, p) => sum + p.fatigueLevel, 0) / players.length)}%
            </div>
            <div className="text-sm text-muted-foreground">Avg Fatigue</div>
            <div className="text-xs text-yellow-600 mt-1">
              {players.filter(p => p.fatigueLevel > 70).length} high fatigue
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-green-600">
              {recommendedStrategy.effectiveness.toFixed(1)}%
            </div>
            <div className="text-sm text-muted-foreground">Strategy Effectiveness</div>
            <div className="text-xs text-blue-600 mt-1">{recommendedStrategy.successRate.toFixed(1)}% success rate</div>
          </CardContent>
        </Card>
      </div>

      {/* Main Interface */}
      <Tabs value={selectedTab} onValueChange={(value: any) => setSelectedTab(value)}>
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="lineups">Lineup Optimizer</TabsTrigger>
          <TabsTrigger value="strategies">Game Strategies</TabsTrigger>
          <TabsTrigger value="rotations">Rotation Planner</TabsTrigger>
          <TabsTrigger value="opponent">Opponent Analysis</TabsTrigger>
          <TabsTrigger value="live">Live Adjustments</TabsTrigger>
        </TabsList>

        <TabsContent value="lineups" className="space-y-6">
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            {/* Player Pool */}
            <Card className="xl:col-span-1">
              <CardHeader>
                <h4 className="font-semibold flex items-center gap-2">
                  <Users className="w-4 h-4" />
                  Player Pool ({players.length})
                </h4>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {players.map(player => (
                    <div key={player.id} className="p-3 border rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Badge 
                            style={{ backgroundColor: getPositionColor(player.position) }}
                            className="text-white text-xs"
                          >
                            {player.position}
                          </Badge>
                          <span className="font-medium text-sm">{player.name}</span>
                        </div>
                        <Badge 
                          style={{ backgroundColor: getConditionColor(player.condition) }}
                          className="text-white text-xs"
                        >
                          {player.condition}
                        </Badge>
                      </div>
                      
                      <div className="grid grid-cols-3 gap-2 mb-2 text-xs">
                        <div>
                          <div className="text-muted-foreground">Performance</div>
                          <Progress value={getFatigueImpact(player)} className="h-1 mt-1" />
                          <div className="font-medium">{getFatigueImpact(player).toFixed(0)}%</div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">Stamina</div>
                          <Progress value={player.stamina} className="h-1 mt-1" />
                          <div className="font-medium">{player.stamina}%</div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">Chemistry</div>
                          <Progress value={Object.values(player.chemistry).reduce((a, b) => a + b, 0) / Object.values(player.chemistry).length} className="h-1 mt-1" />
                          <div className="font-medium">
                            {(Object.values(player.chemistry).reduce((a, b) => a + b, 0) / Object.values(player.chemistry).length).toFixed(0)}%
                          </div>
                        </div>
                      </div>
                      
                      <div className="text-xs text-muted-foreground">
                        Optimal: {player.optimalMinutes}min • Role: {player.recommendedRole}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Optimized Lineups */}
            <Card className="xl:col-span-2">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold flex items-center gap-2">
                    <Cog className="w-4 h-4" />
                    Optimized Lineups ({lineups.length})
                  </h4>
                  <div className="flex gap-2">
                    <Select value={optimizationMode} onValueChange={(value: any) => setOptimizationMode(value)}>
                      <SelectTrigger className="w-32">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="offensive">Offensive</SelectItem>
                        <SelectItem value="defensive">Defensive</SelectItem>
                        <SelectItem value="balanced">Balanced</SelectItem>
                        <SelectItem value="situational">Situational</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button size="sm" variant="outline">
                      <RefreshCw className="w-4 h-4" />
                      Re-optimize
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {lineups.map(lineup => (
                    <div 
                      key={lineup.id} 
                      className={`p-4 border rounded-lg cursor-pointer transition-all ${
                        selectedLineup === lineup.id ? 'border-purple-500 bg-purple-50' : 'hover:bg-gray-50'
                      }`}
                      onClick={() => setSelectedLineup(selectedLineup === lineup.id ? null : lineup.id)}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <div className="font-medium">{lineup.name}</div>
                          <div className="text-sm text-muted-foreground capitalize">{lineup.type} lineup</div>
                        </div>
                        <div className="text-right">
                          <Badge variant="outline" className="mb-1">
                            {lineup.expectedEfficiency.toFixed(1)} efficiency
                          </Badge>
                          <div className="text-sm text-muted-foreground">
                            +{lineup.matchupRating} vs opponent
                          </div>
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-5 gap-2 mb-3">
                        {lineup.players.slice(0, 5).map(player => (
                          <div key={player.id} className="text-center">
                            <Badge 
                              style={{ backgroundColor: getPositionColor(player.position) }}
                              className="text-white text-xs mb-1"
                            >
                              {player.position}
                            </Badge>
                            <div className="text-xs font-medium">{player.name.split(' ').pop()}</div>
                            <div className="text-xs text-muted-foreground">
                              {getFatigueImpact(player).toFixed(0)}%
                            </div>
                          </div>
                        ))}
                      </div>
                      
                      <div className="grid grid-cols-4 gap-3 mb-3">
                        <div className="text-center">
                          <div className="text-xs text-muted-foreground">Offense</div>
                          <div className="font-medium text-sm">{lineup.offensiveRating.toFixed(1)}</div>
                        </div>
                        <div className="text-center">
                          <div className="text-xs text-muted-foreground">Defense</div>
                          <div className="font-medium text-sm">{lineup.defensiveRating.toFixed(1)}</div>
                        </div>
                        <div className="text-center">
                          <div className="text-xs text-muted-foreground">Chemistry</div>
                          <div className="font-medium text-sm">{lineup.chemistry}%</div>
                        </div>
                        <div className="text-center">
                          <div className="text-xs text-muted-foreground">Spacing</div>
                          <div className="font-medium text-sm">{lineup.spacing}%</div>
                        </div>
                      </div>
                      
                      {selectedLineup === lineup.id && (
                        <div className="mt-4 pt-4 border-t space-y-3">
                          <div>
                            <div className="text-sm font-medium mb-2">Strengths:</div>
                            <div className="flex flex-wrap gap-1">
                              {lineup.strengths.map(strength => (
                                <Badge key={strength} variant="secondary" className="text-xs">
                                  {strength}
                                </Badge>
                              ))}
                            </div>
                          </div>
                          
                          <div>
                            <div className="text-sm font-medium mb-2">Optimal Situations:</div>
                            <div className="flex flex-wrap gap-1">
                              {lineup.optimalGameSituations.map(situation => (
                                <Badge key={situation} variant="outline" className="text-xs">
                                  {situation}
                                </Badge>
                              ))}
                            </div>
                          </div>
                          
                          <div className="grid grid-cols-3 gap-4 text-xs">
                            <div>
                              <span className="text-muted-foreground">Recommended Minutes:</span>
                              <span className="font-medium ml-1">{lineup.recommendedMinutes}</span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">Pace Rating:</span>
                              <span className="font-medium ml-1">{lineup.paceRating.toFixed(1)}</span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">Rebounding:</span>
                              <span className="font-medium ml-1">{lineup.reboundingRating.toFixed(1)}%</span>
                            </div>
                          </div>
                          
                          <div className="flex gap-2 mt-3">
                            <Button size="sm" variant="outline" className="text-xs">
                              <Play className="w-3 h-3 mr-1" />
                              Deploy Now
                            </Button>
                            <Button size="sm" variant="outline" className="text-xs">
                              <Settings className="w-3 h-3 mr-1" />
                              Customize
                            </Button>
                            <Button size="sm" variant="outline" className="text-xs">
                              <BarChart3 className="w-3 h-3 mr-1" />
                              Analytics
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="strategies" className="space-y-6">
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* Available Strategies */}
            <Card>
              <CardHeader>
                <h4 className="font-semibold flex items-center gap-2">
                  <Brain className="w-4 h-4" />
                  Game Strategies ({strategies.length})
                </h4>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {strategies.map(strategy => (
                    <div 
                      key={strategy.id} 
                      className={`p-4 border rounded-lg cursor-pointer transition-all ${
                        selectedStrategy === strategy.id ? 'border-purple-500 bg-purple-50' : 'hover:bg-gray-50'
                      }`}
                      onClick={() => setSelectedStrategy(selectedStrategy === strategy.id ? null : strategy.id)}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <div className="font-medium">{strategy.name}</div>
                          <div className="text-sm text-muted-foreground capitalize">{strategy.type} strategy</div>
                        </div>
                        <div className="text-right">
                          <Badge variant="outline" className="mb-1">
                            {strategy.effectiveness}% effective
                          </Badge>
                          <div className="text-sm text-muted-foreground">
                            {strategy.successRate.toFixed(1)}% success
                          </div>
                        </div>
                      </div>
                      
                      <div className="text-sm text-muted-foreground mb-3">
                        {strategy.description}
                      </div>
                      
                      <div className="grid grid-cols-2 gap-4 text-xs mb-3">
                        <div>
                          <div className="text-muted-foreground">Expected PPP:</div>
                          <div className="font-medium">{strategy.expectedOutcome.pointsPerPossession.toFixed(2)}</div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">Turnover Rate:</div>
                          <div className="font-medium">{strategy.expectedOutcome.turnoverRate.toFixed(1)}%</div>
                        </div>
                      </div>
                      
                      {selectedStrategy === strategy.id && (
                        <div className="mt-4 pt-4 border-t space-y-3">
                          <div>
                            <div className="text-sm font-medium mb-2">Counters:</div>
                            <div className="flex flex-wrap gap-1">
                              {strategy.counters.map(counter => (
                                <Badge key={counter} variant="secondary" className="text-xs">
                                  {counter}
                                </Badge>
                              ))}
                            </div>
                          </div>
                          
                          <div>
                            <div className="text-sm font-medium mb-2">Weaknesses:</div>
                            <div className="flex flex-wrap gap-1">
                              {strategy.weaknesses.map(weakness => (
                                <Badge key={weakness} variant="destructive" className="text-xs">
                                  {weakness}
                                </Badge>
                              ))}
                            </div>
                          </div>
                          
                          <div>
                            <div className="text-sm font-medium mb-2">Required Skills:</div>
                            <div className="flex flex-wrap gap-1">
                              {strategy.playerRequirements.skillRequirements.map(skill => (
                                <Badge key={skill} variant="outline" className="text-xs">
                                  {skill}
                                </Badge>
                              ))}
                            </div>
                          </div>
                          
                          <div className="flex gap-2 mt-3">
                            <Button size="sm" variant="outline" className="text-xs">
                              <Play className="w-3 h-3 mr-1" />
                              Activate
                            </Button>
                            <Button size="sm" variant="outline" className="text-xs">
                              <Settings className="w-3 h-3 mr-1" />
                              Modify
                            </Button>
                            <Button size="sm" variant="outline" className="text-xs">
                              <BarChart3 className="w-3 h-3 mr-1" />
                              Analysis
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Strategy Effectiveness Chart */}
            <Card>
              <CardHeader>
                <h4 className="font-semibold flex items-center gap-2">
                  <LineChart className="w-4 h-4" />
                  Strategy Effectiveness Analysis
                </h4>
              </CardHeader>
              <CardContent>
                <div className="relative h-64 bg-gradient-to-br from-purple-50 to-blue-50 rounded-lg p-4">
                  <svg width="100%" height="100%" viewBox="0 0 400 200">
                    <defs>
                      <linearGradient id="strategyGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style={{stopColor: '#8b5cf6', stopOpacity: 0.8}} />
                        <stop offset="100%" style={{stopColor: '#3b82f6', stopOpacity: 0.8}} />
                      </linearGradient>
                    </defs>

                    {/* Grid lines */}
                    {[0, 1, 2, 3, 4].map(i => (
                      <line
                        key={i}
                        x1={50 + i * 75}
                        y1="20"
                        x2={50 + i * 75}
                        y2="180"
                        stroke="#e5e7eb"
                        strokeWidth="1"
                      />
                    ))}
                    
                    {[20, 40, 60, 80, 100].map((value, index) => (
                      <line
                        key={value}
                        x1="50"
                        y1={20 + index * 32}
                        x2="350"
                        y2={20 + index * 32}
                        stroke="#e5e7eb"
                        strokeWidth="1"
                      />
                    ))}

                    {/* Strategy effectiveness bars */}
                    {strategies.map((strategy, index) => {
                      const height = (strategy.effectiveness / 100) * 140;
                      const x = 70 + index * 80;
                      const y = 160 - height;
                      
                      return (
                        <g key={strategy.id}>
                          <rect
                            x={x}
                            y={y}
                            width="40"
                            height={height}
                            fill="url(#strategyGradient)"
                            rx="4"
                            className="cursor-pointer"
                          />
                          <text
                            x={x + 20}
                            y={y - 5}
                            textAnchor="middle"
                            className="text-xs font-medium fill-gray-700"
                          >
                            {strategy.effectiveness}%
                          </text>
                          <text
                            x={x + 20}
                            y="190"
                            textAnchor="middle"
                            className="text-xs fill-gray-600"
                          >
                            {strategy.name.split(' ')[0]}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                  
                  <div className="absolute top-4 right-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 text-xs">
                    <div className="font-medium mb-2">Strategy Performance</div>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                        <span>Effectiveness Rating</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                        <span>vs Current Opponent</span>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="opponent" className="space-y-6">
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* Opponent Analysis */}
            <Card>
              <CardHeader>
                <h4 className="font-semibold flex items-center gap-2">
                  <Eye className="w-4 h-4" />
                  {opponent.teamName} Analysis
                </h4>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <div className="text-muted-foreground">Offensive Rating</div>
                      <div className="font-bold text-lg">{opponent.offensiveRating.toFixed(1)}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Defensive Rating</div>
                      <div className="font-bold text-lg">{opponent.defensiveRating.toFixed(1)}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Preferred Pace</div>
                      <div className="font-bold text-lg">{opponent.preferredPace.toFixed(1)}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Avg Points</div>
                      <div className="font-bold text-lg">{opponent.averagePoints.toFixed(1)}</div>
                    </div>
                  </div>
                  
                  <div>
                    <div className="text-sm font-medium mb-2">Strengths:</div>
                    <div className="flex flex-wrap gap-1">
                      {opponent.strengths.map(strength => (
                        <Badge key={strength} variant="destructive" className="text-xs">
                          {strength}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  
                  <div>
                    <div className="text-sm font-medium mb-2">Weaknesses:</div>
                    <div className="flex flex-wrap gap-1">
                      {opponent.weaknesses.map(weakness => (
                        <Badge key={weakness} variant="secondary" className="text-xs">
                          {weakness}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  
                  <div>
                    <div className="text-sm font-medium mb-2">Key Players:</div>
                    <div className="space-y-2">
                      {opponent.keyPlayers.map((player, index) => (
                        <div key={index} className="p-2 border rounded">
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-medium text-sm">{player.name}</span>
                            <Badge variant="outline" className="text-xs">{player.position}</Badge>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            Threats: {player.threats.join(', ')}
                          </div>
                          <div className="text-xs text-green-600">
                            Counters: {player.counters.join(', ')}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Recommended Counterstrategy */}
            <Card>
              <CardHeader>
                <h4 className="font-semibold flex items-center gap-2">
                  <Target className="w-4 h-4" />
                  Recommended Counterstrategy
                </h4>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                    <div className="font-medium text-green-800 mb-2">
                      Optimal Strategy: {opponent.optimalStrategy.replace('-', ' ').toUpperCase()}
                    </div>
                    <div className="text-sm text-green-700">
                      Based on opponent tendencies and our team strengths, this approach maximizes our advantages while exploiting their weaknesses.
                    </div>
                  </div>
                  
                  <div>
                    <div className="text-sm font-medium mb-2">Recommended Lineups:</div>
                    <div className="flex flex-wrap gap-1">
                      {opponent.recommendedLineups.map(lineup => (
                        <Badge key={lineup} variant="outline" className="text-xs">
                          {lineup.replace('-', ' ')}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  
                  <div>
                    <div className="text-sm font-medium mb-3">Opponent Tendencies:</div>
                    <div className="space-y-2">
                      {opponent.tendencies.map((tendency, index) => (
                        <div key={index} className="flex items-center justify-between p-2 border rounded">
                          <div className="text-sm">
                            <div className="font-medium">{tendency.situation}</div>
                            <div className="text-muted-foreground text-xs">{tendency.behavior}</div>
                          </div>
                          <Badge variant="secondary" className="text-xs">
                            {tendency.frequency}%
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  <div className="pt-4 border-t">
                    <Button className="w-full">
                      <Play className="w-4 h-4 mr-2" />
                      Implement Counterstrategy
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      {/* Control Panel */}
      <Card>
        <CardHeader>
          <h4 className="font-semibold flex items-center gap-2">
            <Settings className="w-4 h-4" />
            Strategy Optimization Controls
          </h4>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="space-y-4">
              <div>
                <Label className="text-sm">Time Horizon: {Math.floor(timeHorizon[0] / 60)}:{(timeHorizon[0] % 60).toString().padStart(2, '0')}</Label>
                <Slider
                  value={timeHorizon}
                  onValueChange={setTimeHorizon}
                  min={60}
                  max={720}
                  step={30}
                  className="mt-2"
                />
              </div>
              <div>
                <Label className="text-sm">Risk Tolerance: {riskTolerance[0]}%</Label>
                <Slider
                  value={riskTolerance}
                  onValueChange={setRiskTolerance}
                  min={0}
                  max={100}
                  step={5}
                  className="mt-2"
                />
              </div>
            </div>
            
            <div className="space-y-4">
              <div>
                <Label className="text-sm font-medium">Priority Weights</Label>
                <div className="space-y-2 mt-2">
                  <div>
                    <Label className="text-xs">Offense: {priorityWeight.offense}%</Label>
                    <Slider
                      value={[priorityWeight.offense]}
                      onValueChange={([value]) => setPriorityWeight({...priorityWeight, offense: value})}
                      min={0}
                      max={100}
                      step={5}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Defense: {priorityWeight.defense}%</Label>
                    <Slider
                      value={[priorityWeight.defense]}
                      onValueChange={([value]) => setPriorityWeight({...priorityWeight, defense: value})}
                      min={0}
                      max={100}
                      step={5}
                      className="mt-1"
                    />
                  </div>
                </div>
              </div>
            </div>
            
            <div className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Auto Optimization</Label>
                  <Switch checked={autoOptimize} onCheckedChange={setAutoOptimize} />
                </div>
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Advanced Metrics</Label>
                  <Switch checked={showAdvancedMetrics} onCheckedChange={setShowAdvancedMetrics} />
                </div>
              </div>
              
              <div>
                <Label className="text-sm font-medium">Quick Actions</Label>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  <Button size="sm" variant="outline">
                    <RefreshCw className="w-3 h-3 mr-1" />
                    Re-optimize
                  </Button>
                  <Button size="sm" variant="outline">
                    <Download className="w-3 h-3 mr-1" />
                    Export
                  </Button>
                </div>
              </div>
            </div>
            
            <div className="space-y-4">
              <div>
                <Label className="text-sm font-medium">Game Simulation</Label>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  <Button size="sm" variant="outline">
                    <Play className="w-3 h-3 mr-1" />
                    Simulate
                  </Button>
                  <Button size="sm" variant="outline">
                    <Eye className="w-3 h-3 mr-1" />
                    Preview
                  </Button>
                  <Button size="sm" variant="outline">
                    <Brain className="w-3 h-3 mr-1" />
                    AI Analysis
                  </Button>
                  <Button size="sm" variant="outline">
                    <Trophy className="w-3 h-3 mr-1" />
                    Win Prob
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
} 