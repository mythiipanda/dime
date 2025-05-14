"use client";

import React, { useRef, useEffect, useState, useMemo } from 'react';
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Play, Pause, RotateCcw, Filter, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

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
  season?: string;
  seasonType?: string;
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

export function ShotChart({ playerName, shots, zones, className, season: initialSeason, seasonType: initialSeasonType }: ShotChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>(0);
  const [activeTab, setActiveTab] = useState<'chart' | 'zones'>('chart');
  const [animationProgress, setAnimationProgress] = useState(100);
  const [isAnimating, setIsAnimating] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [chartImage, setChartImage] = useState<string | null>(null);
  const [chartType, setChartType] = useState<'scatter' | 'heatmap' | 'hexbin' | 'animated' | 'frequency' | 'distance'>('scatter');
  const [season, setSeason] = useState<string | undefined>(initialSeason);
  const [seasonType, setSeasonType] = useState<string>(initialSeasonType || 'Regular Season');
  const [error, setError] = useState<string | null>(null);

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

  // Fetch advanced shot chart from backend
  const fetchAdvancedShotChart = async (chartType: string = 'scatter') => {
    if (!playerName) return;

    setIsLoading(true);
    setError(null);

    try {
      // Build query parameters
      const params = new URLSearchParams();
      if (season) params.append('season', season);
      if (seasonType) params.append('seasonType', seasonType);
      params.append('chartType', chartType);
      params.append('outputFormat', 'base64');

      // Fetch shot chart from the API
      const url = `/api/v1/analyze/player/${encodeURIComponent(playerName)}/advanced-shotchart?${params.toString()}`;
      const response = await fetch(url);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Failed to fetch advanced shot chart: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      // Set the chart image based on the chart type
      if (data.image_data) {
        setChartImage(data.image_data);
      } else if (data.animation_data) {
        setChartImage(data.animation_data);
      } else {
        throw new Error('No image data returned from the server');
      }

      setChartType(data.chart_type as any);
    } catch (error) {
      console.error('Error fetching advanced shot chart:', error);
      setError(error instanceof Error ? error.message : 'Failed to fetch advanced shot chart');
    } finally {
      setIsLoading(false);
    }
  };

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

  // Update state when props change
  useEffect(() => {
    if (initialSeason !== undefined) {
      setSeason(initialSeason);
    }
    if (initialSeasonType !== undefined) {
      setSeasonType(initialSeasonType);
    }
  }, [initialSeason, initialSeasonType]);

  // Fetch advanced shot chart on component mount or when relevant props change
  useEffect(() => {
    if (playerName) {
      fetchAdvancedShotChart(chartType);
    }
  }, [playerName, season, seasonType]);

  return (
    <div className={cn("space-y-4", className)}>
      <h2 className="text-2xl font-bold">{playerName} Shot Analysis</h2>

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as 'chart' | 'zones')}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="chart">Shot Chart</TabsTrigger>
          <TabsTrigger value="zones">Zone Analysis</TabsTrigger>
        </TabsList>

        <TabsContent value="chart" className="space-y-4">
          <div className="flex flex-wrap gap-2 justify-between items-center">
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => fetchAdvancedShotChart('scatter')}
                className={cn(chartType === 'scatter' ? 'bg-primary text-primary-foreground' : '')}
              >
                Scatter
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => fetchAdvancedShotChart('heatmap')}
                className={cn(chartType === 'heatmap' ? 'bg-primary text-primary-foreground' : '')}
              >
                Heatmap
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => fetchAdvancedShotChart('hexbin')}
                className={cn(chartType === 'hexbin' ? 'bg-primary text-primary-foreground' : '')}
              >
                Hexbin
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => fetchAdvancedShotChart('animated')}
                className={cn(chartType === 'animated' ? 'bg-primary text-primary-foreground' : '')}
              >
                Animated
              </Button>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className="h-4 w-4 mr-2" />
              Filters
            </Button>
          </div>

          {showFilters && (
            <Card>
              <CardContent className="pt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="shot-type">Shot Type</Label>
                  <Select value={selectedShotType} onValueChange={setSelectedShotType}>
                    <SelectTrigger id="shot-type">
                      <SelectValue placeholder="Select shot type" />
                    </SelectTrigger>
                    <SelectContent>
                      {SHOT_TYPES.map(type => (
                        <SelectItem key={type} value={type}>{type}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="shot-zone">Shot Zone</Label>
                  <Select value={selectedZone} onValueChange={setSelectedZone}>
                    <SelectTrigger id="shot-zone">
                      <SelectValue placeholder="Select shot zone" />
                    </SelectTrigger>
                    <SelectContent>
                      {SHOT_ZONES.map(zone => (
                        <SelectItem key={zone} value={zone}>{zone}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Shot Distance ({minDistance}ft - {maxDistance}ft)</Label>
                  <Slider
                    value={[minDistance, maxDistance]}
                    min={0}
                    max={maxShotDistance}
                    step={1}
                    onValueChange={(values) => {
                      setMinDistance(values[0]);
                      setMaxDistance(values[1]);
                    }}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="show-made">Show Made</Label>
                    <div className="flex items-center space-x-2">
                      <Switch
                        id="show-made"
                        checked={showMadeShots}
                        onCheckedChange={setShowMadeShots}
                      />
                      <Label htmlFor="show-made">Made Shots</Label>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="show-missed">Show Missed</Label>
                    <div className="flex items-center space-x-2">
                      <Switch
                        id="show-missed"
                        checked={showMissedShots}
                        onCheckedChange={setShowMissedShots}
                      />
                      <Label htmlFor="show-missed">Missed Shots</Label>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="show-2pt">Show 2PT</Label>
                    <div className="flex items-center space-x-2">
                      <Switch
                        id="show-2pt"
                        checked={showTwoPointers}
                        onCheckedChange={setShowTwoPointers}
                      />
                      <Label htmlFor="show-2pt">2-Point Shots</Label>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="show-3pt">Show 3PT</Label>
                    <div className="flex items-center space-x-2">
                      <Switch
                        id="show-3pt"
                        checked={showThreePointers}
                        onCheckedChange={setShowThreePointers}
                      />
                      <Label htmlFor="show-3pt">3-Point Shots</Label>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          <div className="relative border rounded-md bg-background">
            {isLoading ? (
              <div className="flex items-center justify-center h-[500px]">
                <div className="text-center">
                  <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2 text-primary" />
                  <p className="text-sm text-muted-foreground">Loading shot chart...</p>
                </div>
              </div>
            ) : error ? (
              <div className="flex items-center justify-center h-[500px]">
                <div className="text-center p-4">
                  <p className="text-sm text-red-500 mb-2">{error}</p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => fetchAdvancedShotChart(chartType)}
                  >
                    Retry
                  </Button>
                </div>
              </div>
            ) : chartImage ? (
              <div className="flex justify-center">
                <img
                  src={chartImage}
                  alt={`${playerName} Shot Chart`}
                  className="max-w-full h-auto"
                />
              </div>
            ) : (
              <div className="flex items-center justify-center h-[500px]">
                <p className="text-muted-foreground">No shot data available</p>
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="zones" className="space-y-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Zone</TableHead>
                <TableHead className="text-right">FGM</TableHead>
                <TableHead className="text-right">FGA</TableHead>
                <TableHead className="text-right">FG%</TableHead>
                <TableHead className="text-right">League FG%</TableHead>
                <TableHead className="text-right">+/-</TableHead>
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
                    "text-right",
                    zone.relativePercentage > 0 ? "text-green-600" :
                    zone.relativePercentage < 0 ? "text-red-600" : ""
                  )}>
                    {zone.relativePercentage > 0 ? '+' : ''}{(zone.relativePercentage * 100).toFixed(1)}%
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TabsContent>
      </Tabs>
    </div>
  );
}
