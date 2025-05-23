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
import { 
  Play, 
  Pause, 
  RotateCcw, 
  SkipBack,
  SkipForward,
  Eye,
  Activity,
  Target,
  Users,
  Zap,
  TrendingUp,
  GitCompare,
  Map,
  Route
} from 'lucide-react';

interface PlayerPosition {
  id: string;
  name: string;
  number: number;
  team: 'home' | 'away';
  position: string; // PG, SG, SF, PF, C
  x: number; // Court coordinates (0-94 feet)
  y: number; // Court coordinates (0-50 feet)
  timestamp: number;
  hasReboundPosition?: boolean;
  isDefender?: boolean;
  role: 'primary' | 'secondary' | 'spot-up' | 'screener' | 'cutter';
}

interface PlayData {
  id: string;
  name: string;
  type: 'offense' | 'defense';
  quarter: number;
  timeRemaining: string;
  positions: PlayerPosition[][];
  ballPosition: { x: number; y: number }[];
  outcome: 'made' | 'missed' | 'turnover' | 'foul';
  points: number;
  keyEvents: {
    timestamp: number;
    event: string;
    player?: string;
    description: string;
  }[];
}

interface CourtProps {
  teamNames: { home: string; away: string };
  currentPlay?: PlayData;
  viewMode: '2d' | '3d' | 'heatmap' | 'spacing';
  showPlayerNames?: boolean;
  showMovementTrails?: boolean;
  showSpacingLines?: boolean;
}

// Mock play data for demonstration
const mockPlay: PlayData = {
  id: 'play-1',
  name: 'Lakers Ball Screen Action',
  type: 'offense',
  quarter: 2,
  timeRemaining: '8:23',
  outcome: 'made',
  points: 3,
  positions: [
    // Frame 1 - Initial setup
    [
      { id: 'lbj', name: 'LeBron James', number: 23, team: 'home', position: 'PG', x: 25, y: 35, timestamp: 0, role: 'primary' },
      { id: 'ad', name: 'Anthony Davis', number: 3, team: 'home', position: 'C', x: 28, y: 15, timestamp: 0, role: 'screener' },
      { id: 'ar', name: 'Austin Reaves', number: 15, team: 'home', position: 'SG', x: 45, y: 20, timestamp: 0, role: 'spot-up' },
      { id: 'rw', name: 'Rui Hachimura', number: 28, team: 'home', position: 'PF', x: 15, y: 12, timestamp: 0, role: 'spot-up' },
      { id: 'dr', name: 'D\'Angelo Russell', number: 1, team: 'home', position: 'SG', x: 5, y: 25, timestamp: 0, role: 'spot-up' },
      
      { id: 'jt', name: 'Jayson Tatum', number: 0, team: 'away', position: 'SF', x: 24, y: 32, timestamp: 0, isDefender: true, role: 'primary' },
      { id: 'jb', name: 'Jaylen Brown', number: 7, team: 'away', position: 'SG', x: 44, y: 18, timestamp: 0, isDefender: true, role: 'secondary' },
      { id: 'kp', name: 'Kristaps Porzingis', number: 8, team: 'away', position: 'C', x: 26, y: 8, timestamp: 0, isDefender: true, role: 'secondary' },
      { id: 'jh', name: 'Jrue Holiday', number: 4, team: 'away', position: 'PG', x: 6, y: 27, timestamp: 0, isDefender: true, role: 'secondary' },
      { id: 'aw', name: 'Al Horford', number: 42, team: 'away', position: 'PF', x: 16, y: 14, timestamp: 0, isDefender: true, role: 'secondary' },
    ],
    // Frame 2 - Screen set
    [
      { id: 'lbj', name: 'LeBron James', number: 23, team: 'home', position: 'PG', x: 28, y: 30, timestamp: 1, role: 'primary' },
      { id: 'ad', name: 'Anthony Davis', number: 3, team: 'home', position: 'C', x: 26, y: 18, timestamp: 1, role: 'screener' },
      { id: 'ar', name: 'Austin Reaves', number: 15, team: 'home', position: 'SG', x: 43, y: 18, timestamp: 1, role: 'spot-up' },
      { id: 'rw', name: 'Rui Hachimura', number: 28, team: 'home', position: 'PF', x: 12, y: 8, timestamp: 1, role: 'spot-up' },
      { id: 'dr', name: 'D\'Angelo Russell', number: 1, team: 'home', position: 'SG', x: 8, y: 23, timestamp: 1, role: 'spot-up' },
      
      { id: 'jt', name: 'Jayson Tatum', number: 0, team: 'away', position: 'SF', x: 30, y: 28, timestamp: 1, isDefender: true, role: 'primary' },
      { id: 'jb', name: 'Jaylen Brown', number: 7, team: 'away', position: 'SG', x: 42, y: 16, timestamp: 1, isDefender: true, role: 'secondary' },
      { id: 'kp', name: 'Kristaps Porzingis', number: 8, team: 'away', position: 'C', x: 24, y: 6, timestamp: 1, isDefender: true, role: 'secondary' },
      { id: 'jh', name: 'Jrue Holiday', number: 4, team: 'away', position: 'PG', x: 9, y: 25, timestamp: 1, isDefender: true, role: 'secondary' },
      { id: 'aw', name: 'Al Horford', number: 42, team: 'away', position: 'PF', x: 14, y: 12, timestamp: 1, isDefender: true, role: 'secondary' },
    ],
    // Frame 3 - Shot attempt
    [
      { id: 'lbj', name: 'LeBron James', number: 23, team: 'home', position: 'PG', x: 25, y: 23, timestamp: 2, role: 'primary' },
      { id: 'ad', name: 'Anthony Davis', number: 3, team: 'home', position: 'C', x: 22, y: 12, timestamp: 2, role: 'screener' },
      { id: 'ar', name: 'Austin Reaves', number: 15, team: 'home', position: 'SG', x: 40, y: 15, timestamp: 2, role: 'spot-up' },
      { id: 'rw', name: 'Rui Hachimura', number: 28, team: 'home', position: 'PF', x: 10, y: 5, timestamp: 2, role: 'spot-up' },
      { id: 'dr', name: 'D\'Angelo Russell', number: 1, team: 'home', position: 'SG', x: 12, y: 20, timestamp: 2, role: 'spot-up' },
      
      { id: 'jt', name: 'Jayson Tatum', number: 0, team: 'away', position: 'SF', x: 27, y: 25, timestamp: 2, isDefender: true, role: 'primary' },
      { id: 'jb', name: 'Jaylen Brown', number: 7, team: 'away', position: 'SG', x: 39, y: 13, timestamp: 2, isDefender: true, role: 'secondary' },
      { id: 'kp', name: 'Kristaps Porzingis', number: 8, team: 'away', position: 'C', x: 20, y: 4, timestamp: 2, isDefender: true, role: 'secondary' },
      { id: 'jh', name: 'Jrue Holiday', number: 4, team: 'away', position: 'PG', x: 13, y: 22, timestamp: 2, isDefender: true, role: 'secondary' },
      { id: 'aw', name: 'Al Horford', number: 42, team: 'away', position: 'PF', x: 11, y: 9, timestamp: 2, isDefender: true, role: 'secondary' },
    ],
  ],
  ballPosition: [
    { x: 25, y: 35 }, // Initial position with LeBron
    { x: 28, y: 30 }, // After screen
    { x: 25, y: 23 }, // Shot position
  ],
  keyEvents: [
    { timestamp: 0, event: 'play_start', description: 'LeBron brings ball up court' },
    { timestamp: 1, event: 'screen_set', player: 'Anthony Davis', description: 'Davis sets ball screen' },
    { timestamp: 2, event: 'shot_attempt', player: 'LeBron James', description: 'LeBron pulls up for 3' },
  ]
};

export default function InteractiveCourt({   teamNames = { home: 'Lakers', away: 'Celtics' },  currentPlay = mockPlay,  viewMode = '2d',  showPlayerNames: showPlayerNamesProp = true,  showMovementTrails: showMovementTrailsProp = true,  showSpacingLines: showSpacingLinesProp = false}: CourtProps) {  const [playFrame, setPlayFrame] = useState(0);  const [isPlaying, setIsPlaying] = useState(false);  const [playSpeed, setPlaySpeed] = useState([1]);  const [selectedPlayer, setSelectedPlayer] = useState<string | null>(null);  const [analysisMode, setAnalysisMode] = useState<'movement' | 'spacing' | 'roles' | 'coverage'>('movement');  const [show3D, setShow3D] = useState(false);  const [courtAngle, setCourtAngle] = useState([0]);  const [showPlayerNames, setShowPlayerNames] = useState(showPlayerNamesProp);  const [showMovementTrails, setShowMovementTrails] = useState(showMovementTrailsProp);  const [showSpacingLines, setShowSpacingLines] = useState(showSpacingLinesProp);  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Auto-play functionality
  useEffect(() => {
    if (isPlaying && playFrame < currentPlay.positions.length - 1) {
      intervalRef.current = setInterval(() => {
        setPlayFrame(prev => {
          if (prev >= currentPlay.positions.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 1000 / playSpeed[0]);
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isPlaying, playFrame, playSpeed, currentPlay.positions.length]);

  // Get current frame data
  const currentPositions = currentPlay.positions[playFrame] || [];
  const currentBallPosition = currentPlay.ballPosition[playFrame] || { x: 25, y: 25 };

  // Convert coordinates to SVG
  const coordsToSVG = (x: number, y: number) => {
    return {
      x: (x / 94) * 50,
      y: (y / 50) * 25
    };
  };

  // Get player by team
  const homePlayers = currentPositions.filter(p => p.team === 'home');
  const awayPlayers = currentPositions.filter(p => p.team === 'away');

  // Calculate spacing metrics
  const spacingMetrics = useMemo(() => {
    const homePositions = homePlayers.map(p => ({ x: p.x, y: p.y }));
    const awayPositions = awayPlayers.map(p => ({ x: p.x, y: p.y }));
    
    // Calculate average distance between players
    const avgHomeSpacing = homePositions.length > 1 ? 
      homePositions.reduce((sum, pos1, i) => {
        const distances = homePositions.slice(i + 1).map(pos2 => 
          Math.sqrt(Math.pow(pos1.x - pos2.x, 2) + Math.pow(pos1.y - pos2.y, 2))
        );
        return sum + distances.reduce((a, b) => a + b, 0);
      }, 0) / (homePositions.length * (homePositions.length - 1) / 2) : 0;

    // Calculate court coverage
    const homeXSpread = Math.max(...homePositions.map(p => p.x)) - Math.min(...homePositions.map(p => p.x));
    const homeYSpread = Math.max(...homePositions.map(p => p.y)) - Math.min(...homePositions.map(p => p.y));
    
    return {
      avgSpacing: avgHomeSpacing.toFixed(1),
      courtCoverage: ((homeXSpread * homeYSpread) / (94 * 50) * 100).toFixed(1),
      xSpread: homeXSpread.toFixed(1),
      ySpread: homeYSpread.toFixed(1)
    };
  }, [homePlayers, awayPlayers]);

  // Get player role color
  const getRoleColor = (role: string, team: string) => {
    const baseColors = team === 'home' ? 
      { primary: '#7c3aed', secondary: '#a855f7', spotUp: '#c084fc', screener: '#e879f9', cutter: '#f0abfc' } :
      { primary: '#dc2626', secondary: '#ef4444', spotUp: '#f87171', screener: '#fca5a5', cutter: '#fecaca' };
    
    switch (role) {
      case 'primary': return baseColors.primary;
      case 'secondary': return baseColors.secondary;
      case 'spot-up': return baseColors.spotUp;
      case 'screener': return baseColors.screener;
      case 'cutter': return baseColors.cutter;
      default: return '#6b7280';
    }
  };

  const handlePlayPause = () => {
    setIsPlaying(!isPlaying);
  };

  const handleReset = () => {
    setIsPlaying(false);
    setPlayFrame(0);
  };

  const handleFrameChange = (frame: number) => {
    setPlayFrame(frame);
    setIsPlaying(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Activity className="w-5 h-5" />
                Interactive Court Analysis
                <Badge variant="outline">{currentPlay.name}</Badge>
              </h3>
              <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                <span>{teamNames.home} vs {teamNames.away}</span>
                <span>Q{currentPlay.quarter} • {currentPlay.timeRemaining}</span>
                <Badge variant={currentPlay.outcome === 'made' ? 'default' : 'destructive'}>
                  {currentPlay.outcome} • {currentPlay.points} pts
                </Badge>
              </div>
            </div>
            
            <Tabs value={analysisMode} onValueChange={(value: any) => setAnalysisMode(value)}>
              <TabsList>
                <TabsTrigger value="movement">Movement</TabsTrigger>
                <TabsTrigger value="spacing">Spacing</TabsTrigger>
                <TabsTrigger value="roles">Roles</TabsTrigger>
                <TabsTrigger value="coverage">Coverage</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </CardHeader>
      </Card>

      {/* Controls */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <Label className="text-sm font-medium">Playback Controls</Label>
            <div className="flex items-center gap-2 mt-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleFrameChange(Math.max(0, playFrame - 1))}
                disabled={playFrame === 0}
              >
                <SkipBack className="w-4 h-4" />
              </Button>
              <Button
                size="sm"
                onClick={handlePlayPause}
                className="flex-1"
              >
                {isPlaying ? <Pause className="w-4 h-4 mr-2" /> : <Play className="w-4 h-4 mr-2" />}
                {isPlaying ? 'Pause' : 'Play'}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleFrameChange(Math.min(currentPlay.positions.length - 1, playFrame + 1))}
                disabled={playFrame === currentPlay.positions.length - 1}
              >
                <SkipForward className="w-4 h-4" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={handleReset}
              >
                <RotateCcw className="w-4 h-4" />
              </Button>
            </div>
            <div className="mt-3">
              <Label className="text-xs">Speed: {playSpeed[0]}x</Label>
              <Slider
                value={playSpeed}
                onValueChange={setPlaySpeed}
                min={0.5}
                max={3}
                step={0.5}
                className="mt-1"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <Label className="text-sm font-medium">Frame Control</Label>
            <div className="mt-2">
              <Slider
                value={[playFrame]}
                onValueChange={(value) => handleFrameChange(value[0])}
                min={0}
                max={currentPlay.positions.length - 1}
                step={1}
                className="mt-1"
              />
              <div className="text-xs text-muted-foreground mt-1">
                Frame {playFrame + 1} of {currentPlay.positions.length}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <Label className="text-sm">Player Names</Label>
              <Switch checked={showPlayerNames} onCheckedChange={setShowPlayerNames} />
            </div>
            <div className="flex items-center justify-between">
              <Label className="text-sm">Movement Trails</Label>
              <Switch checked={showMovementTrails} onCheckedChange={setShowMovementTrails} />
            </div>
            <div className="flex items-center justify-between">
              <Label className="text-sm">Spacing Lines</Label>
              <Switch checked={showSpacingLines} onCheckedChange={setShowSpacingLines} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <Label className="text-sm font-medium">View Options</Label>
            <div className="space-y-2 mt-2">
              <div className="flex items-center justify-between">
                <Label className="text-sm">3D Mode</Label>
                <Switch checked={show3D} onCheckedChange={setShow3D} />
              </div>
              {show3D && (
                <div>
                  <Label className="text-xs">Court Angle</Label>
                  <Slider
                    value={courtAngle}
                    onValueChange={setCourtAngle}
                    min={-45}
                    max={45}
                    step={5}
                    className="mt-1"
                  />
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Court Visualization */}
      <Card>
        <CardContent className="p-6">
          <div className="relative">
            <svg 
              viewBox="0 0 50 25" 
              className={`w-full border border-gray-300 rounded-lg bg-gradient-to-b from-orange-50 to-orange-100 transition-all duration-500 ${
                show3D ? 'transform perspective-1000' : ''
              }`}
              style={{ 
                aspectRatio: '2/1',
                height: '500px',
                transform: show3D ? `rotateX(${courtAngle[0]}deg)` : 'none',
                transformStyle: 'preserve-3d'
              }}
            >
              {/* Court Base */}
              <defs>
                <filter id="shadow" x="-50%" y="-50%" width="200%" height="200%">
                  <feDropShadow dx="0.1" dy="0.1" stdDeviation="0.2" floodColor="#000000" floodOpacity="0.3"/>
                </filter>
                <radialGradient id="courtGradient" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" style={{ stopColor: '#fef3c7', stopOpacity: 1 }} />
                  <stop offset="100%" style={{ stopColor: '#f59e0b', stopOpacity: 0.3 }} />
                </radialGradient>
              </defs>
              
              {/* Court fill */}
              <rect x="0" y="0" width="50" height="25" fill="url(#courtGradient)" />
              
              {/* Court markings */}
              <rect x="19" y="0" width="12" height="19" fill="none" stroke="#374151" strokeWidth="0.2"/>
              <circle cx="25" cy="19" r="6" fill="none" stroke="#374151" strokeWidth="0.2"/>
              <path d="M 3 23.75 A 22 22 0 0 0 47 23.75" fill="none" stroke="#374151" strokeWidth="0.2"/>
              <circle cx="25" cy="5" r="0.75" fill="#dc2626" stroke="#991b1b" strokeWidth="0.1"/>
              <line x1="22" y1="4" x2="28" y2="4" stroke="#374151" strokeWidth="0.3"/>

              {/* Spacing analysis lines */}
              {showSpacingLines && analysisMode === 'spacing' && (
                <g opacity="0.6">
                  {homePlayers.map((player1, i) =>
                    homePlayers.slice(i + 1).map((player2, j) => {
                      const pos1 = coordsToSVG(player1.x, player1.y);
                      const pos2 = coordsToSVG(player2.x, player2.y);
                      const distance = Math.sqrt(Math.pow(player1.x - player2.x, 2) + Math.pow(player1.y - player2.y, 2));
                      const color = distance > 15 ? '#10b981' : distance > 10 ? '#f59e0b' : '#ef4444';
                      
                      return (
                        <line
                          key={`spacing-${i}-${j}`}
                          x1={pos1.x}
                          y1={pos1.y}
                          x2={pos2.x}
                          y2={pos2.y}
                          stroke={color}
                          strokeWidth="0.1"
                          strokeDasharray="0.3,0.2"
                        />
                      );
                    })
                  )}
                </g>
              )}

              {/* Movement trails */}
              {showMovementTrails && playFrame > 0 && (
                <g opacity="0.4">
                  {currentPositions.map(player => {
                    const previousFrame = currentPlay.positions[playFrame - 1];
                    const prevPlayer = previousFrame?.find(p => p.id === player.id);
                    if (!prevPlayer) return null;
                    
                    const currentPos = coordsToSVG(player.x, player.y);
                    const prevPos = coordsToSVG(prevPlayer.x, prevPlayer.y);
                    
                    return (
                      <line
                        key={`trail-${player.id}`}
                        x1={prevPos.x}
                        y1={prevPos.y}
                        x2={currentPos.x}
                        y2={currentPos.y}
                        stroke={player.team === 'home' ? '#7c3aed' : '#dc2626'}
                        strokeWidth="0.2"
                        markerEnd="url(#arrowhead)"
                      />
                    );
                  })}
                </g>
              )}

              {/* Arrow marker for trails */}
              <defs>
                <marker id="arrowhead" markerWidth="2" markerHeight="2" refX="1.5" refY="1" orient="auto">
                  <polygon points="0 0, 2 1, 0 2" fill="#6b7280" />
                </marker>
              </defs>

              {/* Ball */}
              <circle
                cx={coordsToSVG(currentBallPosition.x, currentBallPosition.y).x}
                cy={coordsToSVG(currentBallPosition.x, currentBallPosition.y).y}
                r="0.3"
                fill="#f97316"
                stroke="#ea580c"
                strokeWidth="0.05"
                filter="url(#shadow)"
              />

              {/* Players */}
              {currentPositions.map(player => {
                const pos = coordsToSVG(player.x, player.y);
                const isSelected = selectedPlayer === player.id;
                const teamColor = player.team === 'home' ? '#7c3aed' : '#dc2626';
                const roleColor = analysisMode === 'roles' ? getRoleColor(player.role, player.team) : teamColor;
                
                return (
                  <g key={player.id}>
                    {/* Player circle */}
                    <circle
                      cx={pos.x}
                      cy={pos.y}
                      r={isSelected ? "0.8" : "0.6"}
                      fill={roleColor}
                      stroke="#ffffff"
                      strokeWidth="0.1"
                      filter="url(#shadow)"
                      className="cursor-pointer transition-all duration-200 hover:r-0.7"
                      onClick={() => setSelectedPlayer(isSelected ? null : player.id)}
                    />
                    
                    {/* Player number */}
                    <text
                      x={pos.x}
                      y={pos.y + 0.2}
                      textAnchor="middle"
                      className="text-white font-bold pointer-events-none"
                      fontSize="0.4"
                    >
                      {player.number}
                    </text>
                    
                    {/* Player name */}
                    {showPlayerNames && (
                      <text
                        x={pos.x}
                        y={pos.y - 1}
                        textAnchor="middle"
                        className="fill-gray-700 font-medium pointer-events-none"
                        fontSize="0.3"
                      >
                        {player.name.split(' ').pop()}
                      </text>
                    )}
                    
                    {/* Role indicator */}
                    {analysisMode === 'roles' && (
                      <text
                        x={pos.x}
                        y={pos.y + 1.2}
                        textAnchor="middle"
                        className="fill-gray-600 font-medium pointer-events-none"
                        fontSize="0.25"
                      >
                        {player.role}
                      </text>
                    )}
                    
                    {/* Coverage indicator for defenders */}
                    {analysisMode === 'coverage' && player.isDefender && (
                      <circle
                        cx={pos.x}
                        cy={pos.y}
                        r="1.5"
                        fill="none"
                        stroke={roleColor}
                        strokeWidth="0.05"
                        strokeDasharray="0.2,0.1"
                        opacity="0.5"
                      />
                    )}
                  </g>
                );
              })}
            </svg>

            {/* Play Event Timeline */}
            <div className="absolute bottom-4 left-4 right-4 bg-white/90 backdrop-blur-sm rounded-lg p-3">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">
                  {currentPlay.keyEvents[playFrame]?.description || 'Play in progress...'}
                </span>
                <div className="flex items-center gap-2">
                  {currentPlay.keyEvents.map((event, index) => (
                    <div
                      key={index}
                      className={`w-2 h-2 rounded-full transition-all duration-200 ${
                        index <= playFrame ? 'bg-blue-500' : 'bg-gray-300'
                      }`}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Analysis Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <h4 className="font-semibold flex items-center gap-2">
              <Map className="w-4 h-4" />
              Spacing Analysis
            </h4>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span>Average Spacing:</span>
                <Badge variant="outline">{spacingMetrics.avgSpacing} ft</Badge>
              </div>
              <div className="flex justify-between">
                <span>Court Coverage:</span>
                <Badge variant="outline">{spacingMetrics.courtCoverage}%</Badge>
              </div>
              <div className="flex justify-between">
                <span>Width Spread:</span>
                <Badge variant="outline">{spacingMetrics.xSpread} ft</Badge>
              </div>
              <div className="flex justify-between">
                <span>Length Spread:</span>
                <Badge variant="outline">{spacingMetrics.ySpread} ft</Badge>
              </div>
              <div className="mt-4 p-2 bg-blue-50 rounded text-xs">
                <strong>Analysis:</strong> {
                  Number(spacingMetrics.avgSpacing) > 15 ? 'Excellent spacing creates driving lanes' :
                  Number(spacingMetrics.avgSpacing) > 12 ? 'Good spacing with some congestion' :
                  'Spacing too tight, limited driving opportunities'
                }
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h4 className="font-semibold flex items-center gap-2">
              <Users className="w-4 h-4" />
              Player Roles
            </h4>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {['primary', 'screener', 'spot-up', 'secondary', 'cutter'].map(role => {
                const playersInRole = currentPositions.filter(p => p.role === role && p.team === 'home');
                if (playersInRole.length === 0) return null;
                
                return (
                  <div key={role} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div 
                        className="w-3 h-3 rounded-full" 
                        style={{ backgroundColor: getRoleColor(role, 'home') }}
                      />
                      <span className="capitalize">{role.replace('-', ' ')}</span>
                    </div>
                    <span className="text-muted-foreground">
                      {playersInRole.map(p => p.name.split(' ').pop()).join(', ')}
                    </span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h4 className="font-semibold flex items-center gap-2">
              <Route className="w-4 h-4" />
              Movement Insights
            </h4>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span>Ball Movement:</span>
                <Badge variant="outline">
                  {playFrame > 0 ? 'Active' : 'Static'}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span>Screen Actions:</span>
                <Badge variant="outline">
                  {currentPositions.filter(p => p.role === 'screener').length}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span>Cutting Players:</span>
                <Badge variant="outline">
                  {currentPositions.filter(p => p.role === 'cutter').length}
                </Badge>
              </div>
              <div className="mt-4 p-2 bg-green-50 rounded text-xs">
                <strong>Key Action:</strong> {
                  currentPlay.keyEvents[playFrame]?.event === 'screen_set' ? 'Ball screen creates switching advantage' :
                  currentPlay.keyEvents[playFrame]?.event === 'shot_attempt' ? 'Clean look generated by movement' :
                  'Setting up offensive action'
                }
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Selected Player Details */}
      {selectedPlayer && (
        <Card>
          <CardContent className="p-4">
            {(() => {
              const player = currentPositions.find(p => p.id === selectedPlayer);
              if (!player) return null;
              
              return (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div 
                      className="w-12 h-12 rounded-full flex items-center justify-center text-white font-bold"
                      style={{ backgroundColor: player.team === 'home' ? '#7c3aed' : '#dc2626' }}
                    >
                      {player.number}
                    </div>
                    <div>
                      <h4 className="font-semibold">{player.name}</h4>
                      <p className="text-sm text-muted-foreground">
                        {player.position} • {teamNames[player.team]} • Role: {player.role}
                      </p>
                    </div>
                  </div>
                  <div className="text-right text-sm">
                    <div>Position: ({player.x.toFixed(1)}, {player.y.toFixed(1)})</div>
                    <div className="text-muted-foreground">
                      {player.isDefender ? 'Defending' : 'Offensive action'}
                    </div>
                  </div>
                </div>
              );
            })()}
          </CardContent>
        </Card>
      )}
    </div>
  );
} 