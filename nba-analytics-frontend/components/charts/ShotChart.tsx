"use client";

import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Target,
  Zap,
  TrendingUp,
  Activity,
  Filter,
  Play,
  Pause,
  RotateCcw
} from 'lucide-react';

interface ShotData {
  id: string;
  x: number; // Court coordinates (0-94 feet)
  y: number; // Court coordinates (0-50 feet)
  made: boolean;
  points: number; // 2 or 3
  quarter: number;
  timeRemaining: string;
  defender: string;
  shotType: string;
  distance: number;
  difficulty: 'Easy' | 'Medium' | 'Hard' | 'Contested';
}

interface Zone {
  id: string;
  name: string;
  path: string; // SVG path
  attempts: number;
  makes: number;
  percentage: number;
  expectedPoints: number;
  difficulty: number;
}

interface ShotChartProps {
  playerName: string;
  shots: ShotData[];
  zones?: Zone[];
  season?: string;
  seasonType?: string;
  gameRange?: [number, number];
}

// Mock shot data for demonstration
const mockShots: ShotData[] = [
  // Paint shots
  { id: '1', x: 25, y: 5, made: true, points: 2, quarter: 1, timeRemaining: '10:23', defender: 'Lopez', shotType: 'Layup', distance: 2, difficulty: 'Easy' },
  { id: '2', x: 25, y: 8, made: false, points: 2, quarter: 1, timeRemaining: '9:45', defender: 'Howard', shotType: 'Hook', distance: 4, difficulty: 'Medium' },
  { id: '3', x: 23, y: 6, made: true, points: 2, quarter: 2, timeRemaining: '8:12', defender: 'None', shotType: 'Dunk', distance: 1, difficulty: 'Easy' },

  // Mid-range shots
  { id: '4', x: 25, y: 15, made: true, points: 2, quarter: 1, timeRemaining: '7:30', defender: 'Smart', shotType: 'Pullup', distance: 12, difficulty: 'Medium' },
  { id: '5', x: 30, y: 18, made: false, points: 2, quarter: 2, timeRemaining: '6:45', defender: 'Brown', shotType: 'Fadeaway', distance: 16, difficulty: 'Hard' },
  { id: '6', x: 20, y: 17, made: true, points: 2, quarter: 3, timeRemaining: '11:22', defender: 'White', shotType: 'Turnaround', distance: 14, difficulty: 'Medium' },

  // 3-point shots
  { id: '7', x: 25, y: 23, made: true, points: 3, quarter: 1, timeRemaining: '5:15', defender: 'Holiday', shotType: '3PT', distance: 24, difficulty: 'Medium' },
  { id: '8', x: 35, y: 23, made: false, points: 3, quarter: 2, timeRemaining: '4:33', defender: 'Tatum', shotType: '3PT', distance: 26, difficulty: 'Contested' },
  { id: '9', x: 15, y: 23, made: true, points: 3, quarter: 3, timeRemaining: '3:44', defender: 'None', shotType: '3PT', distance: 25, difficulty: 'Easy' },
  { id: '10', x: 42, y: 20, made: false, points: 3, quarter: 4, timeRemaining: '2:18', defender: 'Horford', shotType: '3PT', distance: 28, difficulty: 'Hard' },

  // Corner 3s
  { id: '11', x: 47, y: 7, made: true, points: 3, quarter: 2, timeRemaining: '8:55', defender: 'None', shotType: 'Corner3', distance: 22, difficulty: 'Easy' },
  { id: '12', x: 3, y: 7, made: false, points: 3, quarter: 4, timeRemaining: '1:45', defender: 'Pritchard', shotType: 'Corner3', distance: 22, difficulty: 'Contested' },
];

// Shot zones for heat map analysis
const shotZones: Zone[] = [
  { id: 'paint', name: 'Paint', path: 'M 19 0 L 19 19 L 31 19 L 31 0 Z', attempts: 8, makes: 6, percentage: 75, expectedPoints: 1.5, difficulty: 2 },
  { id: 'midrange', name: 'Mid-Range', path: 'M 10 19 L 10 23 L 40 23 L 40 19 Z', attempts: 12, makes: 7, percentage: 58.3, expectedPoints: 1.17, difficulty: 6 },
  { id: 'arc3', name: '3PT Arc', path: 'M 3 23 L 47 23 L 47 25 L 3 25 Z', attempts: 15, makes: 6, percentage: 40, expectedPoints: 1.2, difficulty: 7 },
  { id: 'corner3', name: 'Corner 3', path: 'M 0 7 L 3 7 L 3 23 L 0 23 Z', attempts: 4, makes: 2, percentage: 50, expectedPoints: 1.5, difficulty: 5 },
];

function ShotChart({
  playerName = "Player",
  shots = mockShots,
  zones = shotZones,
  season = "2024-25",
  seasonType = "Regular Season"
}: ShotChartProps) {
  const [viewMode, setViewMode] = useState<'shots' | 'heatmap' | 'zones' | 'evolution'>('shots');
  const [filterQuarter, setFilterQuarter] = useState<string>('all');
  const [filterDifficulty, setFilterDifficulty] = useState<string>('all');
  const [showMakes, setShowMakes] = useState(true);
  const [showMisses, setShowMisses] = useState(true);
  const [showDefender, setShowDefender] = useState(false);
  const [timelinePosition, setTimelinePosition] = useState([100]);
  const [isAnimating, setIsAnimating] = useState(false);

  // Filter shots based on current filters
  const filteredShots = useMemo(() => {
    return shots.filter(shot => {
      if (filterQuarter !== 'all' && shot.quarter.toString() !== filterQuarter) return false;
      if (filterDifficulty !== 'all' && shot.difficulty.toLowerCase() !== filterDifficulty) return false;
      if (!showMakes && shot.made) return false;
      if (!showMisses && !shot.made) return false;
      return true;
    });
  }, [shots, filterQuarter, filterDifficulty, showMakes, showMisses]);

  // Calculate shooting stats
  const stats = useMemo(() => {
    const totalShots = filteredShots.length;
    const makes = filteredShots.filter(s => s.made).length;
    const threePointers = filteredShots.filter(s => s.points === 3);
    const threeMakes = threePointers.filter(s => s.made).length;
    const twoPointers = filteredShots.filter(s => s.points === 2);
    const twoMakes = twoPointers.filter(s => s.made).length;

    return {
      totalShots,
      makes,
      percentage: totalShots > 0 ? (makes / totalShots * 100).toFixed(1) : '0.0',
      threePointPercentage: threePointers.length > 0 ? (threeMakes / threePointers.length * 100).toFixed(1) : '0.0',
      twoPointPercentage: twoPointers.length > 0 ? (twoMakes / twoPointers.length * 100).toFixed(1) : '0.0',
      pointsScored: filteredShots.filter(s => s.made).reduce((sum, s) => sum + s.points, 0),
      effectiveFieldGoal: totalShots > 0 ? ((makes + 0.5 * threeMakes) / totalShots * 100).toFixed(1) : '0.0'
    };
  }, [filteredShots]);

  // Convert shot coordinates to SVG coordinates
  const getShotPosition = (shot: ShotData) => {
    // NBA court is 94 feet long, 50 feet wide
    // SVG viewBox is 0 0 50 25 (half court)
    const x = (shot.x / 94) * 50;
    const y = (shot.y / 50) * 25;
    return { x, y };
  };

  // Get heat map intensity for a zone
  const getHeatMapIntensity = (percentage: number) => {
    if (percentage >= 60) return 'rgba(34, 197, 94, 0.8)'; // Green
    if (percentage >= 45) return 'rgba(234, 179, 8, 0.8)'; // Yellow
    if (percentage >= 35) return 'rgba(249, 115, 22, 0.8)'; // Orange
    return 'rgba(239, 68, 68, 0.8)'; // Red
  };

  // Animate timeline
  const handlePlayAnimation = () => {
    if (isAnimating) {
      setIsAnimating(false);
      return;
    }

    setIsAnimating(true);
    let position = 0;
    const interval = setInterval(() => {
      position += 2;
      setTimelinePosition([position]);

      if (position >= 100) {
        setIsAnimating(false);
        clearInterval(interval);
      }
    }, 100);
  };

  return (
    <div className="space-y-6">
      {/* Header with stats */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Target className="w-5 h-5" />
                {playerName} Shot Chart
                <Badge variant="outline">{season}</Badge>
              </h3>
              <div className="flex items-center gap-4 mt-2 text-sm">
                <span><strong>{stats.makes}</strong>/{stats.totalShots} FG ({stats.percentage}%)</span>
                <span><strong>{stats.pointsScored}</strong> PTS</span>
                <span>eFG: <strong>{stats.effectiveFieldGoal}%</strong></span>
              </div>
            </div>

            {/* View Mode Selector */}
            <Select value={viewMode} onValueChange={(value: any) => setViewMode(value)}>
              <SelectTrigger className="w-[140px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="shots">Shot Plot</SelectItem>
                <SelectItem value="heatmap">Heat Map</SelectItem>
                <SelectItem value="zones">Zone Analysis</SelectItem>
                <SelectItem value="evolution">Evolution</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
      </Card>

      {/* Controls */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <Label className="text-sm font-medium">Quarter</Label>
            <Select value={filterQuarter} onValueChange={setFilterQuarter}>
              <SelectTrigger className="mt-2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Quarters</SelectItem>
                <SelectItem value="1">1st Quarter</SelectItem>
                <SelectItem value="2">2nd Quarter</SelectItem>
                <SelectItem value="3">3rd Quarter</SelectItem>
                <SelectItem value="4">4th Quarter</SelectItem>
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <Label className="text-sm font-medium">Shot Difficulty</Label>
            <Select value={filterDifficulty} onValueChange={setFilterDifficulty}>
              <SelectTrigger className="mt-2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Shots</SelectItem>
                <SelectItem value="easy">Easy</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="hard">Hard</SelectItem>
                <SelectItem value="contested">Contested</SelectItem>
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <Label className="text-sm">Show Makes</Label>
              <Switch checked={showMakes} onCheckedChange={setShowMakes} />
            </div>
            <div className="flex items-center justify-between">
              <Label className="text-sm">Show Misses</Label>
              <Switch checked={showMisses} onCheckedChange={setShowMisses} />
            </div>
            <div className="flex items-center justify-between">
              <Label className="text-sm">Defender Info</Label>
              <Switch checked={showDefender} onCheckedChange={setShowDefender} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <Label className="text-sm font-medium">Timeline</Label>
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handlePlayAnimation}
                  className="h-6 w-6 p-0"
                >
                  {isAnimating ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setTimelinePosition([0])}
                  className="h-6 w-6 p-0"
                >
                  <RotateCcw className="w-3 h-3" />
                </Button>
              </div>
            </div>
            <Slider
              value={timelinePosition}
              onValueChange={setTimelinePosition}
              max={100}
              step={1}
              className="mt-2"
            />
            <div className="text-xs text-muted-foreground mt-1">
              Game Progress: {timelinePosition[0]}%
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Shot Chart */}
      <Card>
        <CardContent className="p-6">
          <div className="relative">
            {/* Basketball Court SVG */}
            <svg
              viewBox="0 0 50 25"
              className="w-full h-96 border border-gray-300 rounded-lg bg-gradient-to-b from-orange-50 to-orange-100"
              style={{ aspectRatio: '2/1' }}
            >
              {/* Court markings */}
              <defs>
                <pattern id="courtLines" patternUnits="userSpaceOnUse" width="1" height="1">
                  <rect width="1" height="1" fill="none" stroke="#d1d5db" strokeWidth="0.05"/>
                </pattern>
              </defs>

              {/* Free throw lane */}
              <rect x="19" y="0" width="12" height="19" fill="none" stroke="#374151" strokeWidth="0.2"/>

              {/* Free throw circle */}
              <circle cx="25" cy="19" r="6" fill="none" stroke="#374151" strokeWidth="0.2"/>

              {/* 3-point arc */}
              <path
                d="M 3 23.75 A 22 22 0 0 0 47 23.75"
                fill="none"
                stroke="#374151"
                strokeWidth="0.2"
              />

              {/* Hoop */}
              <circle cx="25" cy="5" r="0.75" fill="#dc2626" stroke="#991b1b" strokeWidth="0.1"/>

              {/* Backboard */}
              <line x1="22" y1="4" x2="28" y2="4" stroke="#374151" strokeWidth="0.3"/>

              {/* Zone overlays for heat map */}
              {viewMode === 'heatmap' && zones.map(zone => (
                <path
                  key={zone.id}
                  d={zone.path}
                  fill={getHeatMapIntensity(zone.percentage)}
                  stroke="#374151"
                  strokeWidth="0.1"
                />
              ))}

              {/* Zone analysis overlay */}
              {viewMode === 'zones' && zones.map(zone => (
                <g key={zone.id}>
                  <path
                    d={zone.path}
                    fill="rgba(59, 130, 246, 0.1)"
                    stroke="#3b82f6"
                    strokeWidth="0.2"
                    strokeDasharray="0.5,0.3"
                  />
                  <text
                    x={zone.id === 'paint' ? 25 : zone.id === 'corner3' ? 1.5 : 25}
                    y={zone.id === 'paint' ? 10 : zone.id === 'corner3' ? 15 : 21}
                    textAnchor="middle"
                    className="text-xs fill-blue-700 font-medium"
                    fontSize="1.2"
                  >
                    {zone.percentage.toFixed(0)}%
                  </text>
                </g>
              ))}

              {/* Shot points */}
              {viewMode !== 'zones' && filteredShots.map(shot => {
                const pos = getShotPosition(shot);
                const radius = shot.points === 3 ? 0.4 : 0.3;
                const color = shot.made ? '#10b981' : '#ef4444';
                const opacity = viewMode === 'evolution' ?
                  (timelinePosition[0] / 100 >= (shot.quarter - 1) / 4 ? 1 : 0.2) : 1;

                return (
                  <g key={shot.id} opacity={opacity}>
                    <circle
                      cx={pos.x}
                      cy={pos.y}
                      r={radius}
                      fill={color}
                      stroke="#ffffff"
                      strokeWidth="0.1"
                      className="transition-all duration-300 hover:r-0.6"
                    />
                    {shot.made && (
                      <text
                        x={pos.x}
                        y={pos.y + 0.15}
                        textAnchor="middle"
                        className="text-white font-bold"
                        fontSize="0.4"
                      >
                        ✓
                      </text>
                    )}
                    {showDefender && shot.defender !== 'None' && (
                      <text
                        x={pos.x}
                        y={pos.y - 0.8}
                        textAnchor="middle"
                        className="fill-gray-600"
                        fontSize="0.3"
                      >
                        {shot.defender}
                      </text>
                    )}
                  </g>
                );
              })}
            </svg>

            {/* Legend */}
            <div className="absolute top-4 right-4 bg-white p-3 rounded-lg shadow-md border">
              <div className="space-y-2 text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                  <span>Made Shot</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <span>Missed Shot</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                  <span>3-Point Attempt</span>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Zone Statistics */}
      {viewMode === 'zones' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {zones.map(zone => (
            <Card key={zone.id}>
              <CardContent className="p-4">
                <div className="space-y-2">
                  <h4 className="font-semibold text-sm">{zone.name}</h4>
                  <div className="space-y-1 text-xs">
                    <div className="flex justify-between">
                      <span>FG%:</span>
                      <span className="font-medium">{zone.percentage.toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Attempts:</span>
                      <span className="font-medium">{zone.attempts}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Expected Pts:</span>
                      <span className="font-medium">{zone.expectedPoints.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Difficulty:</span>
                      <Badge variant={zone.difficulty > 6 ? 'destructive' : zone.difficulty > 4 ? 'secondary' : 'default'} className="text-xs">
                        {zone.difficulty > 6 ? 'Hard' : zone.difficulty > 4 ? 'Medium' : 'Easy'}
                      </Badge>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Detailed Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4">
            <h4 className="font-semibold mb-3 flex items-center gap-2">
              <TrendingUp className="w-4 h-4" />
              Shooting Efficiency
            </h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span>Field Goal %:</span>
                <span className="font-medium">{stats.percentage}%</span>
              </div>
              <div className="flex justify-between">
                <span>3-Point %:</span>
                <span className="font-medium">{stats.threePointPercentage}%</span>
              </div>
              <div className="flex justify-between">
                <span>2-Point %:</span>
                <span className="font-medium">{stats.twoPointPercentage}%</span>
              </div>
              <div className="flex justify-between">
                <span>eFG%:</span>
                <span className="font-medium">{stats.effectiveFieldGoal}%</span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <h4 className="font-semibold mb-3 flex items-center gap-2">
              <Activity className="w-4 h-4" />
              Shot Distribution
            </h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span>Paint Shots:</span>
                <span className="font-medium">{filteredShots.filter(s => s.distance <= 8).length}</span>
              </div>
              <div className="flex justify-between">
                <span>Mid-Range:</span>
                <span className="font-medium">{filteredShots.filter(s => s.distance > 8 && s.points === 2).length}</span>
              </div>
              <div className="flex justify-between">
                <span>3-Pointers:</span>
                <span className="font-medium">{filteredShots.filter(s => s.points === 3).length}</span>
              </div>
              <div className="flex justify-between">
                <span>Contested:</span>
                <span className="font-medium">{filteredShots.filter(s => s.difficulty === 'Contested').length}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <h4 className="font-semibold mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4" />
              Hot Zones
            </h4>
            <div className="space-y-2 text-sm">
              {zones
                .sort((a, b) => b.percentage - a.percentage)
                .slice(0, 3)
                .map((zone, index) => (
                  <div key={zone.id} className="flex justify-between">
                    <span>{zone.name}:</span>
                    <Badge
                      variant={index === 0 ? 'default' : 'secondary'}
                      className="text-xs"
                    >
                      {zone.percentage.toFixed(1)}%
                    </Badge>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default ShotChart;
export { ShotChart };
