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
  Zap, 
  Target, 
  Activity, 
  Eye,
  RotateCcw,
  Play,
  Pause,
  SkipForward,
  TrendingUp,
  Crosshair,
  Wind,
  Gauge,
  BarChart3,
  Maximize,
  Settings,
  Camera
} from 'lucide-react';

interface ShotData {
  id: string;
  playerName: string;
  shotType: string;
  releaseX: number;
  releaseY: number;
  releaseHeight: number;
  targetX: number;
  targetY: number;
  targetHeight: number;
  releaseAngle: number;
  releaseVelocity: number;
  spinRate: number;
  made: boolean;
  actualArcHeight: number;
  actualDistance: number;
  shotDifficulty: number;
  defenseProximity: number;
  successProbability: number;
  releaseTime: number;
  trajectoryPoints: { x: number; y: number; z: number; time: number }[];
}

interface ShotVisualizerProps {
  playerName: string;
  shots: ShotData[];
  selectedShotId?: string;
  viewMode: 'trajectory' | 'heatmap' | 'comparison' | 'physics';
  courtAngle: number;
  showPhysicsData?: boolean;
}

const mockShots: ShotData[] = [
  {
    id: 'shot-1',
    playerName: 'Stephen Curry',
    shotType: '3PT Pullup',
    releaseX: 25, releaseY: 26, releaseHeight: 9.5,
    targetX: 25, targetY: 5.25, targetHeight: 10,
    releaseAngle: 48, releaseVelocity: 29.5, spinRate: 180,
    made: true, actualArcHeight: 16.2, actualDistance: 26.8,
    shotDifficulty: 7, defenseProximity: 4.2, successProbability: 78,
    releaseTime: 0.42,
    trajectoryPoints: [
      { x: 25, y: 26, z: 9.5, time: 0 },
      { x: 25, y: 24, z: 12.8, time: 0.15 },
      { x: 25, y: 20, z: 15.2, time: 0.35 },
      { x: 25, y: 15, z: 16.2, time: 0.55 },
      { x: 25, y: 10, z: 14.8, time: 0.75 },
      { x: 25, y: 6, z: 11.2, time: 0.9 },
      { x: 25, y: 5.25, z: 10, time: 1.0 }
    ]
  },
  {
    id: 'shot-2',
    playerName: 'LeBron James',
    shotType: 'Fadeaway Jumper',
    releaseX: 30, releaseY: 18, releaseHeight: 10.2,
    targetX: 25, targetY: 5.25, targetHeight: 10,
    releaseAngle: 52, releaseVelocity: 28.8, spinRate: 165,
    made: false, actualArcHeight: 17.5, actualDistance: 15.8,
    shotDifficulty: 8, defenseProximity: 2.1, successProbability: 65,
    releaseTime: 0.38,
    trajectoryPoints: [
      { x: 30, y: 18, z: 10.2, time: 0 },
      { x: 29, y: 16, z: 13.5, time: 0.12 },
      { x: 28, y: 13, z: 16.2, time: 0.28 },
      { x: 27, y: 10, z: 17.5, time: 0.45 },
      { x: 26, y: 8, z: 16.8, time: 0.6 },
      { x: 25.2, y: 6, z: 13.2, time: 0.78 },
      { x: 24.8, y: 4.5, z: 9.5, time: 0.92 }
    ]
  },
  {
    id: 'shot-3',
    playerName: 'Damian Lillard',
    shotType: 'Deep 3PT',
    releaseX: 25, releaseY: 32, releaseHeight: 9.8,
    targetX: 25, targetY: 5.25, targetHeight: 10,
    releaseAngle: 45, releaseVelocity: 32.1, spinRate: 195,
    made: true, actualArcHeight: 18.8, actualDistance: 32.5,
    shotDifficulty: 9, defenseProximity: 3.8, successProbability: 45,
    releaseTime: 0.35,
    trajectoryPoints: [
      { x: 25, y: 32, z: 9.8, time: 0 },
      { x: 25, y: 28, z: 14.2, time: 0.2 },
      { x: 25, y: 24, z: 17.1, time: 0.4 },
      { x: 25, y: 19, z: 18.8, time: 0.6 },
      { x: 25, y: 14, z: 18.2, time: 0.8 },
      { x: 25, y: 9, z: 15.5, time: 1.0 },
      { x: 25, y: 5.25, z: 10, time: 1.18 }
    ]
  }
];

export default function ShotTrajectoryVisualizer({
  playerName = "Stephen Curry",
  shots = mockShots,
  selectedShotId,
  viewMode = 'trajectory',
  courtAngle = 0,
  showPhysicsData = false
}: ShotVisualizerProps) {
  const [currentShot, setCurrentShot] = useState(selectedShotId || shots[0]?.id);
  const [animationProgress, setAnimationProgress] = useState([100]);
  const [isAnimating, setIsAnimating] = useState(false);
  const [showTrajectory, setShowTrajectory] = useState(true);
  const [showPhysics, setShowPhysics] = useState(showPhysicsData);
  const [camera3D, setCamera3D] = useState({ elevation: 30, rotation: 0, distance: 150 });
  const [playbackSpeed, setPlaybackSpeed] = useState([1]);
  const [highlightOptimal, setHighlightOptimal] = useState(false);
  const [showSuccessProbability, setShowSuccessProbability] = useState(true);
  const [timeElapsed, setTimeElapsed] = useState(0);
  const animationRef = useRef<number | null>(null);

  const selectedShot = shots.find(shot => shot.id === currentShot) || shots[0];

  const optimalTrajectory = useMemo(() => {
    if (!selectedShot) return [];
    
    const distance = Math.sqrt(
      Math.pow(selectedShot.targetX - selectedShot.releaseX, 2) +
      Math.pow(selectedShot.targetY - selectedShot.releaseY, 2)
    );
    
    const optimalAngle = 45 + (selectedShot.targetHeight - selectedShot.releaseHeight) / distance * 10;
    const optimalVelocity = Math.sqrt(
      (distance * 32.174) / Math.sin(2 * optimalAngle * Math.PI / 180)
    );
    
    const points = [];
    for (let t = 0; t <= 1.2; t += 0.05) {
      const x = selectedShot.releaseX + (selectedShot.targetX - selectedShot.releaseX) * (t / 1.2);
      const y = selectedShot.releaseY + (selectedShot.targetY - selectedShot.releaseY) * (t / 1.2);
      const z = selectedShot.releaseHeight +
        optimalVelocity * Math.sin(optimalAngle * Math.PI / 180) * t -
        16.087 * t * t;
      
      if (z >= 0) points.push({ x, y, z, time: t });
    }
    
    return points;
  }, [selectedShot]);

  useEffect(() => {
    if (isAnimating) {
      const animate = () => {
        setTimeElapsed(prev => {
          const newTime = prev + 0.016 * playbackSpeed[0];
          if (newTime >= (selectedShot?.trajectoryPoints[selectedShot.trajectoryPoints.length - 1]?.time || 1)) {
            setIsAnimating(false);
            return newTime;
          }
          return newTime;
        });
        animationRef.current = requestAnimationFrame(animate);
      };
      animationRef.current = requestAnimationFrame(animate);
    } else {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    }

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isAnimating, playbackSpeed, selectedShot]);

  const project3D = (x: number, y: number, z: number) => {
    const cos_elev = Math.cos(camera3D.elevation * Math.PI / 180);
    const sin_elev = Math.sin(camera3D.elevation * Math.PI / 180);
    const cos_rot = Math.cos(camera3D.rotation * Math.PI / 180);
    const sin_rot = Math.sin(camera3D.rotation * Math.PI / 180);
    
    const x_rot = x * cos_rot - y * sin_rot;
    const y_rot = x * sin_rot + y * cos_rot;
    
    const x_proj = x_rot;
    const y_proj = y_rot * cos_elev - z * sin_elev;
    const z_proj = y_rot * sin_elev + z * cos_elev;
    
    const perspective = camera3D.distance / (camera3D.distance + z_proj);
    
    return {
      x: 400 + x_proj * perspective * 4,
      y: 300 - y_proj * perspective * 4,
      scale: perspective
    };
  };

  const getCurrentBallPosition = () => {
    if (!selectedShot || !isAnimating) return null;
    
    const trajectory = selectedShot.trajectoryPoints;
    const currentTime = timeElapsed;
    
    let i = 0;
    while (i < trajectory.length - 1 && trajectory[i].time < currentTime) {
      i++;
    }
    
    if (i === 0) return trajectory[0];
    if (i >= trajectory.length) return trajectory[trajectory.length - 1];
    
    const prev = trajectory[i - 1];
    const next = trajectory[i];
    const t = (currentTime - prev.time) / (next.time - prev.time);
    
    return {
      x: prev.x + (next.x - prev.x) * t,
      y: prev.y + (next.y - prev.y) * t,
      z: prev.z + (next.z - prev.z) * t,
      time: currentTime
    };
  };

  const currentBallPos = getCurrentBallPosition();

  const shotAnalytics = useMemo(() => {
    if (!selectedShot) return null;
    
    const peakHeight = Math.max(...selectedShot.trajectoryPoints.map(p => p.z));
    const totalTime = selectedShot.trajectoryPoints[selectedShot.trajectoryPoints.length - 1].time;
    const avgVelocity = selectedShot.actualDistance / totalTime;
    
    return {
      peakHeight: peakHeight.toFixed(1),
      totalTime: totalTime.toFixed(2),
      avgVelocity: avgVelocity.toFixed(1),
      efficiency: ((selectedShot.successProbability / 100) * (10 - selectedShot.shotDifficulty)).toFixed(1)
    };
  }, [selectedShot]);

  const handlePlayAnimation = () => {
    if (isAnimating) {
      setIsAnimating(false);
    } else {
      setTimeElapsed(0);
      setIsAnimating(true);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Target className="w-5 h-5" />
                3D Shot Trajectory Analyzer
                <Badge variant="outline">{selectedShot?.shotType}</Badge>
              </h3>
              <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                <span>Player: {selectedShot?.playerName}</span>
                <span>Distance: {selectedShot?.actualDistance.toFixed(1)} ft</span>
                <span>Success Rate: {selectedShot?.successProbability}%</span>
              </div>
            </div>
            
            <Tabs value={viewMode} onValueChange={() => {}}>
              <TabsList>
                <TabsTrigger value="trajectory">Trajectory</TabsTrigger>
                <TabsTrigger value="heatmap">Heat Map</TabsTrigger>
                <TabsTrigger value="comparison">Compare</TabsTrigger>
                <TabsTrigger value="physics">Physics</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </CardHeader>
      </Card>

      {/* Controls */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card>
          <CardContent className="p-4">
            <Label className="text-sm font-medium">Shot Selection</Label>
            <Select value={currentShot} onValueChange={setCurrentShot}>
              <SelectTrigger className="mt-2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {shots.map(shot => (
                  <SelectItem key={shot.id} value={shot.id}>
                    {shot.shotType} • {shot.made ? '✓' : '✗'}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <Label className="text-sm font-medium">Camera Control</Label>
            <div className="space-y-2 mt-2">
              <div>
                <Label className="text-xs">Elevation</Label>
                <Slider
                  value={[camera3D.elevation]}
                  onValueChange={(value) => setCamera3D(prev => ({ ...prev, elevation: value[0] }))}
                  min={0}
                  max={90}
                  step={5}
                />
              </div>
              <div>
                <Label className="text-xs">Rotation</Label>
                <Slider
                  value={[camera3D.rotation]}
                  onValueChange={(value) => setCamera3D(prev => ({ ...prev, rotation: value[0] }))}
                  min={-180}
                  max={180}
                  step={10}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <Label className="text-sm font-medium">Animation</Label>
            <div className="space-y-2 mt-2">
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  onClick={handlePlayAnimation}
                  className="flex-1"
                >
                  {isAnimating ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setTimeElapsed(0)}
                >
                  <RotateCcw className="w-4 h-4" />
                </Button>
              </div>
              <div>
                <Label className="text-xs">Speed: {playbackSpeed[0]}x</Label>
                <Slider
                  value={playbackSpeed}
                  onValueChange={setPlaybackSpeed}
                  min={0.25}
                  max={3}
                  step={0.25}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <Label className="text-sm">Show Trajectory</Label>
              <Switch checked={showTrajectory} onCheckedChange={setShowTrajectory} />
            </div>
            <div className="flex items-center justify-between">
              <Label className="text-sm">Physics Data</Label>
              <Switch checked={showPhysics} onCheckedChange={setShowPhysics} />
            </div>
            <div className="flex items-center justify-between">
              <Label className="text-sm">Optimal Arc</Label>
              <Switch checked={highlightOptimal} onCheckedChange={setHighlightOptimal} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <Label className="text-sm font-medium">Shot Metrics</Label>
            <div className="space-y-1 text-xs mt-2">
              <div className="flex justify-between">
                <span>Release Angle:</span>
                <Badge variant="outline">{selectedShot?.releaseAngle}°</Badge>
              </div>
              <div className="flex justify-between">
                <span>Velocity:</span>
                <Badge variant="outline">{selectedShot?.releaseVelocity} ft/s</Badge>
              </div>
              <div className="flex justify-between">
                <span>Spin Rate:</span>
                <Badge variant="outline">{selectedShot?.spinRate} RPM</Badge>
              </div>
              <div className="flex justify-between">
                <span>Difficulty:</span>
                <Badge variant={selectedShot && selectedShot.shotDifficulty > 7 ? 'destructive' : 'secondary'}>
                  {selectedShot?.shotDifficulty}/10
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 3D Visualization */}
      <Card>
        <CardContent className="p-6">
          <div className="relative bg-gradient-to-br from-blue-900 to-purple-900 rounded-lg overflow-hidden" style={{ height: '600px' }}>
            <svg width="100%" height="100%" viewBox="0 0 800 600">
              <defs>
                <radialGradient id="ballGradient" cx="30%" cy="30%" r="50%">
                  <stop offset="0%" style={{stopColor: '#ff6b35', stopOpacity: 1}} />
                  <stop offset="100%" style={{stopColor: '#d63031', stopOpacity: 1}} />
                </radialGradient>
                <linearGradient id="courtGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" style={{stopColor: '#2d3748', stopOpacity: 0.8}} />
                  <stop offset="100%" style={{stopColor: '#1a202c', stopOpacity: 0.9}} />
                </linearGradient>
                <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                  <feMerge> 
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                  </feMerge>
                </filter>
              </defs>

              {/* Court base */}
              <rect width="100%" height="100%" fill="url(#courtGradient)" />
              
              {/* Court markings (simplified 3D perspective) */}
              {/* Free throw lane */}
              {(() => {
                const lane1 = project3D(19, 0, 0);
                const lane2 = project3D(31, 0, 0);
                const lane3 = project3D(31, 19, 0);
                const lane4 = project3D(19, 19, 0);
                
                return (
                  <polygon
                    points={`${lane1.x},${lane1.y} ${lane2.x},${lane2.y} ${lane3.x},${lane3.y} ${lane4.x},${lane4.y}`}
                    fill="none"
                    stroke="#4a5568"
                    strokeWidth="2"
                    opacity="0.6"
                  />
                );
              })()}
              
              {/* 3-point arc */}
              {(() => {
                const arcPoints = [];
                for (let angle = -Math.PI/3; angle <= Math.PI/3; angle += Math.PI/30) {
                  const x = 25 + 23.75 * Math.sin(angle);
                  const y = 5.25 + 23.75 * Math.cos(angle);
                  const projected = project3D(x, y, 0);
                  arcPoints.push(`${projected.x},${projected.y}`);
                }
                
                return (
                  <polyline
                    points={arcPoints.join(' ')}
                    fill="none"
                    stroke="#4a5568"
                    strokeWidth="2"
                    opacity="0.6"
                  />
                );
              })()}

              {/* Basket */}
              {(() => {
                const basket = project3D(25, 5.25, 10);
                const backboard1 = project3D(22, 4, 10);
                const backboard2 = project3D(28, 4, 10);
                const backboard3 = project3D(28, 4, 14);
                const backboard4 = project3D(22, 4, 14);
                
                return (
                  <g>
                    {/* Backboard */}
                    <polygon
                      points={`${backboard1.x},${backboard1.y} ${backboard2.x},${backboard2.y} ${backboard3.x},${backboard3.y} ${backboard4.x},${backboard4.y}`}
                      fill="#e2e8f0"
                      stroke="#718096"
                      strokeWidth="1"
                      opacity="0.8"
                    />
                    {/* Rim */}
                    <circle
                      cx={basket.x}
                      cy={basket.y}
                      r="6"
                      fill="none"
                      stroke="#e53e3e"
                      strokeWidth="3"
                    />
                  </g>
                );
              })()}

              {/* Optimal trajectory (if enabled) */}
              {highlightOptimal && (
                <path
                  d={`M ${optimalTrajectory.map(point => {
                    const proj = project3D(point.x, point.y, point.z);
                    return `${proj.x},${proj.y}`;
                  }).join(' L ')}`}
                  stroke="#48bb78"
                  strokeWidth="2"
                  fill="none"
                  strokeDasharray="5,3"
                  opacity="0.7"
                />
              )}

              {/* Actual trajectory */}
              {showTrajectory && selectedShot && (
                <g>
                  <path
                    d={`M ${selectedShot.trajectoryPoints.map(point => {
                      const proj = project3D(point.x, point.y, point.z);
                      return `${proj.x},${proj.y}`;
                    }).join(' L ')}`}
                    stroke={selectedShot.made ? '#48bb78' : '#f56565'}
                    strokeWidth="3"
                    fill="none"
                    filter="url(#glow)"
                  />
                  
                  {/* Trajectory points */}
                  {selectedShot.trajectoryPoints.map((point, index) => {
                    const proj = project3D(point.x, point.y, point.z);
                    const isPassed = isAnimating ? point.time <= timeElapsed : true;
                    
                    return (
                      <circle
                        key={index}
                        cx={proj.x}
                        cy={proj.y}
                        r="3"
                        fill={isPassed ? (selectedShot.made ? '#48bb78' : '#f56565') : '#4a5568'}
                        opacity={isPassed ? 0.8 : 0.3}
                      />
                    );
                  })}
                </g>
              )}

              {/* Animated ball */}
              {isAnimating && currentBallPos && (
                <g>
                  {(() => {
                    const ballProj = project3D(currentBallPos.x, currentBallPos.y, currentBallPos.z);
                    return (
                      <circle
                        cx={ballProj.x}
                        cy={ballProj.y}
                        r={8 * ballProj.scale}
                        fill="url(#ballGradient)"
                        stroke="#d63031"
                        strokeWidth="1"
                        filter="url(#glow)"
                      />
                    );
                  })()}
                </g>
              )}

              {/* Release point */}
              {selectedShot && (
                <g>
                  {(() => {
                    const releaseProj = project3D(selectedShot.releaseX, selectedShot.releaseY, selectedShot.releaseHeight);
                    return (
                      <circle
                        cx={releaseProj.x}
                        cy={releaseProj.y}
                        r="5"
                        fill="#3182ce"
                        stroke="#ffffff"
                        strokeWidth="2"
                      />
                    );
                  })()}
                </g>
              )}

              {/* Physics data overlay */}
              {showPhysics && selectedShot && (
                <g>
                  {/* Release angle indicator */}
                  {(() => {
                    const releaseProj = project3D(selectedShot.releaseX, selectedShot.releaseY, selectedShot.releaseHeight);
                    const angleLength = 30;
                    const angleEndX = releaseProj.x + angleLength * Math.cos(selectedShot.releaseAngle * Math.PI / 180);
                    const angleEndY = releaseProj.y - angleLength * Math.sin(selectedShot.releaseAngle * Math.PI / 180);
                    
                    return (
                      <g>
                        <line
                          x1={releaseProj.x}
                          y1={releaseProj.y}
                          x2={angleEndX}
                          y2={angleEndY}
                          stroke="#fbb040"
                          strokeWidth="2"
                          strokeDasharray="3,2"
                        />
                        <text
                          x={angleEndX + 5}
                          y={angleEndY}
                          className="text-xs fill-yellow-400"
                          fontSize="12"
                        >
                          {selectedShot.releaseAngle}°
                        </text>
                      </g>
                    );
                  })()}
                </g>
              )}

              {/* Success probability indicator */}
              {showSuccessProbability && selectedShot && (
                <g>
                  {(() => {
                    const targetProj = project3D(selectedShot.targetX, selectedShot.targetY, selectedShot.targetHeight + 5);
                    const probability = selectedShot.successProbability;
                    const color = probability > 70 ? '#48bb78' : probability > 40 ? '#ed8936' : '#f56565';
                    
                    return (
                      <g>
                        <circle
                          cx={targetProj.x}
                          cy={targetProj.y}
                          r="15"
                          fill={color}
                          opacity="0.3"
                        />
                        <text
                          x={targetProj.x}
                          y={targetProj.y + 3}
                          textAnchor="middle"
                          className="text-white font-bold"
                          fontSize="12"
                        >
                          {probability}%
                        </text>
                      </g>
                    );
                  })()}
                </g>
              )}
            </svg>

            {/* HUD Overlay */}
            <div className="absolute top-4 left-4 bg-black/70 backdrop-blur-sm rounded-lg p-3 text-white">
              <div className="space-y-1 text-xs">
                <div>Camera: {camera3D.elevation}° elev, {camera3D.rotation}° rot</div>
                {isAnimating && (
                  <div>Time: {timeElapsed.toFixed(2)}s / {selectedShot?.trajectoryPoints[selectedShot.trajectoryPoints.length - 1]?.time.toFixed(2)}s</div>
                )}
                {shotAnalytics && (
                  <>
                    <div>Peak Height: {shotAnalytics.peakHeight} ft</div>
                    <div>Flight Time: {shotAnalytics.totalTime}s</div>
                    <div>Avg Velocity: {shotAnalytics.avgVelocity} ft/s</div>
                  </>
                )}
              </div>
            </div>

            {/* Controls overlay */}
            <div className="absolute top-4 right-4 bg-black/70 backdrop-blur-sm rounded-lg p-3 text-white">
              <div className="space-y-2 text-xs">
                <div className="font-medium">View Controls</div>
                <div>Mouse wheel: Zoom</div>
                <div>Drag: Rotate view</div>
                <div>Space: Play/Pause</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Detailed Analytics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <h4 className="font-semibold flex items-center gap-2">
              <Gauge className="w-4 h-4" />
              Shot Mechanics
            </h4>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm">Release Height:</span>
                <Badge variant="outline">{selectedShot?.releaseHeight} ft</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Launch Angle:</span>
                <Badge variant="outline">{selectedShot?.releaseAngle}°</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Initial Velocity:</span>
                <Badge variant="outline">{selectedShot?.releaseVelocity} ft/s</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Ball Spin:</span>
                <Badge variant="outline">{selectedShot?.spinRate} RPM</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Release Time:</span>
                <Badge variant="outline">{selectedShot?.releaseTime}s</Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h4 className="font-semibold flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Performance Metrics
            </h4>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm">Success Probability:</span>
                <Badge variant={selectedShot && selectedShot.successProbability > 70 ? 'default' : 'secondary'}>
                  {selectedShot?.successProbability}%
                </Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Shot Difficulty:</span>
                <Badge variant={selectedShot && selectedShot.shotDifficulty > 7 ? 'destructive' : 'secondary'}>
                  {selectedShot?.shotDifficulty}/10
                </Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Defense Proximity:</span>
                <Badge variant="outline">{selectedShot?.defenseProximity} ft</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Actual Result:</span>
                <Badge variant={selectedShot?.made ? 'default' : 'destructive'}>
                  {selectedShot?.made ? 'Made' : 'Missed'}
                </Badge>
              </div>
              {shotAnalytics && (
                <div className="flex justify-between items-center">
                  <span className="text-sm">Shot Efficiency:</span>
                  <Badge variant="outline">{shotAnalytics.efficiency}</Badge>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h4 className="font-semibold flex items-center gap-2">
              <TrendingUp className="w-4 h-4" />
              Trajectory Analysis
            </h4>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm">Peak Height:</span>
                <Badge variant="outline">{selectedShot?.actualArcHeight} ft</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Total Distance:</span>
                <Badge variant="outline">{selectedShot?.actualDistance} ft</Badge>
              </div>
              {shotAnalytics && (
                <>
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Flight Time:</span>
                    <Badge variant="outline">{shotAnalytics.totalTime}s</Badge>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Avg Speed:</span>
                    <Badge variant="outline">{shotAnalytics.avgVelocity} ft/s</Badge>
                  </div>
                </>
              )}
              <div className="flex justify-between items-center">
                <span className="text-sm">Arc Quality:</span>
                <Badge variant={selectedShot && selectedShot.actualArcHeight > 15 ? 'default' : 'secondary'}>
                  {selectedShot && selectedShot.actualArcHeight > 15 ? 'Optimal' : 'Low'}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
} 