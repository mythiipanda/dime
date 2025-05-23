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
import { 
  Activity, 
  Brain, 
  Target, 
  TrendingUp,
  TrendingDown,
  Zap,
  Eye,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  Users,
  BarChart3,
  LineChart,
  PieChart,
  Gauge,
  Wifi,
  WifiOff,
  Play,
  Pause,
  RotateCcw,
  Settings,
  Maximize2,
  Volume2,
  VolumeX
} from 'lucide-react';

interface LiveGameData {
  gameId: string;
  homeTeam: string;
  awayTeam: string;
  quarter: number;
  timeRemaining: string;
  homeScore: number;
  awayScore: number;
  possession: 'home' | 'away';
  shotClock: number;
  gameStatus: 'live' | 'halftime' | 'final' | 'upcoming';
  broadcast: string;
}

interface PlayerPerformance {
  playerId: string;
  name: string;
  team: 'home' | 'away';
  position: string;
  jersey: number;
  // Current game stats
  points: number;
  rebounds: number;
  assists: number;
  steals: number;
  blocks: number;
  turnovers: number;
  fouls: number;
  // Live metrics
  plusMinus: number;
  efficiency: number;
  usage: number;
  fatigue: number; // 0-100
  hotStreak: boolean;
  coldStreak: boolean;
  // Predictions
  projectedPoints: number;
  injuryRisk: number; // 0-100
  clutchRating: number; // 0-10
  // Real-time status
  onCourt: boolean;
  minutesPlayed: number;
  restTime: number;
}

interface TeamMetrics {
  team: 'home' | 'away';
  teamName: string;
  // Live performance
  fieldGoalPercentage: number;
  threePointPercentage: number;
  freeThrowPercentage: number;
  totalRebounds: number;
  assists: number;
  turnovers: number;
  // Advanced metrics
  pace: number;
  offensiveRating: number;
  defensiveRating: number;
  netRating: number;
  // Momentum indicators
  momentum: number; // -100 to 100
  energyLevel: number; // 0-100
  chemistry: number; // 0-100
  coaching: number; // 0-100
  // Predictions
  winProbability: number; // 0-100
  projectedFinalScore: number;
}

interface AIInsight {
  id: string;
  type: 'substitution' | 'strategy' | 'matchup' | 'timeout' | 'injury' | 'opportunity';
  priority: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description: string;
  confidence: number; // 0-100
  timeGenerated: Date;
  actionable: boolean;
  impact: string;
  recommendation: string;
}

interface GameIntelligenceProps {
  gameData: LiveGameData;
  homePerformances: PlayerPerformance[];
  awayPerformances: PlayerPerformance[];
  homeMetrics: TeamMetrics;
  awayMetrics: TeamMetrics;
  aiInsights: AIInsight[];
  isLive?: boolean;
}

// Mock live game data
const mockGameData: LiveGameData = {
  gameId: 'LAL-BOS-20241025',
  homeTeam: 'Lakers',
  awayTeam: 'Celtics',
  quarter: 3,
  timeRemaining: '7:23',
  homeScore: 89,
  awayScore: 92,
  possession: 'home',
  shotClock: 18,
  gameStatus: 'live',
  broadcast: 'ESPN'
};

const mockHomePlayers: PlayerPerformance[] = [
  {
    playerId: 'lebron', name: 'LeBron James', team: 'home', position: 'SF', jersey: 23,
    points: 24, rebounds: 8, assists: 7, steals: 2, blocks: 1, turnovers: 3, fouls: 2,
    plusMinus: -1, efficiency: 28.5, usage: 31.2, fatigue: 65, hotStreak: false, coldStreak: false,
    projectedPoints: 32, injuryRisk: 15, clutchRating: 9, onCourt: true, minutesPlayed: 28, restTime: 0
  },
  {
    playerId: 'ad', name: 'Anthony Davis', team: 'home', position: 'PF/C', jersey: 3,
    points: 18, rebounds: 12, assists: 2, steals: 1, blocks: 3, turnovers: 2, fouls: 3,
    plusMinus: 2, efficiency: 24.8, usage: 28.5, fatigue: 72, hotStreak: false, coldStreak: false,
    projectedPoints: 25, injuryRisk: 25, clutchRating: 8, onCourt: true, minutesPlayed: 26, restTime: 0
  },
  {
    playerId: 'reaves', name: 'Austin Reaves', team: 'home', position: 'SG', jersey: 15,
    points: 14, rebounds: 3, assists: 5, steals: 1, blocks: 0, turnovers: 1, fouls: 1,
    plusMinus: -3, efficiency: 18.2, usage: 24.1, fatigue: 45, hotStreak: true, coldStreak: false,
    projectedPoints: 19, injuryRisk: 8, clutchRating: 7, onCourt: true, minutesPlayed: 25, restTime: 0
  },
  {
    playerId: 'russell', name: 'D\'Angelo Russell', team: 'home', position: 'PG', jersey: 1,
    points: 11, rebounds: 2, assists: 6, steals: 0, blocks: 0, turnovers: 4, fouls: 2,
    plusMinus: -5, efficiency: 12.8, usage: 26.8, fatigue: 58, hotStreak: false, coldStreak: true,
    projectedPoints: 15, injuryRisk: 12, clutchRating: 6, onCourt: false, minutesPlayed: 22, restTime: 8
  },
  {
    playerId: 'vanderbilt', name: 'Jarred Vanderbilt', team: 'home', position: 'PF', jersey: 2,
    points: 6, rebounds: 7, assists: 1, steals: 2, blocks: 1, turnovers: 0, fouls: 1,
    plusMinus: 4, efficiency: 15.6, usage: 12.4, fatigue: 38, hotStreak: false, coldStreak: false,
    projectedPoints: 8, injuryRisk: 20, clutchRating: 7, onCourt: false, minutesPlayed: 18, restTime: 12
  }
];

const mockAwayPlayers: PlayerPerformance[] = [
  {
    playerId: 'tatum', name: 'Jayson Tatum', team: 'away', position: 'SF', jersey: 0,
    points: 26, rebounds: 6, assists: 4, steals: 1, blocks: 0, turnovers: 2, fouls: 2,
    plusMinus: 5, efficiency: 31.2, usage: 33.1, fatigue: 68, hotStreak: true, coldStreak: false,
    projectedPoints: 35, injuryRisk: 10, clutchRating: 9, onCourt: true, minutesPlayed: 29, restTime: 0
  },
  {
    playerId: 'brown', name: 'Jaylen Brown', team: 'away', position: 'SG', jersey: 7,
    points: 22, rebounds: 5, assists: 3, steals: 2, blocks: 1, turnovers: 1, fouls: 1,
    plusMinus: 3, efficiency: 26.8, usage: 29.4, fatigue: 62, hotStreak: false, coldStreak: false,
    projectedPoints: 28, injuryRisk: 8, clutchRating: 8, onCourt: true, minutesPlayed: 27, restTime: 0
  },
  {
    playerId: 'porzingis', name: 'Kristaps Porzingis', team: 'away', position: 'C', jersey: 8,
    points: 15, rebounds: 9, assists: 1, steals: 0, blocks: 2, turnovers: 2, fouls: 3,
    plusMinus: 1, efficiency: 20.4, usage: 22.8, fatigue: 75, hotStreak: false, coldStreak: false,
    projectedPoints: 20, injuryRisk: 35, clutchRating: 6, onCourt: true, minutesPlayed: 24, restTime: 0
  }
];

const mockHomeMetrics: TeamMetrics = {
  team: 'home', teamName: 'Lakers',
  fieldGoalPercentage: 47.8, threePointPercentage: 34.6, freeThrowPercentage: 78.9,
  totalRebounds: 32, assists: 21, turnovers: 10,
  pace: 102.4, offensiveRating: 112.8, defensiveRating: 116.2, netRating: -3.4,
  momentum: -15, energyLevel: 72, chemistry: 84, coaching: 88,
  winProbability: 44, projectedFinalScore: 118
};

const mockAwayMetrics: TeamMetrics = {
  team: 'away', teamName: 'Celtics',
  fieldGoalPercentage: 52.1, threePointPercentage: 41.2, freeThrowPercentage: 85.7,
  totalRebounds: 28, assists: 24, turnovers: 8,
  pace: 98.6, offensiveRating: 118.5, defensiveRating: 108.9, netRating: 9.6,
  momentum: 18, energyLevel: 85, chemistry: 91, coaching: 92,
  winProbability: 56, projectedFinalScore: 124
};

const mockAIInsights: AIInsight[] = [
  {
    id: 'insight-1', type: 'substitution', priority: 'high',
    title: 'D\'Angelo Russell Cold Streak Alert',
    description: 'Russell is 2/9 FG with 4 turnovers. Consider substituting for Reaves who is hot.',
    confidence: 87, timeGenerated: new Date(), actionable: true,
    impact: 'Could improve offense by +8.2 rating',
    recommendation: 'Sub Russell for Reaves, move to bench unit leader role'
  },
  {
    id: 'insight-2', type: 'matchup', priority: 'critical',
    title: 'Tatum Exploiting Switch Defense',
    description: 'Tatum is 4/5 when switched onto guards. Adjust defensive scheme.',
    confidence: 92, timeGenerated: new Date(Date.now() - 120000), actionable: true,
    impact: 'Could reduce opponent scoring by 12%',
    recommendation: 'Implement no-switch policy on Tatum possessions'
  },
  {
    id: 'insight-3', type: 'injury', priority: 'medium',
    title: 'AD Fatigue Risk Increasing',
    description: 'Davis showing 72% fatigue with elevated injury risk. Monitor closely.',
    confidence: 78, timeGenerated: new Date(Date.now() - 300000), actionable: false,
    impact: 'Injury risk: 25% and climbing',
    recommendation: 'Consider 3-4 minute rest period'
  },
  {
    id: 'insight-4', type: 'opportunity', priority: 'high',
    title: 'Paint Advantage Available',
    description: 'Celtics have allowed 68% FG in paint last 5 minutes. Attack inside.',
    confidence: 85, timeGenerated: new Date(Date.now() - 180000), actionable: true,
    impact: 'Expected +15% scoring efficiency',
    recommendation: 'Run post-up plays for AD, drive penetration for LeBron'
  },
  {
    id: 'insight-5', type: 'timeout', priority: 'medium',
    title: 'Momentum Shift Detected',
    description: 'Celtics on 8-2 run, team energy declining. Strategic timeout recommended.',
    confidence: 79, timeGenerated: new Date(Date.now() - 60000), actionable: true,
    impact: 'Could halt momentum shift',
    recommendation: 'Call timeout, emphasize defensive communication'
  }
];

export default function GameIntelligenceDashboard({
  gameData = mockGameData,
  homePerformances = mockHomePlayers,
  awayPerformances = mockAwayPlayers,
  homeMetrics = mockHomeMetrics,
  awayMetrics = mockAwayMetrics,
  aiInsights = mockAIInsights,
  isLive = true
}: GameIntelligenceProps) {
  const [selectedTab, setSelectedTab] = useState<'overview' | 'players' | 'insights' | 'predictions'>('overview');
  const [selectedTeam, setSelectedTeam] = useState<'home' | 'away' | 'both'>('both');
  const [alertsEnabled, setAlertsEnabled] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(isLive);
  const [refreshInterval, setRefreshInterval] = useState([5]);
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [compactMode, setCompactMode] = useState(false);
  const [timeElapsed, setTimeElapsed] = useState(0);
  const animationRef = useRef<number | null>(null);

  // Live data simulation
  useEffect(() => {
    if (autoRefresh && isLive) {
      const interval = setInterval(() => {
        setTimeElapsed(prev => prev + 1);
        // Simulate live data updates here
      }, refreshInterval[0] * 1000);
      
      return () => clearInterval(interval);
    }
  }, [autoRefresh, isLive, refreshInterval]);

  // Get priority color for insights
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return '#ef4444';
      case 'high': return '#f97316';
      case 'medium': return '#f59e0b';
      case 'low': return '#6b7280';
      default: return '#6b7280';
    }
  };

  // Get momentum indicator
  const getMomentumIndicator = (momentum: number) => {
    if (momentum > 10) return { icon: TrendingUp, color: '#10b981', text: 'Strong' };
    if (momentum > 0) return { icon: TrendingUp, color: '#3b82f6', text: 'Positive' };
    if (momentum < -10) return { icon: TrendingDown, color: '#ef4444', text: 'Poor' };
    return { icon: TrendingDown, color: '#f97316', text: 'Negative' };
  };

  // Calculate team comparison
  const teamComparison = useMemo(() => {
    return {
      scoreDifference: gameData.homeScore - gameData.awayScore,
      fgDifference: homeMetrics.fieldGoalPercentage - awayMetrics.fieldGoalPercentage,
      threePtDifference: homeMetrics.threePointPercentage - awayMetrics.threePointPercentage,
      reboundDifference: homeMetrics.totalRebounds - awayMetrics.totalRebounds,
      assistDifference: homeMetrics.assists - awayMetrics.assists,
      netRatingDifference: homeMetrics.netRating - awayMetrics.netRating
    };
  }, [gameData, homeMetrics, awayMetrics]);

  // Filter insights by priority
  const criticalInsights = aiInsights.filter(insight => insight.priority === 'critical');
  const actionableInsights = aiInsights.filter(insight => insight.actionable);

  return (
    <div className="space-y-6">
      {/* Header & Game Status */}
      <Card className="border-2 border-blue-500">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-xl font-bold flex items-center gap-3">
                <Brain className="w-6 h-6 text-blue-500" />
                Game Intelligence Dashboard
                <Badge variant={isLive ? 'default' : 'secondary'} className="flex items-center gap-1">
                  {isLive ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                  {isLive ? 'LIVE' : 'OFFLINE'}
                </Badge>
              </h3>
              <div className="flex items-center gap-6 mt-2 text-sm text-muted-foreground">
                <span className="text-lg font-bold text-foreground">
                  {gameData.awayTeam} {gameData.awayScore} - {gameData.homeScore} {gameData.homeTeam}
                </span>
                <span>Q{gameData.quarter} • {gameData.timeRemaining}</span>
                <span>Shot Clock: {gameData.shotClock}s</span>
                <span>📺 {gameData.broadcast}</span>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant={soundEnabled ? 'default' : 'outline'}
                  onClick={() => setSoundEnabled(!soundEnabled)}
                >
                  {soundEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
                </Button>
                <Button
                  size="sm"
                  variant={autoRefresh ? 'default' : 'outline'}
                  onClick={() => setAutoRefresh(!autoRefresh)}
                >
                  {autoRefresh ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </Button>
                <Button size="sm" variant="outline">
                  <Settings className="w-4 h-4" />
                </Button>
              </div>
              
              <Tabs value={selectedTab} onValueChange={(value: any) => setSelectedTab(value)}>
                <TabsList>
                  <TabsTrigger value="overview">Overview</TabsTrigger>
                  <TabsTrigger value="players">Players</TabsTrigger>
                  <TabsTrigger value="insights">AI Insights</TabsTrigger>
                  <TabsTrigger value="predictions">Predictions</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Critical Alerts */}
      {criticalInsights.length > 0 && alertsEnabled && (
        <Card className="border-2 border-red-500 bg-red-50">
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-3">
              <AlertTriangle className="w-5 h-5 text-red-500" />
              <h4 className="font-semibold text-red-800">Critical Alerts ({criticalInsights.length})</h4>
            </div>
            <div className="space-y-2">
              {criticalInsights.map(insight => (
                <div key={insight.id} className="bg-white p-3 rounded-lg border border-red-200">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-red-800">{insight.title}</span>
                    <Badge variant="destructive">{insight.confidence}% confidence</Badge>
                  </div>
                  <p className="text-sm text-red-700 mt-1">{insight.description}</p>
                  <p className="text-sm font-medium text-red-800 mt-2">→ {insight.recommendation}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Dashboard Content */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        {/* Team Comparison */}
        <Card className="xl:col-span-2">
          <CardHeader>
            <h4 className="font-semibold flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Team Performance Comparison
            </h4>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Score */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium">Score</span>
                  <span className={`text-sm ${teamComparison.scoreDifference > 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {teamComparison.scoreDifference > 0 ? '+' : ''}{teamComparison.scoreDifference}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs w-12">{awayMetrics.teamName}</span>
                  <div className="flex-1 bg-gray-200 rounded-full h-2 relative">
                    <div 
                      className="bg-blue-500 h-2 rounded-full transition-all duration-300" 
                      style={{ width: `${(gameData.awayScore / (gameData.homeScore + gameData.awayScore)) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs w-12 text-right">{homeMetrics.teamName}</span>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>{gameData.awayScore}</span>
                  <span>{gameData.homeScore}</span>
                </div>
              </div>

              {/* Win Probability */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium">Win Probability</span>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">{awayMetrics.winProbability}%</Badge>
                    <Badge variant="outline">{homeMetrics.winProbability}%</Badge>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs w-12">{awayMetrics.teamName}</span>
                  <div className="flex-1 bg-gray-200 rounded-full h-3 relative">
                    <div 
                      className="bg-gradient-to-r from-blue-500 to-blue-600 h-3 rounded-full transition-all duration-300" 
                      style={{ width: `${awayMetrics.winProbability}%` }}
                    />
                    <div 
                      className="bg-gradient-to-r from-red-500 to-red-600 h-3 rounded-full transition-all duration-300 absolute right-0 top-0" 
                      style={{ width: `${homeMetrics.winProbability}%` }}
                    />
                  </div>
                  <span className="text-xs w-12 text-right">{homeMetrics.teamName}</span>
                </div>
              </div>

              {/* Momentum */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium">Momentum</span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex items-center gap-2">
                    {(() => {
                      const awayMomentum = getMomentumIndicator(awayMetrics.momentum);
                      return (
                        <div className="flex items-center gap-2">
                          <awayMomentum.icon className="w-4 h-4" style={{ color: awayMomentum.color }} />
                          <span className="text-sm">{awayMetrics.teamName}: {awayMomentum.text}</span>
                        </div>
                      );
                    })()}
                  </div>
                  <div className="flex items-center gap-2">
                    {(() => {
                      const homeMomentum = getMomentumIndicator(homeMetrics.momentum);
                      return (
                        <div className="flex items-center gap-2">
                          <homeMomentum.icon className="w-4 h-4" style={{ color: homeMomentum.color }} />
                          <span className="text-sm">{homeMetrics.teamName}: {homeMomentum.text}</span>
                        </div>
                      );
                    })()}
                  </div>
                </div>
              </div>

              {/* Key Stats */}
              <div className="grid grid-cols-3 gap-3 text-xs">
                <div>
                  <div className="text-muted-foreground">FG%</div>
                  <div className="flex justify-between">
                    <span>{awayMetrics.fieldGoalPercentage.toFixed(1)}%</span>
                    <span>{homeMetrics.fieldGoalPercentage.toFixed(1)}%</span>
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">3P%</div>
                  <div className="flex justify-between">
                    <span>{awayMetrics.threePointPercentage.toFixed(1)}%</span>
                    <span>{homeMetrics.threePointPercentage.toFixed(1)}%</span>
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">AST</div>
                  <div className="flex justify-between">
                    <span>{awayMetrics.assists}</span>
                    <span>{homeMetrics.assists}</span>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Live AI Insights */}
        <Card className="xl:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <h4 className="font-semibold flex items-center gap-2">
                <Brain className="w-4 h-4" />
                AI Insights ({aiInsights.length})
              </h4>
              <Badge variant="outline">{actionableInsights.length} actionable</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 max-h-64 overflow-y-auto">
              {aiInsights.slice(0, 5).map(insight => (
                <div key={insight.id} className="p-3 border rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div 
                        className="w-2 h-2 rounded-full" 
                        style={{ backgroundColor: getPriorityColor(insight.priority) }}
                      />
                      <span className="text-sm font-medium">{insight.title}</span>
                      {insight.actionable && <CheckCircle className="w-3 h-3 text-green-500" />}
                    </div>
                    <Badge variant="outline" className="text-xs">
                      {insight.confidence}%
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mb-2">{insight.description}</p>
                  <div className="text-xs">
                    <span className="font-medium">Impact:</span> {insight.impact}
                  </div>
                  <div className="text-xs">
                    <span className="font-medium">Action:</span> {insight.recommendation}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {new Date(insight.timeGenerated).toLocaleTimeString()}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Player Performance Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Home Team Players */}
        <Card>
          <CardHeader>
            <h4 className="font-semibold flex items-center gap-2">
              <Users className="w-4 h-4" />
              {homeMetrics.teamName} Players
            </h4>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {homePerformances.map(player => (
                <div key={player.playerId} className="p-3 border rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold ${player.onCourt ? 'bg-green-500' : 'bg-gray-400'}`}>
                        {player.jersey}
                      </div>
                      <div>
                        <div className="font-medium text-sm">{player.name}</div>
                        <div className="text-xs text-muted-foreground">{player.position} • {player.minutesPlayed} min</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {player.hotStreak && <Zap className="w-3 h-3 text-orange-500" />}
                      {player.coldStreak && <XCircle className="w-3 h-3 text-blue-500" />}
                      <Badge variant={player.plusMinus >= 0 ? 'default' : 'destructive'} className="text-xs">
                        {player.plusMinus >= 0 ? '+' : ''}{player.plusMinus}
                      </Badge>
                    </div>
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-xs">
                    <div>
                      <div className="text-muted-foreground">PTS</div>
                      <div className="font-medium">{player.points}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">REB</div>
                      <div className="font-medium">{player.rebounds}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">AST</div>
                      <div className="font-medium">{player.assists}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">EFF</div>
                      <div className="font-medium">{player.efficiency.toFixed(1)}</div>
                    </div>
                  </div>
                  <div className="mt-2">
                    <div className="flex justify-between text-xs mb-1">
                      <span>Fatigue</span>
                      <span>{player.fatigue}%</span>
                    </div>
                    <Progress 
                      value={player.fatigue} 
                      className="h-2" 
                    />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Away Team Players */}
        <Card>
          <CardHeader>
            <h4 className="font-semibold flex items-center gap-2">
              <Users className="w-4 h-4" />
              {awayMetrics.teamName} Players
            </h4>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {awayPerformances.map(player => (
                <div key={player.playerId} className="p-3 border rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold ${player.onCourt ? 'bg-blue-500' : 'bg-gray-400'}`}>
                        {player.jersey}
                      </div>
                      <div>
                        <div className="font-medium text-sm">{player.name}</div>
                        <div className="text-xs text-muted-foreground">{player.position} • {player.minutesPlayed} min</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {player.hotStreak && <Zap className="w-3 h-3 text-orange-500" />}
                      {player.coldStreak && <XCircle className="w-3 h-3 text-blue-500" />}
                      <Badge variant={player.plusMinus >= 0 ? 'default' : 'destructive'} className="text-xs">
                        {player.plusMinus >= 0 ? '+' : ''}{player.plusMinus}
                      </Badge>
                    </div>
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-xs">
                    <div>
                      <div className="text-muted-foreground">PTS</div>
                      <div className="font-medium">{player.points}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">REB</div>
                      <div className="font-medium">{player.rebounds}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">AST</div>
                      <div className="font-medium">{player.assists}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">EFF</div>
                      <div className="font-medium">{player.efficiency.toFixed(1)}</div>
                    </div>
                  </div>
                  <div className="mt-2">
                    <div className="flex justify-between text-xs mb-1">
                      <span>Fatigue</span>
                      <span>{player.fatigue}%</span>
                    </div>
                    <Progress 
                      value={player.fatigue} 
                      className="h-2" 
                    />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Advanced Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">{awayMetrics.pace.toFixed(1)}</div>
            <div className="text-sm text-muted-foreground">{awayMetrics.teamName} Pace</div>
            <div className="text-xs text-muted-foreground mt-1">vs {homeMetrics.pace.toFixed(1)} {homeMetrics.teamName}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-green-600">{awayMetrics.offensiveRating.toFixed(1)}</div>
            <div className="text-sm text-muted-foreground">{awayMetrics.teamName} OFF RTG</div>
            <div className="text-xs text-muted-foreground mt-1">vs {homeMetrics.offensiveRating.toFixed(1)} {homeMetrics.teamName}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-red-600">{awayMetrics.defensiveRating.toFixed(1)}</div>
            <div className="text-sm text-muted-foreground">{awayMetrics.teamName} DEF RTG</div>
            <div className="text-xs text-muted-foreground mt-1">vs {homeMetrics.defensiveRating.toFixed(1)} {homeMetrics.teamName}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-purple-600">{awayMetrics.netRating.toFixed(1)}</div>
            <div className="text-sm text-muted-foreground">{awayMetrics.teamName} NET RTG</div>
            <div className="text-xs text-muted-foreground mt-1">vs {homeMetrics.netRating.toFixed(1)} {homeMetrics.teamName}</div>
          </CardContent>
        </Card>
      </div>

      {/* Settings Panel */}
      <Card>
        <CardHeader>
          <h4 className="font-semibold flex items-center gap-2">
            <Settings className="w-4 h-4" />
            Dashboard Settings
          </h4>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm">Auto Refresh</Label>
                <Switch checked={autoRefresh} onCheckedChange={setAutoRefresh} />
              </div>
              <div>
                <Label className="text-sm">Refresh Interval: {refreshInterval[0]}s</Label>
                <Slider
                  value={refreshInterval}
                  onValueChange={setRefreshInterval}
                  min={1}
                  max={30}
                  step={1}
                  className="mt-2"
                />
              </div>
            </div>
            
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm">Sound Alerts</Label>
                <Switch checked={soundEnabled} onCheckedChange={setSoundEnabled} />
              </div>
              <div className="flex items-center justify-between">
                <Label className="text-sm">Critical Alerts</Label>
                <Switch checked={alertsEnabled} onCheckedChange={setAlertsEnabled} />
              </div>
            </div>
            
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm">Compact Mode</Label>
                <Switch checked={compactMode} onCheckedChange={setCompactMode} />
              </div>
              <div>
                <Label className="text-sm">Team Focus</Label>
                <Select value={selectedTeam} onValueChange={(value: any) => setSelectedTeam(value)}>
                  <SelectTrigger className="mt-2">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="both">Both Teams</SelectItem>
                    <SelectItem value="home">{homeMetrics.teamName}</SelectItem>
                    <SelectItem value="away">{awayMetrics.teamName}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            <div className="space-y-3">
              <div className="text-sm text-muted-foreground">
                Live Updates: {timeElapsed}s
              </div>
              <div className="text-sm text-muted-foreground">
                Last Updated: {new Date().toLocaleTimeString()}
              </div>
              <Button size="sm" variant="outline" className="w-full">
                <Maximize2 className="w-4 h-4 mr-2" />
                Fullscreen
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
} 