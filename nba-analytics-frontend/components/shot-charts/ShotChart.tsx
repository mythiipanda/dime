"use client";

import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { RefreshCw, Target, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface ShotChartProps {
  playerName: string;
  season?: string;
}

interface Shot {
  x: number;
  y: number;
  made: boolean;
  value: number;
  shot_type: string;
  shot_zone: string;
  distance: number;
  game_date: string;
  period: number;
}

interface ShotZone {
  zone: string;
  attempts: number;
  made: number;
  percentage: number;
  leaguePercentage: number;
  relativePercentage: number;
}

interface ShotData {
  shots: Shot[];
  zones: ShotZone[];
}

export function ShotChart({ playerName, season = "2024-25" }: ShotChartProps) {
  const [shotData, setShotData] = useState<ShotData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedZone, setSelectedZone] = useState<string>("all");
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    fetchShotData();
  }, [playerName, season]);

  useEffect(() => {
    if (shotData && canvasRef.current) {
      drawShotChart();
    }
  }, [shotData, selectedZone]);

  const fetchShotData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`/api/v1/analyze/player/${encodeURIComponent(playerName)}/shots?season=${season}`);
      if (!response.ok) {
        throw new Error('Failed to fetch shot data');
      }
      
      const data = await response.json();
      setShotData(data);
    } catch (err) {
      console.error('Error fetching shot data:', err);
      setError('Failed to load shot chart data');
    } finally {
      setLoading(false);
    }
  };

  const drawShotChart = () => {
    const canvas = canvasRef.current;
    if (!canvas || !shotData) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    canvas.width = 500;
    canvas.height = 470;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw basketball court
    drawCourt(ctx);

    // Filter shots by zone if selected
    const filteredShots = selectedZone === "all" 
      ? shotData.shots 
      : shotData.shots.filter(shot => shot.shot_zone.toLowerCase().includes(selectedZone.toLowerCase()));

    // Draw shots
    filteredShots.forEach(shot => {
      drawShot(ctx, shot);
    });
  };

  const drawCourt = (ctx: CanvasRenderingContext2D) => {
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 2;

    // Court dimensions (scaled to fit canvas)
    const courtWidth = 500;
    const courtHeight = 470;
    const centerX = courtWidth / 2;

    // Baseline
    ctx.beginPath();
    ctx.moveTo(0, courtHeight);
    ctx.lineTo(courtWidth, courtHeight);
    ctx.stroke();

    // Free throw lane
    ctx.beginPath();
    ctx.rect(centerX - 80, courtHeight - 190, 160, 190);
    ctx.stroke();

    // Free throw circle
    ctx.beginPath();
    ctx.arc(centerX, courtHeight - 190, 60, 0, Math.PI);
    ctx.stroke();

    // Basket
    ctx.beginPath();
    ctx.arc(centerX, courtHeight - 41.75, 7.5, 0, 2 * Math.PI);
    ctx.stroke();

    // Restricted area
    ctx.beginPath();
    ctx.arc(centerX, courtHeight - 41.75, 40, 0, Math.PI);
    ctx.stroke();

    // 3-point line
    ctx.beginPath();
    ctx.arc(centerX, courtHeight - 41.75, 238, 0.244, Math.PI - 0.244);
    ctx.stroke();

    // 3-point corners
    ctx.beginPath();
    ctx.moveTo(centerX - 220, courtHeight);
    ctx.lineTo(centerX - 220, courtHeight - 140);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(centerX + 220, courtHeight);
    ctx.lineTo(centerX + 220, courtHeight - 140);
    ctx.stroke();
  };

  const drawShot = (ctx: CanvasRenderingContext2D, shot: Shot) => {
    // Convert NBA coordinates to canvas coordinates
    const canvasX = 250 + (shot.x * 0.5); // Scale and center
    const canvasY = 470 - (shot.y * 0.5 + 41.75); // Flip Y and adjust for basket position

    // Draw shot
    ctx.beginPath();
    ctx.arc(canvasX, canvasY, 3, 0, 2 * Math.PI);
    
    if (shot.made) {
      ctx.fillStyle = shot.value === 3 ? '#22c55e' : '#16a34a'; // Green for makes
    } else {
      ctx.fillStyle = shot.value === 3 ? '#ef4444' : '#dc2626'; // Red for misses
    }
    
    ctx.fill();
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 0.5;
    ctx.stroke();
  };

  const getZoneStats = (zone: string) => {
    return shotData?.zones.find(z => z.zone === zone);
  };

  const formatPercentage = (value: number) => {
    return (value * 100).toFixed(1) + '%';
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-10 w-32" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-96 w-full" />
          <div className="space-y-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <div className="text-center">
            <Target className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-muted-foreground">{error}</p>
            <Button onClick={fetchShotData} variant="outline" className="mt-4">
              <RefreshCw className="w-4 h-4 mr-2" />
              Try Again
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Shot Chart</h1>
          <p className="text-muted-foreground">{playerName} • {season} Season</p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={selectedZone} onValueChange={setSelectedZone}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Filter by zone" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Shots</SelectItem>
              <SelectItem value="restricted">Restricted Area</SelectItem>
              <SelectItem value="paint">Paint (Non-RA)</SelectItem>
              <SelectItem value="mid-range">Mid-Range</SelectItem>
              <SelectItem value="corner">Corner 3</SelectItem>
              <SelectItem value="above">Above Break 3</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={fetchShotData} variant="outline" disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="w-5 h-5" />
              Shot Chart
            </CardTitle>
            <CardDescription>
              {shotData?.shots.length} total shots • Green = Made, Red = Missed
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex justify-center">
              <canvas
                ref={canvasRef}
                className="border rounded-lg"
                style={{ maxWidth: '100%', height: 'auto' }}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Shooting Zones</CardTitle>
            <CardDescription>Performance by court area</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {shotData?.zones.map((zone) => (
                <div key={zone.zone} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="font-medium">{zone.zone}</h4>
                    <Badge variant={zone.relativePercentage > 0 ? "default" : "secondary"}>
                      {zone.relativePercentage > 0 ? (
                        <TrendingUp className="w-3 h-3 mr-1" />
                      ) : (
                        <TrendingDown className="w-3 h-3 mr-1" />
                      )}
                      {zone.relativePercentage > 0 ? "+" : ""}{formatPercentage(zone.relativePercentage)} vs League
                    </Badge>
                  </div>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground">FG%</p>
                      <p className="font-medium">{formatPercentage(zone.percentage)}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Attempts</p>
                      <p className="font-medium">{zone.attempts}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Made</p>
                      <p className="font-medium">{zone.made}</p>
                    </div>
                  </div>
                  <div className="w-full bg-muted rounded-full h-2">
                    <div
                      className={cn(
                        "h-2 rounded-full transition-all",
                        zone.relativePercentage > 0 ? "bg-green-500" : "bg-red-500"
                      )}
                      style={{ width: `${Math.min(zone.percentage * 100, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {shotData && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Total Shots</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{shotData.shots.length}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Field Goal %</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {formatPercentage(shotData.shots.filter(s => s.made).length / shotData.shots.length)}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">3-Point %</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {(() => {
                  const threePointers = shotData.shots.filter(s => s.value === 3);
                  const madeThrees = threePointers.filter(s => s.made);
                  return threePointers.length > 0 ? formatPercentage(madeThrees.length / threePointers.length) : "0.0%";
                })()}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Points from Shots</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {shotData.shots.filter(s => s.made).reduce((sum, shot) => sum + shot.value, 0)}
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
