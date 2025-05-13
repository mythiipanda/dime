"use client";

import React, { useRef, useEffect, useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { cn } from '@/lib/utils';
import { Play, Pause, RotateCcw, Filter } from 'lucide-react';

export interface Shot {
  x: number;
  y: number;
  made: boolean;
  value: number;
  shot_type?: string;
  shot_zone?: string;
  distance?: number;
  game_date?: string;
  period?: number;
}

export interface ZoneData {
  zone: string;
  attempts: number;
  made: number;
  percentage: number;
  leaguePercentage: number;
  relativePercentage: number;
}

interface ShotChartProps {
  playerName: string;
  shots: Shot[];
  zones: ZoneData[];
  className?: string;
}

// Shot types for filtering
const SHOT_TYPES = [
  'All Types',
  'Jump Shot',
  'Layup',
  'Dunk',
  'Hook Shot',
  'Fadeaway',
  'Step Back Jump Shot',
  'Driving Layup',
  'Pullup Jump Shot',
  'Running Layup',
  'Alley Oop Dunk'
];

// Shot zones for filtering
const SHOT_ZONES = [
  'All Zones',
  'Restricted Area',
  'In The Paint (Non-RA)',
  'Mid-Range',
  'Left Corner 3',
  'Right Corner 3',
  'Above the Break 3',
  'Backcourt'
];

export function ShotChart({ playerName, shots, zones, className }: ShotChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>(0);
  const [activeTab, setActiveTab] = useState<'chart' | 'zones'>('chart');
  const [animationProgress, setAnimationProgress] = useState(100);
  const [isAnimating, setIsAnimating] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  // Filters
  const [selectedShotType, setSelectedShotType] = useState('All Types');
  const [selectedZone, setSelectedZone] = useState('All Zones');
  const [minDistance, setMinDistance] = useState(0);
  const [maxDistance, setMaxDistance] = useState(40);
  const [showMadeShots, setShowMadeShots] = useState(true);
  const [showMissedShots, setShowMissedShots] = useState(true);
  const [showTwoPointers, setShowTwoPointers] = useState(true);
  const [showThreePointers, setShowThreePointers] = useState(true);
  const [useHeatmap, setUseHeatmap] = useState(false);

  // Calculate max distance for the slider
  const maxShotDistance = useMemo(() => {
    if (shots.length === 0) return 40;
    return Math.ceil(Math.max(...shots.filter(shot => shot.distance !== undefined)
      .map(shot => shot.distance as number)));
  }, [shots]);

  // Apply filters to shots
  const filteredShots = useMemo(() => {
    return shots.filter(shot => {
      // Filter by shot type
      if (selectedShotType !== 'All Types' && shot.shot_type !== selectedShotType) {
        return false;
      }

      // Filter by zone
      if (selectedZone !== 'All Zones' && !shot.shot_zone?.includes(selectedZone)) {
        return false;
      }

      // Filter by distance
      if (shot.distance !== undefined && (shot.distance < minDistance || shot.distance > maxDistance)) {
        return false;
      }

      // Filter by made/missed
      if (!showMadeShots && shot.made) {
        return false;
      }
      if (!showMissedShots && !shot.made) {
        return false;
      }

      // Filter by point value
      if (!showTwoPointers && shot.value === 2) {
        return false;
      }
      if (!showThreePointers && shot.value === 3) {
        return false;
      }

      return true;
    });
  }, [
    shots,
    selectedShotType,
    selectedZone,
    minDistance,
    maxDistance,
    showMadeShots,
    showMissedShots,
    showTwoPointers,
    showThreePointers
  ]);

  // Animation control functions
  const startAnimation = () => {
    if (isAnimating) return;
    setIsAnimating(true);
    setAnimationProgress(0);

    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
    }

    let startTime: number;
    const duration = 2000; // 2 seconds for full animation

    const animate = (timestamp: number) => {
      if (!startTime) startTime = timestamp;
      const elapsed = timestamp - startTime;
      const progress = Math.min(elapsed / duration * 100, 100);

      setAnimationProgress(progress);

      if (progress < 100) {
        animationRef.current = requestAnimationFrame(animate);
      } else {
        setIsAnimating(false);
      }
    };

    animationRef.current = requestAnimationFrame(animate);
  };

  const pauseAnimation = () => {
    if (!isAnimating) return;
    setIsAnimating(false);
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
    }
  };

  const resetAnimation = () => {
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
    }
    setIsAnimating(false);
    setAnimationProgress(100);
  };

  // Handle slider change
  const handleSliderChange = (value: number[]) => {
    setAnimationProgress(value[0]);
    pauseAnimation();
  };

  // Draw the shot chart
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas dimensions
    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Draw court
    drawCourt(ctx, width, height);

    // Calculate how many shots to show based on animation progress
    const shotsToShow = Math.ceil((filteredShots.length * animationProgress) / 100);
    const visibleShots = filteredShots.slice(0, shotsToShow);

    // Draw heatmap if enabled
    if (useHeatmap && visibleShots.length > 0) {
      drawHeatmap(ctx, visibleShots, width, height);
    }

    // Draw shots
    visibleShots.forEach(shot => {
      // Scale coordinates to fit canvas
      const x = (shot.x + 250) * (width / 500);
      const y = height - (shot.y * (height / 470));

      // Draw shot
      ctx.beginPath();

      // Different sizes based on distance for visual effect
      const radius = shot.distance
        ? Math.max(3, 7 - (shot.distance / 10))
        : 5;

      ctx.arc(x, y, radius, 0, 2 * Math.PI);

      if (!useHeatmap) {
        ctx.fillStyle = shot.made ? '#22c55e' : '#ef4444';
        ctx.fill();

        // Add glow effect for made shots
        if (shot.made) {
          ctx.shadowColor = '#22c55e';
          ctx.shadowBlur = 5;
          ctx.fill();
          ctx.shadowBlur = 0;
        }
      } else {
        // For heatmap mode, just draw outlines
        ctx.strokeStyle = shot.made ? '#ffffff' : '#cccccc';
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // Draw shot value if not in heatmap mode
      if (!useHeatmap) {
        ctx.font = '10px Arial';
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(shot.value.toString(), x, y);
      }
    });
  }, [filteredShots, animationProgress, useHeatmap]);

  // Function to draw basketball half court with improved visuals
  const drawCourt = (ctx: CanvasRenderingContext2D, width: number, height: number) => {
    // Clear canvas with court color
    const courtBgGradient = ctx.createLinearGradient(0, 0, 0, height);
    courtBgGradient.addColorStop(0, '#f1f5f9');
    courtBgGradient.addColorStop(1, '#e2e8f0');
    ctx.fillStyle = courtBgGradient;
    ctx.fillRect(0, 0, width, height);

    // Court outline with shadow for depth
    ctx.shadowColor = 'rgba(0, 0, 0, 0.1)';
    ctx.shadowBlur = 5;
    ctx.shadowOffsetX = 2;
    ctx.shadowOffsetY = 2;
    ctx.strokeStyle = '#94a3b8';
    ctx.lineWidth = 2;
    ctx.strokeRect(0, 0, width, height);
    ctx.shadowColor = 'transparent';

    const centerX = width / 2;

    // Three-point line with gradient
    const threePointRadius = width * 0.38;
    const threePointGradient = ctx.createLinearGradient(
      centerX - threePointRadius, 0,
      centerX + threePointRadius, 0
    );
    threePointGradient.addColorStop(0, '#3b82f6');
    threePointGradient.addColorStop(0.5, '#6366f1');
    threePointGradient.addColorStop(1, '#3b82f6');

    ctx.beginPath();
    ctx.arc(centerX, height, threePointRadius, Math.PI, 2 * Math.PI);
    ctx.strokeStyle = threePointGradient;
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // Corner three-point lines
    const cornerThreeWidth = width * 0.14;
    ctx.beginPath();
    // Left corner three
    ctx.moveTo(0, height - cornerThreeWidth);
    ctx.lineTo(cornerThreeWidth, height - cornerThreeWidth);
    // Right corner three
    ctx.moveTo(width, height - cornerThreeWidth);
    ctx.lineTo(width - cornerThreeWidth, height - cornerThreeWidth);
    ctx.strokeStyle = threePointGradient;
    ctx.stroke();

    // Free throw circle
    const ftCircleRadius = width * 0.12;
    ctx.beginPath();
    ctx.arc(centerX, height - height * 0.22, ftCircleRadius, 0, 2 * Math.PI);
    ctx.strokeStyle = '#94a3b8';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Free throw line
    ctx.beginPath();
    ctx.moveTo(centerX - width * 0.15, height - height * 0.22 - ftCircleRadius);
    ctx.lineTo(centerX + width * 0.15, height - height * 0.22 - ftCircleRadius);
    ctx.stroke();

    // Restricted area with gradient
    const restrictedAreaRadius = width * 0.06;
    const restrictedGradient = ctx.createLinearGradient(
      centerX - restrictedAreaRadius, height,
      centerX + restrictedAreaRadius, height
    );
    restrictedGradient.addColorStop(0, '#f43f5e');
    restrictedGradient.addColorStop(1, '#e11d48');

    ctx.beginPath();
    ctx.arc(centerX, height, restrictedAreaRadius, Math.PI, 2 * Math.PI);
    ctx.strokeStyle = restrictedGradient;
    ctx.lineWidth = 2;
    ctx.stroke();

    // Backboard
    const backboardWidth = width * 0.12;
    ctx.beginPath();
    ctx.moveTo(centerX - backboardWidth / 2, height - height * 0.05);
    ctx.lineTo(centerX + backboardWidth / 2, height - height * 0.05);
    ctx.strokeStyle = '#64748b';
    ctx.lineWidth = 3;
    ctx.stroke();

    // Hoop with gradient
    const hoopRadius = width * 0.02;
    const hoopGradient = ctx.createRadialGradient(
      centerX, height - height * 0.05 - hoopRadius, 0,
      centerX, height - height * 0.05 - hoopRadius, hoopRadius
    );
    hoopGradient.addColorStop(0, '#f97316');
    hoopGradient.addColorStop(1, '#ea580c');

    ctx.beginPath();
    ctx.arc(centerX, height - height * 0.05 - hoopRadius, hoopRadius, 0, 2 * Math.PI);
    ctx.strokeStyle = hoopGradient;
    ctx.lineWidth = 2;
    ctx.stroke();

    // Paint area with subtle gradient
    const paintWidth = width * 0.3;
    const paintHeight = height * 0.35;
    const paintGradient = ctx.createLinearGradient(
      centerX, height - paintHeight,
      centerX, height
    );
    paintGradient.addColorStop(0, '#94a3b8');
    paintGradient.addColorStop(1, '#64748b');

    ctx.strokeStyle = paintGradient;
    ctx.lineWidth = 2;
    ctx.strokeRect(centerX - paintWidth / 2, height - paintHeight, paintWidth, paintHeight);

    // Add court labels with shadow for better visibility
    ctx.font = 'bold 12px Arial';
    ctx.fillStyle = '#475569';
    ctx.textAlign = 'center';
    ctx.shadowColor = 'rgba(255, 255, 255, 0.7)';
    ctx.shadowBlur = 2;
    ctx.fillText('Restricted Area', centerX, height - height * 0.08);
    ctx.fillText('Paint', centerX, height - paintHeight / 2);
    ctx.fillText('Free Throw Line', centerX, height - height * 0.22 - ftCircleRadius - 5);
    ctx.fillText('Three-Point Line', centerX, height - threePointRadius - 5);
    ctx.shadowColor = 'transparent';
  };

  // Function to draw heatmap
  const drawHeatmap = (
    ctx: CanvasRenderingContext2D,
    shots: Shot[],
    width: number,
    height: number
  ) => {
    // Create a 2D grid for the heatmap
    const gridSize = 20; // Size of each grid cell in pixels
    const gridWidth = Math.ceil(width / gridSize);
    const gridHeight = Math.ceil(height / gridSize);
    const grid = Array(gridHeight).fill(0).map(() => Array(gridWidth).fill(0));

    // Count shots in each grid cell
    shots.forEach(shot => {
      const x = (shot.x + 250) * (width / 500);
      const y = height - (shot.y * (height / 470));

      const gridX = Math.floor(x / gridSize);
      const gridY = Math.floor(y / gridSize);

      if (gridX >= 0 && gridX < gridWidth && gridY >= 0 && gridY < gridHeight) {
        grid[gridY][gridX]++;
      }
    });

    // Find the maximum count for normalization
    let maxCount = 1;
    for (let y = 0; y < gridHeight; y++) {
      for (let x = 0; x < gridWidth; x++) {
        maxCount = Math.max(maxCount, grid[y][x]);
      }
    }

    // Draw the heatmap
    for (let y = 0; y < gridHeight; y++) {
      for (let x = 0; x < gridWidth; x++) {
        const count = grid[y][x];
        if (count > 0) {
          const intensity = Math.min(count / (maxCount * 0.7), 1); // Scale for better visualization

          // Create a gradient from blue (cold) to red (hot)
          let r, g, b;
          if (intensity < 0.5) {
            // Blue to purple
            r = Math.round(intensity * 2 * 255);
            g = 0;
            b = 255;
          } else {
            // Purple to red
            r = 255;
            g = 0;
            b = Math.round((1 - (intensity - 0.5) * 2) * 255);
          }

          ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${intensity * 0.7})`;
          ctx.fillRect(x * gridSize, y * gridSize, gridSize, gridSize);
        }
      }
    }
  };

  return (
    <div className={cn("space-y-4", className)}>
      <h2 className="text-2xl font-bold">{playerName} Shot Analysis</h2>

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as 'chart' | 'zones')}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="chart">Shot Chart</TabsTrigger>
          <TabsTrigger value="zones">Zone Analysis</TabsTrigger>
        </TabsList>

        <TabsContent value="chart" className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex justify-between items-center">
                <CardTitle>Shot Distribution</CardTitle>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowFilters(!showFilters)}
                    className="flex items-center gap-1"
                  >
                    <Filter className="h-4 w-4" />
                    Filters
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setUseHeatmap(!useHeatmap)}
                    className={cn(
                      "flex items-center gap-1",
                      useHeatmap ? "bg-blue-100 dark:bg-blue-900" : ""
                    )}
                  >
                    {useHeatmap ? "Normal View" : "Heatmap"}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {showFilters && (
                <div className="mb-4 p-4 border rounded-md bg-slate-50 dark:bg-slate-900">
                  <h3 className="text-sm font-medium mb-3">Filter Options</h3>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <div>
                      <Label htmlFor="shotType" className="text-xs">Shot Type</Label>
                      <Select
                        value={selectedShotType}
                        onValueChange={setSelectedShotType}
                      >
                        <SelectTrigger id="shotType">
                          <SelectValue placeholder="Select shot type" />
                        </SelectTrigger>
                        <SelectContent>
                          {SHOT_TYPES.map(type => (
                            <SelectItem key={type} value={type}>{type}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div>
                      <Label htmlFor="shotZone" className="text-xs">Shot Zone</Label>
                      <Select
                        value={selectedZone}
                        onValueChange={setSelectedZone}
                      >
                        <SelectTrigger id="shotZone">
                          <SelectValue placeholder="Select zone" />
                        </SelectTrigger>
                        <SelectContent>
                          {SHOT_ZONES.map(zone => (
                            <SelectItem key={zone} value={zone}>{zone}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="mb-4">
                    <Label className="text-xs mb-2 block">Shot Distance (feet)</Label>
                    <div className="px-2">
                      <Slider
                        defaultValue={[minDistance, maxDistance]}
                        min={0}
                        max={maxShotDistance}
                        step={1}
                        onValueChange={(values) => {
                          setMinDistance(values[0]);
                          setMaxDistance(values[1]);
                        }}
                        className="my-4"
                      />
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>{minDistance} ft</span>
                        <span>{maxDistance} ft</span>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="flex items-center space-x-2">
                      <Switch
                        id="made-shots"
                        checked={showMadeShots}
                        onCheckedChange={setShowMadeShots}
                      />
                      <Label htmlFor="made-shots" className="text-xs">Made Shots</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Switch
                        id="missed-shots"
                        checked={showMissedShots}
                        onCheckedChange={setShowMissedShots}
                      />
                      <Label htmlFor="missed-shots" className="text-xs">Missed Shots</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Switch
                        id="two-pointers"
                        checked={showTwoPointers}
                        onCheckedChange={setShowTwoPointers}
                      />
                      <Label htmlFor="two-pointers" className="text-xs">2-Pointers</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Switch
                        id="three-pointers"
                        checked={showThreePointers}
                        onCheckedChange={setShowThreePointers}
                      />
                      <Label htmlFor="three-pointers" className="text-xs">3-Pointers</Label>
                    </div>
                  </div>
                </div>
              )}

              <div className="flex justify-center">
                <canvas
                  ref={canvasRef}
                  width={500}
                  height={470}
                  className="border rounded-md"
                />
              </div>

              <div className="mt-4">
                <div className="flex justify-between items-center mb-2">
                  <div className="text-sm font-medium">Animation</div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={startAnimation}
                      disabled={isAnimating}
                    >
                      <Play className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={pauseAnimation}
                      disabled={!isAnimating}
                    >
                      <Pause className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={resetAnimation}
                    >
                      <RotateCcw className="h-4 w-4" />
                    </Button>
                  </div>
                </div>

                <Slider
                  value={[animationProgress]}
                  min={0}
                  max={100}
                  step={1}
                  onValueChange={handleSliderChange}
                  className="my-2"
                />

                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>0%</span>
                  <span>{animationProgress.toFixed(0)}%</span>
                  <span>100%</span>
                </div>
              </div>

              <div className="flex justify-center gap-4 mt-4">
                <div className="flex items-center">
                  <div className="w-4 h-4 rounded-full bg-green-500 mr-2"></div>
                  <span className="text-sm">Made Shot</span>
                </div>
                <div className="flex items-center">
                  <div className="w-4 h-4 rounded-full bg-red-500 mr-2"></div>
                  <span className="text-sm">Missed Shot</span>
                </div>
              </div>

              <div className="mt-4 text-sm text-muted-foreground">
                <p>Showing {filteredShots.length} of {shots.length} total shots</p>
                <p>Made: {filteredShots.filter(shot => shot.made).length} ({filteredShots.length > 0 ? ((filteredShots.filter(shot => shot.made).length / filteredShots.length) * 100).toFixed(1) : 0}%)</p>
                <p>3PT: {filteredShots.filter(shot => shot.value === 3).length} shots
                  ({filteredShots.filter(shot => shot.value === 3).length > 0 ?
                    ((filteredShots.filter(shot => shot.value === 3 && shot.made).length /
                      filteredShots.filter(shot => shot.value === 3).length) * 100).toFixed(1) : 0}%)
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="zones" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Shooting Zones</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Zone</TableHead>
                    <TableHead className="text-right">FGM</TableHead>
                    <TableHead className="text-right">FGA</TableHead>
                    <TableHead className="text-right">FG%</TableHead>
                    <TableHead className="text-right">League Avg</TableHead>
                    <TableHead className="text-right">Diff</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {zones.map((zone) => (
                    <TableRow key={zone.zone}>
                      <TableCell className="font-medium">{zone.zone}</TableCell>
                      <TableCell className="text-right">{zone.made}</TableCell>
                      <TableCell className="text-right">{zone.attempts}</TableCell>
                      <TableCell className="text-right">{(zone.percentage * 100).toFixed(1)}%</TableCell>
                      <TableCell className="text-right">{(zone.leaguePercentage * 100).toFixed(1)}%</TableCell>
                      <TableCell className={cn(
                        "text-right font-medium",
                        zone.relativePercentage > 0 ? "text-green-600" :
                        zone.relativePercentage < 0 ? "text-red-600" : ""
                      )}>
                        {zone.relativePercentage > 0 ? "+" : ""}
                        {(zone.relativePercentage * 100).toFixed(1)}%
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
