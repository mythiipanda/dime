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
  Users, 
  Zap, 
  Target, 
  Activity, 
  TrendingUp,
  GitBranch,
  Network,
  Heart,
  Star,
  AlertCircle,
  ArrowRightLeft,
  BarChart3,
  Eye,
  Pause,
  Play
} from 'lucide-react';

interface PlayerNode {
  id: string;
  name: string;
  position: string;
  jersey: number;
  isStarter: boolean;
  // Chemistry metrics
  teamChemistry: number; // 0-100
  leadership: number; // 0-100
  adaptability: number; // 0-100
  communication: number; // 0-100
  // Performance impact
  winSharesAdded: number;
  plusMinusImpact: number;
  clutchPerformance: number; // 0-10
  // Network metrics
  centralityScore: number;
  connectionStrength: number;
  influenceRadius: number;
}

interface PlayerConnection {
  from: string;
  to: string;
  strength: number; // 0-100
  type: 'positive' | 'neutral' | 'negative';
  onCourtPlusMinus: number;
  gamesPlayedTogether: number;
  assistConnectionRate: number;
  defensiveCoordination: number;
  // Contextual data
  improvingTrend: boolean;
  clutchSynergy: number;
  playoffPerformance: number;
}

interface TeamChemistryProps {
  teamName: string;
  season: string;
  players: PlayerNode[];
  connections: PlayerConnection[];
  viewMode: 'chemistry' | 'leadership' | 'performance' | 'clutch';
}

const mockPlayers: PlayerNode[] = [
  {
    id: 'lebron', name: 'LeBron James', position: 'SF', jersey: 23, isStarter: true,
    teamChemistry: 92, leadership: 98, adaptability: 88, communication: 95,
    winSharesAdded: 8.2, plusMinusImpact: 6.8, clutchPerformance: 9,
    centralityScore: 95, connectionStrength: 89, influenceRadius: 94
  },
  {
    id: 'ad', name: 'Anthony Davis', position: 'PF/C', jersey: 3, isStarter: true,
    teamChemistry: 85, leadership: 78, adaptability: 82, communication: 80,
    winSharesAdded: 7.1, plusMinusImpact: 5.9, clutchPerformance: 8,
    centralityScore: 88, connectionStrength: 85, influenceRadius: 87
  },
  {
    id: 'reaves', name: 'Austin Reaves', position: 'SG', jersey: 15, isStarter: true,
    teamChemistry: 78, leadership: 65, adaptability: 92, communication: 85,
    winSharesAdded: 4.3, plusMinusImpact: 3.2, clutchPerformance: 7,
    centralityScore: 72, connectionStrength: 79, influenceRadius: 68
  },
  {
    id: 'russell', name: 'D\'Angelo Russell', position: 'PG', jersey: 1, isStarter: true,
    teamChemistry: 71, leadership: 72, adaptability: 75, communication: 88,
    winSharesAdded: 3.8, plusMinusImpact: 2.1, clutchPerformance: 6,
    centralityScore: 75, connectionStrength: 73, influenceRadius: 71
  },
  {
    id: 'hachimura', name: 'Rui Hachimura', position: 'PF', jersey: 28, isStarter: true,
    teamChemistry: 74, leadership: 58, adaptability: 80, communication: 72,
    winSharesAdded: 2.9, plusMinusImpact: 1.8, clutchPerformance: 6,
    centralityScore: 65, connectionStrength: 71, influenceRadius: 62
  },
  {
    id: 'vanderbilt', name: 'Jarred Vanderbilt', position: 'PF', jersey: 2, isStarter: false,
    teamChemistry: 88, leadership: 82, adaptability: 85, communication: 90,
    winSharesAdded: 3.1, plusMinusImpact: 4.2, clutchPerformance: 7,
    centralityScore: 78, connectionStrength: 86, influenceRadius: 75
  },
  {
    id: 'christie', name: 'Max Christie', position: 'SG', jersey: 10, isStarter: false,
    teamChemistry: 82, leadership: 68, adaptability: 95, communication: 78,
    winSharesAdded: 1.8, plusMinusImpact: 1.2, clutchPerformance: 5,
    centralityScore: 58, connectionStrength: 75, influenceRadius: 55
  }
];

const mockConnections: PlayerConnection[] = [
  { from: 'lebron', to: 'ad', strength: 95, type: 'positive', onCourtPlusMinus: 12.3, gamesPlayedTogether: 45, assistConnectionRate: 78, defensiveCoordination: 88, improvingTrend: true, clutchSynergy: 92, playoffPerformance: 89 },
  { from: 'lebron', to: 'reaves', strength: 88, type: 'positive', onCourtPlusMinus: 8.7, gamesPlayedTogether: 42, assistConnectionRate: 65, defensiveCoordination: 72, improvingTrend: true, clutchSynergy: 85, playoffPerformance: 82 },
  { from: 'lebron', to: 'russell', strength: 72, type: 'neutral', onCourtPlusMinus: 3.2, gamesPlayedTogether: 38, assistConnectionRate: 45, defensiveCoordination: 58, improvingTrend: false, clutchSynergy: 68, playoffPerformance: 65 },
  { from: 'lebron', to: 'vanderbilt', strength: 91, type: 'positive', onCourtPlusMinus: 9.8, gamesPlayedTogether: 28, assistConnectionRate: 42, defensiveCoordination: 95, improvingTrend: true, clutchSynergy: 78, playoffPerformance: 88 },
  
  { from: 'ad', to: 'reaves', strength: 82, type: 'positive', onCourtPlusMinus: 6.8, gamesPlayedTogether: 41, assistConnectionRate: 58, defensiveCoordination: 85, improvingTrend: true, clutchSynergy: 80, playoffPerformance: 75 },
  { from: 'ad', to: 'hachimura', strength: 79, type: 'positive', onCourtPlusMinus: 5.2, gamesPlayedTogether: 35, assistConnectionRate: 52, defensiveCoordination: 82, improvingTrend: false, clutchSynergy: 72, playoffPerformance: 78 },
  { from: 'ad', to: 'vanderbilt', strength: 89, type: 'positive', onCourtPlusMinus: 8.9, gamesPlayedTogether: 26, assistConnectionRate: 38, defensiveCoordination: 92, improvingTrend: true, clutchSynergy: 85, playoffPerformance: 90 },
  
  { from: 'reaves', to: 'russell', strength: 75, type: 'positive', onCourtPlusMinus: 4.1, gamesPlayedTogether: 39, assistConnectionRate: 68, defensiveCoordination: 65, improvingTrend: true, clutchSynergy: 75, playoffPerformance: 70 },
  { from: 'reaves', to: 'christie', strength: 85, type: 'positive', onCourtPlusMinus: 6.2, gamesPlayedTogether: 25, assistConnectionRate: 72, defensiveCoordination: 78, improvingTrend: true, clutchSynergy: 82, playoffPerformance: 68 },
  { from: 'russell', to: 'hachimura', strength: 68, type: 'neutral', onCourtPlusMinus: 1.8, gamesPlayedTogether: 33, assistConnectionRate: 48, defensiveCoordination: 55, improvingTrend: false, clutchSynergy: 62, playoffPerformance: 58 },
  
  { from: 'vanderbilt', to: 'christie', strength: 78, type: 'positive', onCourtPlusMinus: 4.8, gamesPlayedTogether: 18, assistConnectionRate: 35, defensiveCoordination: 88, improvingTrend: true, clutchSynergy: 70, playoffPerformance: 72 },
];

export default function TeamChemistryNetwork({
  teamName = "Lakers",
  season = "2024-25",
  players = mockPlayers,
  connections = mockConnections,
  viewMode = 'chemistry'
}: TeamChemistryProps) {
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedConnection, setSelectedConnection] = useState<PlayerConnection | null>(null);
  const [filterStrength, setFilterStrength] = useState([50]);
  const [showLabels, setShowLabels] = useState(true);
  const [showMetrics, setShowMetrics] = useState(false);
  const [animateFlow, setAnimateFlow] = useState(false);
  const [networkLayout, setNetworkLayout] = useState<'force' | 'circular' | 'hierarchical'>('force');
  const [timeElapsed, setTimeElapsed] = useState(0);
  const animationRef = useRef<number | null>(null);

  const filteredConnections = connections.filter(conn => conn.strength >= filterStrength[0]);

  const nodePositions = useMemo(() => {
    const positions: { [key: string]: { x: number; y: number } } = {};
    const centerX = 250;
    const centerY = 200;

    if (networkLayout === 'circular') {
      players.forEach((player, index) => {
        const angle = (index / players.length) * 2 * Math.PI;
        const radius = 120;
        positions[player.id] = {
          x: centerX + Math.cos(angle) * radius,
          y: centerY + Math.sin(angle) * radius
        };
      });
    } else if (networkLayout === 'hierarchical') {
      const sortedPlayers = [...players].sort((a, b) => b.leadership - a.leadership);
      sortedPlayers.forEach((player, index) => {
        const tier = Math.floor(index / 3);
        const posInTier = index % 3;
        positions[player.id] = {
          x: centerX + (posInTier - 1) * 100,
          y: 80 + tier * 80
        };
      });
    } else {
      players.forEach((player, index) => {
        const angle = (index / players.length) * 2 * Math.PI;
        const radius = 80 + player.centralityScore * 0.8;
        positions[player.id] = {
          x: centerX + Math.cos(angle) * radius,
          y: centerY + Math.sin(angle) * radius
        };
      });
    }

    return positions;
  }, [players, networkLayout]);

  const getNodeColor = (player: PlayerNode) => {
    switch (viewMode) {
      case 'chemistry':
        return player.teamChemistry > 85 ? '#10b981' : player.teamChemistry > 70 ? '#f59e0b' : '#ef4444';
      case 'leadership':
        return player.leadership > 80 ? '#7c3aed' : player.leadership > 60 ? '#3b82f6' : '#6b7280';
      case 'performance':
        return player.winSharesAdded > 5 ? '#dc2626' : player.winSharesAdded > 3 ? '#f97316' : '#64748b';
      case 'clutch':
        return player.clutchPerformance > 7 ? '#fbbf24' : player.clutchPerformance > 5 ? '#a3a3a3' : '#71717a';
      default:
        return '#6b7280';
    }
  };

  const getConnectionStyle = (connection: PlayerConnection) => {
    const width = Math.max(1, (connection.strength / 100) * 4);
    const color = connection.type === 'positive' ? '#10b981' :
                 connection.type === 'negative' ? '#ef4444' : '#6b7280';
    const opacity = connection.improvingTrend ? 0.8 : 0.5;
    
    return { width, color, opacity };
  };

  useEffect(() => {
    if (animateFlow) {
      const animate = () => {
        setTimeElapsed(prev => prev + 0.02);
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
  }, [animateFlow]);

  const teamInsights = useMemo(() => {
    const avgChemistry = players.reduce((sum, p) => sum + p.teamChemistry, 0) / players.length;
    const strongConnections = filteredConnections.filter(c => c.strength > 80).length;
    const leadershipNodes = players.filter(p => p.leadership > 80).length;
    const clutchPlayers = players.filter(p => p.clutchPerformance > 7).length;
    const improvingConnections = filteredConnections.filter(c => c.improvingTrend).length;
    
    return {
      avgChemistry: avgChemistry.toFixed(1),
      strongConnections,
      leadershipNodes,
      clutchPlayers,
      improvingConnections,
      networkHealth: ((strongConnections / filteredConnections.length) * 100).toFixed(0)
    };
  }, [players, filteredConnections]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Network className="w-5 h-5" />
                {teamName} Team Chemistry Network
                <Badge variant="outline">{season}</Badge>
              </h3>
              <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                <span>Network Health: {teamInsights.networkHealth}%</span>
                <span>Strong Connections: {teamInsights.strongConnections}</span>
                <span>Leadership Nodes: {teamInsights.leadershipNodes}</span>
              </div>
            </div>
            
            <Tabs value={viewMode} onValueChange={() => {}}>
              <TabsList>
                <TabsTrigger value="chemistry">Chemistry</TabsTrigger>
                <TabsTrigger value="leadership">Leadership</TabsTrigger>
                <TabsTrigger value="performance">Performance</TabsTrigger>
                <TabsTrigger value="clutch">Clutch</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </CardHeader>
      </Card>

      {/* Controls */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <Label className="text-sm font-medium">Connection Filter</Label>
            <Slider
              value={filterStrength}
              onValueChange={setFilterStrength}
              min={0}
              max={100}
              step={5}
              className="mt-2"
            />
            <div className="text-xs text-muted-foreground mt-1">
              Min strength: {filterStrength[0]}%
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <Label className="text-sm font-medium">Layout</Label>
            <Select value={networkLayout} onValueChange={(value: any) => setNetworkLayout(value)}>
              <SelectTrigger className="mt-2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="force">Force-Directed</SelectItem>
                <SelectItem value="circular">Circular</SelectItem>
                <SelectItem value="hierarchical">Hierarchical</SelectItem>
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <Label className="text-sm">Show Labels</Label>
              <Switch checked={showLabels} onCheckedChange={setShowLabels} />
            </div>
            <div className="flex items-center justify-between">
              <Label className="text-sm">Show Metrics</Label>
              <Switch checked={showMetrics} onCheckedChange={setShowMetrics} />
            </div>
            <div className="flex items-center justify-between">
              <Label className="text-sm">Animate Flow</Label>
              <Switch checked={animateFlow} onCheckedChange={setAnimateFlow} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <h5 className="text-sm font-medium mb-2">Team Insights</h5>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between">
                <span>Avg Chemistry:</span>
                <Badge variant="outline">{teamInsights.avgChemistry}%</Badge>
              </div>
              <div className="flex justify-between">
                <span>Clutch Players:</span>
                <Badge variant="outline">{teamInsights.clutchPlayers}</Badge>
              </div>
              <div className="flex justify-between">
                <span>Improving:</span>
                <Badge variant="outline">{teamInsights.improvingConnections}</Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Network Visualization */}
      <Card>
        <CardContent className="p-6">
          <div className="relative bg-gradient-to-br from-slate-50 to-slate-100 rounded-lg p-4" style={{ height: '400px' }}>
            <svg width="100%" height="100%" viewBox="0 0 500 400">
              <defs>
                <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                  <feMerge> 
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                  </feMerge>
                </filter>
                <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                  <polygon points="0 0, 10 3.5, 0 7" fill="#6b7280" />
                </marker>
              </defs>

              {/* Connections */}
              {filteredConnections.map((connection, index) => {
                const fromPos = nodePositions[connection.from];
                const toPos = nodePositions[connection.to];
                if (!fromPos || !toPos) return null;

                const style = getConnectionStyle(connection);
                const isSelected = selectedConnection?.from === connection.from && selectedConnection?.to === connection.to;
                
                const animOffset = animateFlow ? (timeElapsed * 50 + index * 30) % 100 : 0;

                return (
                  <g key={`${connection.from}-${connection.to}`}>
                    {/* Main connection line */}
                    <line
                      x1={fromPos.x}
                      y1={fromPos.y}
                      x2={toPos.x}
                      y2={toPos.y}
                      stroke={style.color}
                      strokeWidth={isSelected ? style.width + 2 : style.width}
                      opacity={isSelected ? 1 : style.opacity}
                      className="cursor-pointer transition-all duration-200"
                      onClick={() => setSelectedConnection(selectedConnection === connection ? null : connection)}
                      filter={isSelected ? "url(#glow)" : "none"}
                    />
                    
                    {/* Flow animation */}
                    {animateFlow && (
                      <circle
                        cx={fromPos.x + (toPos.x - fromPos.x) * (animOffset / 100)}
                        cy={fromPos.y + (toPos.y - fromPos.y) * (animOffset / 100)}
                        r="2"
                        fill={style.color}
                        opacity="0.8"
                      />
                    )}
                    
                    {/* Connection strength indicator */}
                    {showMetrics && (
                      <text
                        x={(fromPos.x + toPos.x) / 2}
                        y={(fromPos.y + toPos.y) / 2}
                        textAnchor="middle"
                        className="text-xs fill-gray-600 font-medium"
                        fontSize="10"
                      >
                        {connection.strength}
                      </text>
                    )}
                  </g>
                );
              })}

              {/* Player nodes */}
              {players.map(player => {
                const pos = nodePositions[player.id];
                if (!pos) return null;

                const isSelected = selectedNode === player.id;
                const nodeColor = getNodeColor(player);
                const radius = player.isStarter ? 20 : 16;

                return (
                  <g key={player.id}>
                    {/* Node halo for leadership */}
                    {player.leadership > 85 && (
                      <circle
                        cx={pos.x}
                        cy={pos.y}
                        r={radius + 8}
                        fill="none"
                        stroke="#fbbf24"
                        strokeWidth="2"
                        opacity="0.6"
                        strokeDasharray="5,3"
                      />
                    )}
                    
                    {/* Main node circle */}
                    <circle
                      cx={pos.x}
                      cy={pos.y}
                      r={isSelected ? radius + 4 : radius}
                      fill={nodeColor}
                      stroke="#ffffff"
                      strokeWidth="3"
                      className="cursor-pointer transition-all duration-200 hover:r-22"
                      onClick={() => setSelectedNode(selectedNode === player.id ? null : player.id)}
                      filter={isSelected ? "url(#glow)" : "none"}
                    />
                    
                    {/* Jersey number */}
                    <text
                      x={pos.x}
                      y={pos.y + 4}
                      textAnchor="middle"
                      className="text-white font-bold pointer-events-none"
                      fontSize="12"
                    >
                      {player.jersey}
                    </text>
                    
                    {/* Player name */}
                    {showLabels && (
                      <text
                        x={pos.x}
                        y={pos.y - radius - 8}
                        textAnchor="middle"
                        className="text-gray-700 font-medium pointer-events-none"
                        fontSize="11"
                      >
                        {player.name.split(' ').pop()}
                      </text>
                    )}
                    
                    {/* Position indicator */}
                    <text
                      x={pos.x}
                      y={pos.y + radius + 15}
                      textAnchor="middle"
                      className="text-gray-500 text-xs pointer-events-none"
                      fontSize="9"
                    >
                      {player.position}
                    </text>
                    
                    {/* Chemistry score */}
                    {showMetrics && (
                      <text
                        x={pos.x + radius + 5}
                        y={pos.y - radius - 5}
                        className="text-gray-600 text-xs font-medium pointer-events-none"
                        fontSize="10"
                      >
                        {player[viewMode === 'chemistry' ? 'teamChemistry' : 
                              viewMode === 'leadership' ? 'leadership' :
                              viewMode === 'performance' ? 'winSharesAdded' : 'clutchPerformance']}
                        {viewMode === 'performance' ? '' : '%'}
                      </text>
                    )}
                  </g>
                );
              })}
            </svg>
            
            {/* Legend */}
            <div className="absolute top-4 right-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 space-y-2 text-xs">
              <div className="font-medium">Node Size</div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-blue-500"></div>
                <span>Starter</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                <span>Bench</span>
              </div>
              <div className="font-medium mt-2">Connection Type</div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-0.5 bg-green-500"></div>
                <span>Positive</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-0.5 bg-gray-500"></div>
                <span>Neutral</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-0.5 bg-red-500"></div>
                <span>Negative</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Selected Player Details */}
      {selectedNode && (
        <Card>
          <CardContent className="p-4">
            {(() => {
              const player = players.find(p => p.id === selectedNode);
              if (!player) return null;
              
              return (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div>
                    <div className="flex items-center gap-3 mb-4">
                      <div 
                        className="w-12 h-12 rounded-full flex items-center justify-center text-white font-bold"
                        style={{ backgroundColor: getNodeColor(player) }}
                      >
                        {player.jersey}
                      </div>
                      <div>
                        <h4 className="font-semibold">{player.name}</h4>
                        <p className="text-sm text-muted-foreground">{player.position} • {player.isStarter ? 'Starter' : 'Bench'}</p>
                      </div>
                    </div>
                  </div>
                  
                  <div>
                    <h5 className="font-medium mb-3">Chemistry Metrics</h5>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span>Team Chemistry:</span>
                        <Badge variant="outline">{player.teamChemistry}%</Badge>
                      </div>
                      <div className="flex justify-between">
                        <span>Leadership:</span>
                        <Badge variant="outline">{player.leadership}%</Badge>
                      </div>
                      <div className="flex justify-between">
                        <span>Communication:</span>
                        <Badge variant="outline">{player.communication}%</Badge>
                      </div>
                      <div className="flex justify-between">
                        <span>Adaptability:</span>
                        <Badge variant="outline">{player.adaptability}%</Badge>
                      </div>
                    </div>
                  </div>
                  
                  <div>
                    <h5 className="font-medium mb-3">Network Impact</h5>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span>Centrality Score:</span>
                        <Badge variant="outline">{player.centralityScore}</Badge>
                      </div>
                      <div className="flex justify-between">
                        <span>Connection Strength:</span>
                        <Badge variant="outline">{player.connectionStrength}</Badge>
                      </div>
                      <div className="flex justify-between">
                        <span>Influence Radius:</span>
                        <Badge variant="outline">{player.influenceRadius}</Badge>
                      </div>
                      <div className="flex justify-between">
                        <span>Clutch Rating:</span>
                        <div className="flex items-center gap-1">
                          {[...Array(10)].map((_, i) => (
                            <Star
                              key={i}
                              className={`w-3 h-3 ${i < player.clutchPerformance ? 'text-yellow-400 fill-current' : 'text-gray-300'}`}
                            />
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })()}
          </CardContent>
        </Card>
      )}

      {/* Selected Connection Details */}
      {selectedConnection && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-4">
              <h4 className="font-semibold flex items-center gap-2">
                <ArrowRightLeft className="w-5 h-5" />
                Connection Analysis
              </h4>
              <Button size="sm" variant="ghost" onClick={() => setSelectedConnection(null)}>
                ×
              </Button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <h5 className="font-medium mb-3">Players</h5>
                <div className="space-y-2">
                  <div>{players.find(p => p.id === selectedConnection.from)?.name}</div>
                  <div className="text-center">↔</div>
                  <div>{players.find(p => p.id === selectedConnection.to)?.name}</div>
                </div>
              </div>
              
              <div>
                <h5 className="font-medium mb-3">On-Court Synergy</h5>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>Connection Strength:</span>
                    <Badge variant="outline">{selectedConnection.strength}%</Badge>
                  </div>
                  <div className="flex justify-between">
                    <span>Plus/Minus:</span>
                    <Badge variant={selectedConnection.onCourtPlusMinus > 0 ? 'default' : 'destructive'}>
                      {selectedConnection.onCourtPlusMinus > 0 ? '+' : ''}{selectedConnection.onCourtPlusMinus}
                    </Badge>
                  </div>
                  <div className="flex justify-between">
                    <span>Games Together:</span>
                    <Badge variant="outline">{selectedConnection.gamesPlayedTogether}</Badge>
                  </div>
                  <div className="flex justify-between">
                    <span>Assist Rate:</span>
                    <Badge variant="outline">{selectedConnection.assistConnectionRate}%</Badge>
                  </div>
                </div>
              </div>
              
              <div>
                <h5 className="font-medium mb-3">Performance Context</h5>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>Defensive Coordination:</span>
                    <Badge variant="outline">{selectedConnection.defensiveCoordination}%</Badge>
                  </div>
                  <div className="flex justify-between">
                    <span>Clutch Synergy:</span>
                    <Badge variant="outline">{selectedConnection.clutchSynergy}%</Badge>
                  </div>
                  <div className="flex justify-between">
                    <span>Playoff Performance:</span>
                    <Badge variant="outline">{selectedConnection.playoffPerformance}%</Badge>
                  </div>
                  <div className="flex justify-between">
                    <span>Trend:</span>
                    <Badge variant={selectedConnection.improvingTrend ? 'default' : 'secondary'}>
                      {selectedConnection.improvingTrend ? 'Improving' : 'Stable'}
                    </Badge>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
} 