"use client";

import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  TrendingUp, 
  TrendingDown, 
  Activity, 
  Calendar, 
  Target,
  AlertTriangle,
  Trophy,
  Zap,
  Heart,
  Users,
  BarChart3,
  Play,
  Pause,
  RotateCcw
} from 'lucide-react';

interface GameData {
  id: string;
  gameNumber: number;
  date: string;
  opponent: string;
  isHome: boolean;
  result: 'W' | 'L';
  score: { team: number; opponent: number };
  // Player stats
  points: number;
  rebounds: number;
  assists: number;
  steals: number;
  blocks: number;
  turnovers: number;
  fieldGoalPercentage: number;
  threePointPercentage: number;
  freeThrowPercentage: number;
  // Advanced metrics
  plusMinus: number;
  offensiveRating: number;
  defensiveRating: number;
  usageRate: number;
  efficiency: number;
  // Context
  minutesPlayed: number;
  isInjured?: boolean;
  injuryType?: string;
  isBackToBack?: boolean;
  daysRest: number;
  // Momentum and streaks
  teamWinStreak: number;
  performanceGrade: 'A' | 'B' | 'C' | 'D' | 'F';
  gameImportance: 'low' | 'medium' | 'high' | 'critical';
  clutchRating: number; // 1-10
}

interface TimelineProps {
  playerName: string;
  season: string;
  games: GameData[];
  metric: string;
}

// Mock game data for demonstration
const mockGames: GameData[] = [
  {
    id: 'game-1', gameNumber: 1, date: '2024-10-15', opponent: 'Nuggets', isHome: true, 
    result: 'W', score: { team: 119, opponent: 107 }, points: 21, rebounds: 8, assists: 5, 
    steals: 1, blocks: 1, turnovers: 3, fieldGoalPercentage: 52.4, threePointPercentage: 33.3,
    freeThrowPercentage: 80.0, plusMinus: 15, offensiveRating: 118, defensiveRating: 105,
    usageRate: 28.5, efficiency: 24.8, minutesPlayed: 35, daysRest: 4, teamWinStreak: 1,
    performanceGrade: 'B', gameImportance: 'high', clutchRating: 7
  },
  {
    id: 'game-2', gameNumber: 2, date: '2024-10-17', opponent: 'Suns', isHome: false, 
    result: 'L', score: { team: 109, opponent: 114 }, points: 32, rebounds: 11, assists: 6, 
    steals: 2, blocks: 0, turnovers: 5, fieldGoalPercentage: 58.3, threePointPercentage: 44.4,
    freeThrowPercentage: 87.5, plusMinus: -8, offensiveRating: 125, defensiveRating: 118,
    usageRate: 32.1, efficiency: 31.2, minutesPlayed: 39, isBackToBack: false, daysRest: 2, 
    teamWinStreak: 0, performanceGrade: 'A', gameImportance: 'medium', clutchRating: 9
  },
  {
    id: 'game-3', gameNumber: 3, date: '2024-10-19', opponent: 'Warriors', isHome: true, 
    result: 'W', score: { team: 123, opponent: 118 }, points: 28, rebounds: 7, assists: 8, 
    steals: 1, blocks: 2, turnovers: 2, fieldGoalPercentage: 61.1, threePointPercentage: 50.0,
    freeThrowPercentage: 100.0, plusMinus: 18, offensiveRating: 132, defensiveRating: 112,
    usageRate: 29.8, efficiency: 35.4, minutesPlayed: 37, daysRest: 2, teamWinStreak: 1,
    performanceGrade: 'A', gameImportance: 'high', clutchRating: 8
  },
  {
    id: 'game-4', gameNumber: 4, date: '2024-10-21', opponent: 'Clippers', isHome: false, 
    result: 'L', score: { team: 98, opponent: 103 }, points: 15, rebounds: 6, assists: 4, 
    steals: 0, blocks: 1, turnovers: 4, fieldGoalPercentage: 38.5, threePointPercentage: 25.0,
    freeThrowPercentage: 66.7, plusMinus: -12, offensiveRating: 95, defensiveRating: 108,
    usageRate: 26.3, efficiency: 12.8, minutesPlayed: 32, isInjured: true, injuryType: 'ankle',
    daysRest: 2, teamWinStreak: 0, performanceGrade: 'D', gameImportance: 'medium', clutchRating: 3
  },
  {
    id: 'game-5', gameNumber: 5, date: '2024-10-23', opponent: 'Kings', isHome: true, 
    result: 'W', score: { team: 131, opponent: 127 }, points: 35, rebounds: 9, assists: 12, 
    steals: 3, blocks: 1, turnovers: 3, fieldGoalPercentage: 64.7, threePointPercentage: 55.6,
    freeThrowPercentage: 91.7, plusMinus: 22, offensiveRating: 145, defensiveRating: 98,
    usageRate: 34.5, efficiency: 42.1, minutesPlayed: 41, daysRest: 2, teamWinStreak: 1,
    performanceGrade: 'A', gameImportance: 'medium', clutchRating: 10
  },
  {
    id: 'game-6', gameNumber: 6, date: '2024-10-25', opponent: 'Mavericks', isHome: false, 
    result: 'W', score: { team: 116, opponent: 110 }, points: 24, rebounds: 8, assists: 7, 
    steals: 2, blocks: 0, turnovers: 1, fieldGoalPercentage: 50.0, threePointPercentage: 37.5,
    freeThrowPercentage: 100.0, plusMinus: 8, offensiveRating: 115, defensiveRating: 102,
    usageRate: 28.9, efficiency: 28.3, minutesPlayed: 35, daysRest: 2, teamWinStreak: 2,
    performanceGrade: 'B', gameImportance: 'low', clutchRating: 6
  },
];

export default function PerformanceTimeline({ 
  playerName = "LeBron James", 
  season = "2024-25", 
  games = mockGames,
  metric = "points"
}: TimelineProps) {
  const [selectedGame, setSelectedGame] = useState<GameData | null>(null);
  const [timelinePosition, setTimelinePosition] = useState([games.length]);
  const [viewMode, setViewMode] = useState<'performance' | 'efficiency' | 'impact' | 'health'>('performance');
  const [showInjuries, setShowInjuries] = useState(true);
  const [showMomentum, setShowMomentum] = useState(true);
  const [showTrends, setShowTrends] = useState(true);
  const [isAnimating, setIsAnimating] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState([1]);

  // Filter games up to timeline position
  const visibleGames = games.slice(0, timelinePosition[0]);

  // Calculate trend metrics
  const trendMetrics = useMemo(() => {
    if (visibleGames.length < 3) return null;
    
    const recent5 = visibleGames.slice(-5);
    const previous5 = visibleGames.slice(-10, -5);
    
    const avgRecent = recent5.reduce((sum, game) => sum + game.points, 0) / recent5.length;
    const avgPrevious = previous5.length > 0 ? previous5.reduce((sum, game) => sum + game.points, 0) / previous5.length : avgRecent;
    
    const trend = avgRecent - avgPrevious;
    const efficiency = recent5.reduce((sum, game) => sum + game.efficiency, 0) / recent5.length;
    const winRate = recent5.filter(game => game.result === 'W').length / recent5.length;
    
        return {      trend: trend.toFixed(1),      trendValue: trend,      efficiency: efficiency.toFixed(1),      winRate: (winRate * 100).toFixed(0),      direction: trend > 2 ? 'up' : trend < -2 ? 'down' : 'stable'    };
  }, [visibleGames]);

  // Get performance color based on grade
  const getPerformanceColor = (grade: string) => {
    switch (grade) {
      case 'A': return '#10b981';
      case 'B': return '#3b82f6';
      case 'C': return '#f59e0b';
      case 'D': return '#f97316';
      case 'F': return '#ef4444';
      default: return '#6b7280';
    }
  };

  // Get metric value for display
  const getMetricValue = (game: GameData, selectedMetric: string) => {
    switch (selectedMetric) {
      case 'points': return game.points;
      case 'efficiency': return game.efficiency;
      case 'plusMinus': return game.plusMinus;
      case 'usage': return game.usageRate;
      case 'offensive': return game.offensiveRating;
      case 'defensive': return game.defensiveRating;
      default: return game.points;
    }
  };

  // Calculate moving average
  const getMovingAverage = (gameIndex: number, window: number = 5) => {
    const start = Math.max(0, gameIndex - window + 1);
    const relevantGames = visibleGames.slice(start, gameIndex + 1);
    return relevantGames.reduce((sum, game) => sum + getMetricValue(game, metric), 0) / relevantGames.length;
  };

  // Animate timeline playback
  const handlePlayback = () => {
    if (isAnimating) {
      setIsAnimating(false);
      return;
    }
    
    setIsAnimating(true);
    let position = 1;
    const interval = setInterval(() => {
      position += 1;
      setTimelinePosition([position]);
      
      if (position >= games.length) {
        setIsAnimating(false);
        clearInterval(interval);
      }
    }, 1000 / playbackSpeed[0]);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Calendar className="w-5 h-5" />
                {playerName} Performance Timeline
                <Badge variant="outline">{season}</Badge>
              </h3>
              <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                <span>Game {timelinePosition[0]} of {games.length}</span>
                {trendMetrics && (
                  <>
                    <span className="flex items-center gap-1">
                      {trendMetrics.direction === 'up' ? (
                        <TrendingUp className="w-4 h-4 text-green-500" />
                      ) : trendMetrics.direction === 'down' ? (
                        <TrendingDown className="w-4 h-4 text-red-500" />
                      ) : (
                        <Activity className="w-4 h-4 text-blue-500" />
                      )}
                      Trend: {trendMetrics.trendValue > 0 ? '+' : ''}{trendMetrics.trend}
                    </span>
                    <span>Win Rate: {trendMetrics.winRate}%</span>
                  </>
                )}
              </div>
            </div>
            
            <Tabs value={viewMode} onValueChange={(value: any) => setViewMode(value)}>
              <TabsList>
                <TabsTrigger value="performance">Performance</TabsTrigger>
                <TabsTrigger value="efficiency">Efficiency</TabsTrigger>
                <TabsTrigger value="impact">Impact</TabsTrigger>
                <TabsTrigger value="health">Health</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </CardHeader>
      </Card>

      {/* Controls */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <Label className="text-sm font-medium">Metric</Label>
            <Select value={metric} onValueChange={() => {}}>
              <SelectTrigger className="mt-2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="points">Points</SelectItem>
                <SelectItem value="efficiency">Efficiency</SelectItem>
                <SelectItem value="plusMinus">Plus/Minus</SelectItem>
                <SelectItem value="usage">Usage Rate</SelectItem>
                <SelectItem value="offensive">Offensive Rating</SelectItem>
                <SelectItem value="defensive">Defensive Rating</SelectItem>
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <Label className="text-sm font-medium">Timeline Control</Label>
            <div className="mt-2">
              <Slider
                value={timelinePosition}
                onValueChange={setTimelinePosition}
                min={1}
                max={games.length}
                step={1}
                className="mt-1"
              />
              <div className="text-xs text-muted-foreground mt-1">
                Showing first {timelinePosition[0]} games
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <Label className="text-sm">Show Injuries</Label>
              <Switch checked={showInjuries} onCheckedChange={setShowInjuries} />
            </div>
            <div className="flex items-center justify-between">
              <Label className="text-sm">Show Momentum</Label>
              <Switch checked={showMomentum} onCheckedChange={setShowMomentum} />
            </div>
            <div className="flex items-center justify-between">
              <Label className="text-sm">Show Trends</Label>
              <Switch checked={showTrends} onCheckedChange={setShowTrends} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <Label className="text-sm font-medium">Playback</Label>
            <div className="flex items-center gap-2 mt-2">
              <Button
                size="sm"
                onClick={handlePlayback}
                className="flex-1"
              >
                {isAnimating ? <Pause className="w-4 h-4 mr-2" /> : <Play className="w-4 h-4 mr-2" />}
                {isAnimating ? 'Pause' : 'Play'}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setTimelinePosition([1])}
              >
                <RotateCcw className="w-4 h-4" />
              </Button>
            </div>
            <div className="mt-3">
              <Label className="text-xs">Speed: {playbackSpeed[0]}x</Label>
              <Slider
                value={playbackSpeed}
                onValueChange={setPlaybackSpeed}
                min={0.5}
                max={3}
                step={0.5}
                className="mt-1"
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Timeline Visualization */}
      <Card>
        <CardContent className="p-6">
          <div className="relative h-96 overflow-hidden">
            {/* Background grid */}
            <svg className="absolute inset-0 w-full h-full" viewBox={`0 0 ${Math.max(800, visibleGames.length * 40)} 400`}>
              <defs>
                <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#f3f4f6" strokeWidth="1"/>
                </pattern>
                <linearGradient id="performanceGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" style={{stopColor: '#10b981', stopOpacity: 0.8}} />
                  <stop offset="50%" style={{stopColor: '#f59e0b', stopOpacity: 0.6}} />
                  <stop offset="100%" style={{stopColor: '#ef4444', stopOpacity: 0.8}} />
                </linearGradient>
              </defs>
              
              <rect width="100%" height="100%" fill="url(#grid)" />
              
              {/* Trend line */}
              {showTrends && visibleGames.length > 1 && (
                <path
                  d={`M ${visibleGames.map((game, index) => 
                    `${index * 40 + 20},${350 - (getMovingAverage(index) / Math.max(...visibleGames.map(g => getMetricValue(g, metric))) * 280)}`
                  ).join(' L ')}`}
                  stroke="#3b82f6"
                  strokeWidth="2"
                  fill="none"
                  strokeDasharray="5,5"
                  opacity="0.7"
                />
              )}
              
              {/* Performance bars */}
              {visibleGames.map((game, index) => {
                const value = getMetricValue(game, metric);
                const maxValue = Math.max(...visibleGames.map(g => getMetricValue(g, metric)));
                const height = (value / maxValue) * 280;
                const x = index * 40 + 10;
                const y = 350 - height;
                
                return (
                  <g key={game.id}>
                    {/* Performance bar */}
                    <rect
                      x={x}
                      y={y}
                      width="20"
                      height={height}
                      fill={getPerformanceColor(game.performanceGrade)}
                      stroke={game.result === 'W' ? '#10b981' : '#ef4444'}
                      strokeWidth="2"
                      className="cursor-pointer transition-all duration-200 hover:opacity-80"
                      onClick={() => setSelectedGame(game)}
                    />
                    
                    {/* Game result indicator */}
                    <circle
                      cx={x + 10}
                      cy={game.result === 'W' ? y - 10 : y + height + 10}
                      r="4"
                      fill={game.result === 'W' ? '#10b981' : '#ef4444'}
                      stroke="#ffffff"
                      strokeWidth="1"
                    />
                    
                    {/* Injury indicator */}
                    {showInjuries && game.isInjured && (
                      <g>
                        <circle cx={x + 10} cy="30" r="6" fill="#ef4444" opacity="0.8" />
                        <text x={x + 10} y="34" textAnchor="middle" className="text-white text-xs font-bold">!</text>
                      </g>
                    )}
                    
                    {/* Momentum indicator */}
                    {showMomentum && game.teamWinStreak > 0 && (
                      <rect
                        x={x + 5}
                        y="10"
                        width="10"
                        height={Math.min(game.teamWinStreak * 3, 20)}
                        fill="#22c55e"
                        opacity="0.6"
                      />
                    )}
                    
                    {/* Game importance */}
                    {game.gameImportance === 'critical' && (
                      <polygon
                        points={`${x + 10},5 ${x + 15},15 ${x + 5},15`}
                        fill="#fbbf24"
                        stroke="#f59e0b"
                        strokeWidth="1"
                      />
                    )}
                    
                    {/* Value label */}
                    <text
                      x={x + 10}
                      y={y - 5}
                      textAnchor="middle"
                      className="text-xs font-medium fill-gray-700"
                    >
                      {value.toFixed(0)}
                    </text>
                    
                    {/* Game number */}
                    <text
                      x={x + 10}
                      y="380"
                      textAnchor="middle"
                      className="text-xs fill-gray-500"
                    >
                      {game.gameNumber}
                    </text>
                  </g>
                );
              })}
            </svg>
            
            {/* Legend */}
            <div className="absolute top-4 right-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 space-y-2 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500 rounded"></div>
                <span>Grade A</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-blue-500 rounded"></div>
                <span>Grade B</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-yellow-500 rounded"></div>
                <span>Grade C</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-500 rounded"></div>
                <span>Grade D/F</span>
              </div>
              {showInjuries && (
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-3 h-3 text-red-500" />
                  <span>Injury</span>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Game Details */}
      {selectedGame && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h4 className="font-semibold flex items-center gap-2">
                <Target className="w-5 h-5" />
                Game {selectedGame.gameNumber} Details
                <Badge variant={selectedGame.result === 'W' ? 'default' : 'destructive'}>
                  {selectedGame.result}
                </Badge>
              </h4>
              <Button size="sm" variant="ghost" onClick={() => setSelectedGame(null)}>
                ×
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <h5 className="font-medium mb-3">Game Info</h5>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>Date:</span>
                    <span>{new Date(selectedGame.date).toLocaleDateString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Opponent:</span>
                    <span>{selectedGame.isHome ? 'vs' : '@'} {selectedGame.opponent}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Score:</span>
                    <span>{selectedGame.score.team}-{selectedGame.score.opponent}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Minutes:</span>
                    <span>{selectedGame.minutesPlayed}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Performance:</span>
                    <Badge style={{ backgroundColor: getPerformanceColor(selectedGame.performanceGrade) }}>
                      Grade {selectedGame.performanceGrade}
                    </Badge>
                  </div>
                </div>
              </div>
              
              <div>
                <h5 className="font-medium mb-3">Statistics</h5>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>Points:</span>
                    <span className="font-medium">{selectedGame.points}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Rebounds:</span>
                    <span className="font-medium">{selectedGame.rebounds}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Assists:</span>
                    <span className="font-medium">{selectedGame.assists}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>FG%:</span>
                    <span className="font-medium">{selectedGame.fieldGoalPercentage.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>3P%:</span>
                    <span className="font-medium">{selectedGame.threePointPercentage.toFixed(1)}%</span>
                  </div>
                </div>
              </div>
              
              <div>
                <h5 className="font-medium mb-3">Advanced Metrics</h5>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>Plus/Minus:</span>
                    <span className={`font-medium ${selectedGame.plusMinus >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {selectedGame.plusMinus > 0 ? '+' : ''}{selectedGame.plusMinus}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Efficiency:</span>
                    <span className="font-medium">{selectedGame.efficiency.toFixed(1)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Usage Rate:</span>
                    <span className="font-medium">{selectedGame.usageRate.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>OFF RTG:</span>
                    <span className="font-medium">{selectedGame.offensiveRating}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Clutch Rating:</span>
                    <div className="flex items-center gap-1">
                      <div className="flex">
                        {[...Array(10)].map((_, i) => (
                          <div
                            key={i}
                            className={`w-2 h-2 rounded-full mr-0.5 ${
                              i < selectedGame.clutchRating ? 'bg-yellow-400' : 'bg-gray-300'
                            }`}
                          />
                        ))}
                      </div>
                      <span className="text-xs">{selectedGame.clutchRating}/10</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Context indicators */}
            <div className="mt-4 flex flex-wrap gap-2">
              {selectedGame.isInjured && (
                <Badge variant="destructive" className="flex items-center gap-1">
                  <Heart className="w-3 h-3" />
                  {selectedGame.injuryType} injury
                </Badge>
              )}
              {selectedGame.isBackToBack && (
                <Badge variant="secondary">Back-to-back</Badge>
              )}
              {selectedGame.daysRest === 0 && (
                <Badge variant="outline">No rest</Badge>
              )}
              {selectedGame.gameImportance === 'critical' && (
                <Badge className="bg-yellow-500">
                  <Trophy className="w-3 h-3 mr-1" />
                  Critical game
                </Badge>
              )}
              {selectedGame.teamWinStreak > 3 && (
                <Badge className="bg-green-500">
                  <Zap className="w-3 h-3 mr-1" />
                  Win streak: {selectedGame.teamWinStreak}
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold">{visibleGames.filter(g => g.result === 'W').length}-{visibleGames.filter(g => g.result === 'L').length}</div>
            <div className="text-sm text-muted-foreground">Record</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold">
              {(visibleGames.reduce((sum, game) => sum + getMetricValue(game, metric), 0) / visibleGames.length).toFixed(1)}
            </div>
            <div className="text-sm text-muted-foreground">Avg {metric}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold">
              {visibleGames.filter(g => g.performanceGrade === 'A').length}
            </div>
            <div className="text-sm text-muted-foreground">A+ Games</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold">
              {visibleGames.filter(g => g.isInjured).length}
            </div>
            <div className="text-sm text-muted-foreground">Injury Games</div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
} 