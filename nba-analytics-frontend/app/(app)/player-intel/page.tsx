"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { 
  Microscope,
  TrendingUp, 
  TrendingDown, 
  Target, 
  Zap, 
  BarChart3, 
  Activity,
  Crown,
  Shield,
  Crosshair,
  Eye,
  ChevronRight,
  Star,
  ArrowUpDown,
  Search,
  Brain,
  FlameKindling,
  LineChart,
  Users,
  Calendar,
  Award
} from 'lucide-react';
import { Input } from "@/components/ui/input";

// Advanced Player Analytics Data Structures
interface PlayerProfile {
  playerId: string;
  fullName: string;
  firstName: string;
  lastName: string;
  teamAbbr: string;
  teamName: string;
  position: string;
  height: string;
  weight: string;
  age: number;
  experience: number;
  college: string;
  country: string;
  jerseyNumber: string;
  avatarUrl?: string;
  salary: number;
  contractYears: number;
}

interface AdvancedPlayerMetrics {
  // Impact Metrics
  epm: number; // Estimated Plus-Minus
  lebron: number; // LEBRON metric
  raptor: number; // RAPTOR
  bpm: number; // Box Plus-Minus
  vorp: number; // Value Over Replacement Player
  winShares: number;
  winSharesPer48: number;
  
  // Efficiency Metrics
  trueShooting: number;
  effectiveFieldGoal: number;
  usage: number;
  pie: number; // Player Impact Estimate
  
  // Shot Quality & Creation
  shotQuality: number; // Expected vs Actual
  shotCreation: number; // Self-created shot %
  assistedFieldGoals: number;
  
  // Defensive Impact
  defRating: number;
  defWinShares: number;
  deflections: number;
  contests: number;
  charges: number;
}

interface SkillDevelopment {
  season: string;
  age: number;
  
  // Shooting Skills
  threePt: number;
  midRange: number;
  rim: number;
  freeThrow: number;
  
  // Playmaking
  assists: number;
  turnovers: number;
  assistToTurnover: number;
  
  // Defense
  steals: number;
  blocks: number;
  defenseRating: number;
  
  // Physical/Motor Skills
  rebounding: number;
  hustle: number;
  athleticism: number;
}

interface ShotAnalysis {
  zone: string;
  attempts: number;
  makes: number;
  percentage: number;
  expectedPercentage: number;
  frequency: number;
  pointsPerShot: number;
  quality: 'Excellent' | 'Good' | 'Average' | 'Poor';
}

interface PlayerComparison {
  playerId: string;
  playerName: string;
  teamAbbr: string;
  similarityScore: number;
  reason: string;
  strengthsInCommon: string[];
  differentiators: string[];
}

interface InjuryImpact {
  injuryType: string;
  gamesAffected: number;
  preInjuryMetrics: {
    ppg: number;
    efficiency: number;
    impact: number;
  };
  postInjuryMetrics: {
    ppg: number;
    efficiency: number;
    impact: number;
  };
  recoveryProjection: string;
}

// Mock API Functions
const mockPlayerSearchAPI = async (query: string): Promise<PlayerProfile[]> => {
  await new Promise(resolve => setTimeout(resolve, 300));
  const allPlayers = [
    { playerId: "1", fullName: "Nikola Jokic", firstName: "Nikola", lastName: "Jokic", teamAbbr: "DEN", teamName: "Denver Nuggets", position: "C", height: "7-0", weight: "284", age: 29, experience: 9, college: "Mega Basket (Serbia)", country: "Serbia", jerseyNumber: "15", salary: 47607350, contractYears: 5 },
    { playerId: "2", fullName: "Luka Doncic", firstName: "Luka", lastName: "Doncic", teamAbbr: "DAL", teamName: "Dallas Mavericks", position: "PG", height: "6-7", weight: "230", age: 25, experience: 6, college: "Real Madrid (Spain)", country: "Slovenia", jerseyNumber: "77", salary: 40064220, contractYears: 5 },
    { playerId: "3", fullName: "Shai Gilgeous-Alexander", firstName: "Shai", lastName: "Gilgeous-Alexander", teamAbbr: "OKC", teamName: "Oklahoma City Thunder", position: "PG", height: "6-6", weight: "180", age: 26, experience: 6, college: "Kentucky", country: "Canada", jerseyNumber: "2", salary: 35334800, contractYears: 5 },
    { playerId: "4", fullName: "Victor Wembanyama", firstName: "Victor", lastName: "Wembanyama", teamAbbr: "SAS", teamName: "San Antonio Spurs", position: "C", height: "7-4", weight: "210", age: 20, experience: 1, college: "Metropolitans 92 (France)", country: "France", jerseyNumber: "1", salary: 12160680, contractYears: 4 },
    { playerId: "5", fullName: "Paolo Banchero", firstName: "Paolo", lastName: "Banchero", teamAbbr: "ORL", teamName: "Orlando Magic", position: "PF", height: "6-10", weight: "250", age: 21, experience: 2, college: "Duke", country: "USA", jerseyNumber: "5", salary: 11009320, contractYears: 4 },
  ];
  
  return allPlayers.filter(player => 
    player.fullName.toLowerCase().includes(query.toLowerCase()) ||
    player.teamAbbr.toLowerCase().includes(query.toLowerCase())
  );
};

const mockAdvancedPlayerMetricsAPI = async (playerId: string): Promise<AdvancedPlayerMetrics> => {
  await new Promise(resolve => setTimeout(resolve, 600));
  
  const metrics: Record<string, AdvancedPlayerMetrics> = {
    "1": { // Jokic
      epm: 8.7, lebron: 9.2, raptor: 9.8, bpm: 11.8, vorp: 8.9, winShares: 15.2, winSharesPer48: 0.254,
      trueShooting: 0.654, effectiveFieldGoal: 0.618, usage: 29.1, pie: 18.7,
      shotQuality: 1.08, shotCreation: 0.42, assistedFieldGoals: 0.58,
      defRating: 112.3, defWinShares: 4.2, deflections: 1.8, contests: 12.4, charges: 0.3
    },
    "2": { // Luka
      epm: 7.9, lebron: 8.1, raptor: 8.4, bpm: 9.4, vorp: 7.8, winShares: 13.8, winSharesPer48: 0.243,
      trueShooting: 0.581, effectiveFieldGoal: 0.548, usage: 35.2, pie: 16.9,
      shotQuality: 0.97, shotCreation: 0.67, assistedFieldGoals: 0.33,
      defRating: 116.8, defWinShares: 2.1, deflections: 1.2, contests: 8.7, charges: 0.1
    },
    "3": { // SGA
      epm: 7.1, lebron: 7.8, raptor: 7.5, bpm: 8.2, vorp: 6.9, winShares: 12.1, winSharesPer48: 0.198,
      trueShooting: 0.612, effectiveFieldGoal: 0.571, usage: 32.4, pie: 15.8,
      shotQuality: 1.12, shotCreation: 0.58, assistedFieldGoals: 0.42,
      defRating: 111.7, defWinShares: 3.8, deflections: 1.6, contests: 11.2, charges: 0.2
    }
  };
  
  return metrics[playerId] || metrics["1"];
};

const mockSkillDevelopmentAPI = async (playerId: string): Promise<SkillDevelopment[]> => {
  await new Promise(resolve => setTimeout(resolve, 500));
  
  // Generate skill development trajectory
  const seasons = ["2021-22", "2022-23", "2023-24"];
  const baseAge = 24;
  
  return seasons.map((season, idx) => ({
    season,
    age: baseAge + idx,
    threePt: 35.2 + (idx * 2.1) + Math.random() * 3,
    midRange: 42.8 + (idx * 1.8) + Math.random() * 2,
    rim: 68.5 + (idx * 1.2) + Math.random() * 2,
    freeThrow: 78.3 + (idx * 2.4) + Math.random() * 3,
    assists: 6.2 + (idx * 0.8) + Math.random() * 1,
    turnovers: 3.4 - (idx * 0.2) + Math.random() * 0.5,
    assistToTurnover: 1.8 + (idx * 0.3) + Math.random() * 0.2,
    steals: 1.4 + (idx * 0.1) + Math.random() * 0.3,
    blocks: 0.8 + (idx * 0.1) + Math.random() * 0.2,
    defenseRating: 112.5 - (idx * 1.2) + Math.random() * 2,
    rebounding: 7.8 + (idx * 0.5) + Math.random() * 1,
    hustle: 75 + (idx * 2) + Math.random() * 5,
    athleticism: 82 - (idx * 0.5) + Math.random() * 2
  }));
};

const mockShotAnalysisAPI = async (playerId: string): Promise<ShotAnalysis[]> => {
  await new Promise(resolve => setTimeout(resolve, 400));
  
  return [
    { zone: "Restricted Area", attempts: 145, makes: 98, percentage: 67.6, expectedPercentage: 64.2, frequency: 28.5, pointsPerShot: 1.35, quality: 'Excellent' },
    { zone: "Paint (Non-RA)", attempts: 87, makes: 41, percentage: 47.1, expectedPercentage: 45.8, frequency: 17.1, pointsPerShot: 0.94, quality: 'Good' },
    { zone: "Mid-Range", attempts: 98, makes: 43, percentage: 43.9, expectedPercentage: 41.2, frequency: 19.3, pointsPerShot: 0.88, quality: 'Good' },
    { zone: "Corner 3", attempts: 67, makes: 28, percentage: 41.8, expectedPercentage: 38.5, frequency: 13.2, pointsPerShot: 1.25, quality: 'Excellent' },
    { zone: "Above Break 3", attempts: 112, makes: 39, percentage: 34.8, expectedPercentage: 35.1, frequency: 22.0, pointsPerShot: 1.04, quality: 'Average' }
  ];
};

const mockPlayerComparisonAPI = async (playerId: string): Promise<PlayerComparison[]> => {
  await new Promise(resolve => setTimeout(resolve, 550));
  
    return [
    {
      playerId: "comp1",
      playerName: "Alperen Sengun", 
      teamAbbr: "HOU",
      similarityScore: 94,
      reason: "Elite passing center with excellent court vision",
      strengthsInCommon: ["Court Vision", "Passing", "Basketball IQ", "Post Skills"],
      differentiators: ["Shooting Range", "Defensive Impact", "Rebounding"]
    },
    {
      playerId: "comp2", 
      playerName: "Domantas Sabonis",
      teamAbbr: "SAC",
      similarityScore: 87,
      reason: "High usage center with strong rebounding and playmaking",
      strengthsInCommon: ["Rebounding", "Passing", "Versatility", "Durability"],
      differentiators: ["Shooting", "Defense", "Post Moves"]
    },
    {
      playerId: "comp3",
      playerName: "Bam Adebayo",
      teamAbbr: "MIA", 
      similarityScore: 73,
      reason: "Versatile big man with defensive impact",
      strengthsInCommon: ["Versatility", "Basketball IQ", "Passing"],
      differentiators: ["Defensive Anchor", "Perimeter Defense", "Offensive Creation"]
    }
  ];
};

const mockInjuryImpactAPI = async (playerId: string): Promise<InjuryImpact | null> => {
  await new Promise(resolve => setTimeout(resolve, 350));
  
  // Return null if no significant injury impact
  if (Math.random() > 0.4) return null;
  
  return {
    injuryType: "Wrist Strain",
    gamesAffected: 12,
    preInjuryMetrics: {
      ppg: 24.8,
      efficiency: 0.612,
      impact: 7.2
    },
    postInjuryMetrics: {
      ppg: 21.3,
      efficiency: 0.583,
      impact: 5.9
    },
    recoveryProjection: "Expected full recovery by playoffs based on similar injury patterns"
  };
};

export default function PlayerLaboratory() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialPlayerId = searchParams.get('id');

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<PlayerProfile[]>([]);
  const [selectedPlayer, setSelectedPlayer] = useState<PlayerProfile | null>(null);
  const [playerMetrics, setPlayerMetrics] = useState<AdvancedPlayerMetrics | null>(null);
  const [skillDevelopment, setSkillDevelopment] = useState<SkillDevelopment[]>([]);
  const [shotAnalysis, setShotAnalysis] = useState<ShotAnalysis[]>([]);
  const [similarPlayers, setSimilarPlayers] = useState<PlayerComparison[]>([]);
  const [injuryImpact, setInjuryImpact] = useState<InjuryImpact | null>(null);
  
  const [isLoadingPlayer, setIsLoadingPlayer] = useState(false);
  const [isLoadingMetrics, setIsLoadingMetrics] = useState(false);
  const [isLoadingSkills, setIsLoadingSkills] = useState(false);
  const [isLoadingShots, setIsLoadingShots] = useState(false);
  const [isLoadingComparisons, setIsLoadingComparisons] = useState(false);
  const [isLoadingInjury, setIsLoadingInjury] = useState(false);

  // Search for players
  useEffect(() => {
    if (searchQuery.length >= 2) {
      const searchPlayers = async () => {
        setIsLoadingPlayer(true);
        const results = await mockPlayerSearchAPI(searchQuery);
        setSearchResults(results);
        setIsLoadingPlayer(false);
      };
      const debounceTimer = setTimeout(searchPlayers, 300);
      return () => clearTimeout(debounceTimer);
    } else {
      setSearchResults([]);
    }
  }, [searchQuery]);

  // Load player data when selected
  useEffect(() => {
    if (selectedPlayer) {
      const loadPlayerData = async () => {
        setIsLoadingMetrics(true);
        setIsLoadingSkills(true);
        setIsLoadingShots(true);
        setIsLoadingComparisons(true);
        setIsLoadingInjury(true);

        try {
          const [metrics, skills, shots, comparisons, injury] = await Promise.all([
            mockAdvancedPlayerMetricsAPI(selectedPlayer.playerId),
            mockSkillDevelopmentAPI(selectedPlayer.playerId),
            mockShotAnalysisAPI(selectedPlayer.playerId),
            mockPlayerComparisonAPI(selectedPlayer.playerId),
            mockInjuryImpactAPI(selectedPlayer.playerId)
          ]);

          setPlayerMetrics(metrics);
          setSkillDevelopment(skills);
          setShotAnalysis(shots);
          setSimilarPlayers(comparisons);
          setInjuryImpact(injury);
        } catch (error) {
          console.error('Error loading player data:', error);
        } finally {
          setIsLoadingMetrics(false);
          setIsLoadingSkills(false);
          setIsLoadingShots(false);
          setIsLoadingComparisons(false);
          setIsLoadingInjury(false);
        }
      };

      loadPlayerData();
    }
  }, [selectedPlayer]);

  // Initialize with player from URL if provided
  useEffect(() => {
    if (initialPlayerId && !selectedPlayer) {
      mockPlayerSearchAPI("").then(players => {
        const player = players.find(p => p.playerId === initialPlayerId) || players[0];
        setSelectedPlayer(player);
      });
    }
  }, [initialPlayerId, selectedPlayer]);

  const selectPlayer = (player: PlayerProfile) => {
    setSelectedPlayer(player);
    setSearchQuery('');
    setSearchResults([]);
    router.push(`/player-intel?id=${player.playerId}`);
  };

  const getSkillColor = (value: number, type: 'percentage' | 'rating' | 'raw') => {
    if (type === 'percentage') {
      if (value >= 40) return 'text-green-600';
      if (value >= 35) return 'text-yellow-600';
      return 'text-red-600';
    }
    if (type === 'rating') {
      if (value <= 110) return 'text-green-600';
      if (value <= 115) return 'text-yellow-600';
      return 'text-red-600';
    }
    return '';
  };

  const getQualityBadge = (quality: string) => {
    const variants = {
      'Excellent': 'default',
      'Good': 'secondary',
      'Average': 'outline',
      'Poor': 'destructive'
    } as const;
    return <Badge variant={variants[quality as keyof typeof variants]}>{quality}</Badge>;
  };

  return (
    <div className="flex-1 space-y-8 p-4 md:p-6 lg:p-8">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Microscope className="h-8 w-8 text-primary" />
            Player Laboratory
          </h1>
          <p className="text-muted-foreground">
            Deep dive analytics and advanced player intelligence
          </p>
        </div>
      </div>

      {/* Player Search */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-5 w-5" />
            Search Players
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative">
            <Input
              placeholder="Search for a player..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full"
            />
          {searchResults.length > 0 && (
              <div className="absolute top-full left-0 right-0 bg-card border rounded-md mt-1 max-h-60 overflow-y-auto z-50">
                {searchResults.map((player) => (
                  <div
                    key={player.playerId}
                    onClick={() => selectPlayer(player)}
                    className="p-3 hover:bg-muted cursor-pointer border-b last:border-b-0"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium">{player.fullName}</div>
                        <div className="text-sm text-muted-foreground">
                          {player.teamAbbr} • {player.position} • {player.age} years old
                        </div>
                      </div>
                      <Badge variant="outline">{player.teamAbbr}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
              </CardContent>
            </Card>

      {selectedPlayer && (
        <>
          {/* Player Header */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-6">
                <Avatar className="h-24 w-24">
                  <AvatarImage src={selectedPlayer.avatarUrl} />
                  <AvatarFallback className="text-lg">
                    {selectedPlayer.firstName[0]}{selectedPlayer.lastName[0]}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1">
                  <div className="flex items-center gap-4 mb-2">
                    <h2 className="text-3xl font-bold">{selectedPlayer.fullName}</h2>
                    <Badge variant="outline" className="text-lg">{selectedPlayer.jerseyNumber}</Badge>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <div className="text-muted-foreground">Team</div>
                      <div className="font-medium">{selectedPlayer.teamName}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Position</div>
                      <div className="font-medium">{selectedPlayer.position}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Age/Experience</div>
                      <div className="font-medium">{selectedPlayer.age} • {selectedPlayer.experience} years</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Size</div>
                      <div className="font-medium">{selectedPlayer.height}, {selectedPlayer.weight} lbs</div>
        </div>
        </div>
      </div>
                <div className="text-right">
                  <div className="text-2xl font-bold">${(selectedPlayer.salary / 1000000).toFixed(1)}M</div>
                  <div className="text-sm text-muted-foreground">{selectedPlayer.contractYears} year contract</div>
                </div>
              </div>
            </CardContent>
           </Card>

          <Tabs defaultValue="impact_metrics" className="w-full">
            <TabsList className="grid w-full grid-cols-2 lg:grid-cols-5">
              <TabsTrigger value="impact_metrics" className="text-xs">
                <Target className="h-4 w-4 mr-1" />
                Impact
              </TabsTrigger>
              <TabsTrigger value="skill_development" className="text-xs">
                <TrendingUp className="h-4 w-4 mr-1" />
                Development
              </TabsTrigger>
              <TabsTrigger value="shot_analysis" className="text-xs">
                <Crosshair className="h-4 w-4 mr-1" />
                Shot Analysis
              </TabsTrigger>
              <TabsTrigger value="comparisons" className="text-xs">
                <Users className="h-4 w-4 mr-1" />
                Comparisons
              </TabsTrigger>
              <TabsTrigger value="injury_impact" className="text-xs">
                <Activity className="h-4 w-4 mr-1" />
                Health
              </TabsTrigger>
            </TabsList>

            <TabsContent value="impact_metrics" className="space-y-6">
          <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Target className="h-5 w-5" />
                    Advanced Impact Metrics
                  </CardTitle>
                  <CardDescription>
                    Comprehensive analysis of {selectedPlayer.firstName}'s on-court impact
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {isLoadingMetrics ? (
                    <Skeleton className="h-96 w-full" />
                  ) : playerMetrics ? (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                      <div className="space-y-4">
                        <h4 className="font-semibold text-sm text-muted-foreground">IMPACT METRICS</h4>
                        <div className="space-y-3">
                          <div className="flex justify-between">
                            <span className="text-sm">EPM</span>
                            <span className="font-mono font-semibold">{playerMetrics.epm > 0 ? '+' : ''}{playerMetrics.epm.toFixed(1)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-sm">LEBRON</span>
                            <span className="font-mono font-semibold">{playerMetrics.lebron > 0 ? '+' : ''}{playerMetrics.lebron.toFixed(1)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-sm">RAPTOR</span>
                            <span className="font-mono font-semibold">{playerMetrics.raptor > 0 ? '+' : ''}{playerMetrics.raptor.toFixed(1)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-sm">BPM</span>
                            <span className="font-mono font-semibold">{playerMetrics.bpm > 0 ? '+' : ''}{playerMetrics.bpm.toFixed(1)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-sm">VORP</span>
                            <span className="font-mono font-semibold">{playerMetrics.vorp.toFixed(1)}</span>
                          </div>
                        </div>
                      </div>

                      <div className="space-y-4">
                        <h4 className="font-semibold text-sm text-muted-foreground">WIN CONTRIBUTION</h4>
                        <div className="space-y-3">
                          <div className="flex justify-between">
                            <span className="text-sm">Win Shares</span>
                            <span className="font-mono font-semibold">{playerMetrics.winShares.toFixed(1)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-sm">WS/48</span>
                            <span className="font-mono font-semibold">{playerMetrics.winSharesPer48.toFixed(3)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-sm">Def WS</span>
                            <span className="font-mono font-semibold">{playerMetrics.defWinShares.toFixed(1)}</span>
                          </div>
                        </div>
                      </div>

                      <div className="space-y-4">
                        <h4 className="font-semibold text-sm text-muted-foreground">EFFICIENCY</h4>
                        <div className="space-y-3">
                          <div className="flex justify-between">
                            <span className="text-sm">TS%</span>
                            <span className="font-mono font-semibold">{(playerMetrics.trueShooting * 100).toFixed(1)}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-sm">eFG%</span>
                            <span className="font-mono font-semibold">{(playerMetrics.effectiveFieldGoal * 100).toFixed(1)}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-sm">Usage</span>
                            <span className="font-mono font-semibold">{playerMetrics.usage.toFixed(1)}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-sm">PIE</span>
                            <span className="font-mono font-semibold">{playerMetrics.pie.toFixed(1)}%</span>
                  </div>
                </div>
              </div>

                      <div className="space-y-4">
                        <h4 className="font-semibold text-sm text-muted-foreground">SHOT CREATION</h4>
                        <div className="space-y-3">
                          <div className="flex justify-between">
                            <span className="text-sm">Shot Quality</span>
                            <span className="font-mono font-semibold">{playerMetrics.shotQuality.toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-sm">Self Created</span>
                            <span className="font-mono font-semibold">{(playerMetrics.shotCreation * 100).toFixed(1)}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-sm">Assisted FG</span>
                            <span className="font-mono font-semibold">{(playerMetrics.assistedFieldGoals * 100).toFixed(1)}%</span>
                          </div>
                        </div>
                </div>
                </div>
                  ) : null}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="skill_development" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5" />
                    Skill Development Trajectory
                  </CardTitle>
                  <CardDescription>
                    Year-over-year development across key skill areas
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {isLoadingSkills ? (
                    <Skeleton className="h-96 w-full" />
                  ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                          <TableHead>Season</TableHead>
                          <TableHead>Age</TableHead>
                          <TableHead className="text-center">3P%</TableHead>
                          <TableHead className="text-center">Mid-Range%</TableHead>
                          <TableHead className="text-center">Rim%</TableHead>
                          <TableHead className="text-center">FT%</TableHead>
                          <TableHead className="text-center">AST</TableHead>
                          <TableHead className="text-center">AST/TO</TableHead>
                          <TableHead className="text-center">Def Rtg</TableHead>
                          <TableHead className="text-center">Hustle</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                        {skillDevelopment.map((season) => (
                          <TableRow key={season.season}>
                            <TableCell className="font-medium">{season.season}</TableCell>
                            <TableCell>{season.age}</TableCell>
                            <TableCell className={`text-center font-mono ${getSkillColor(season.threePt, 'percentage')}`}>
                              {season.threePt.toFixed(1)}%
                            </TableCell>
                            <TableCell className={`text-center font-mono ${getSkillColor(season.midRange, 'percentage')}`}>
                              {season.midRange.toFixed(1)}%
                            </TableCell>
                            <TableCell className={`text-center font-mono ${getSkillColor(season.rim, 'percentage')}`}>
                              {season.rim.toFixed(1)}%
                            </TableCell>
                            <TableCell className={`text-center font-mono ${getSkillColor(season.freeThrow, 'percentage')}`}>
                              {season.freeThrow.toFixed(1)}%
                            </TableCell>
                            <TableCell className="text-center font-mono">
                              {season.assists.toFixed(1)}
                            </TableCell>
                            <TableCell className="text-center font-mono">
                              {season.assistToTurnover.toFixed(1)}
                            </TableCell>
                            <TableCell className={`text-center font-mono ${getSkillColor(season.defenseRating, 'rating')}`}>
                              {season.defenseRating.toFixed(1)}
                            </TableCell>
                            <TableCell className="text-center">
                              <Progress value={season.hustle} className="w-16 h-2" />
                            </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                  )}
                        </CardContent>
                    </Card>
            </TabsContent>

            <TabsContent value="shot_analysis" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Crosshair className="h-5 w-5" />
                    Shot Quality Analysis
                  </CardTitle>
                  <CardDescription>
                    Shot selection and efficiency by court zone
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {isLoadingShots ? (
                    <Skeleton className="h-96 w-full" />
                  ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                          <TableHead>Zone</TableHead>
                          <TableHead className="text-center">Frequency</TableHead>
                          <TableHead className="text-center">FG%</TableHead>
                          <TableHead className="text-center">Expected FG%</TableHead>
                          <TableHead className="text-center">Difference</TableHead>
                          <TableHead className="text-center">PPS</TableHead>
                          <TableHead className="text-center">Quality</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                        {shotAnalysis.map((shot) => (
                          <TableRow key={shot.zone}>
                            <TableCell className="font-medium">{shot.zone}</TableCell>
                            <TableCell className="text-center font-mono">
                              {shot.frequency.toFixed(1)}%
                            </TableCell>
                            <TableCell className="text-center font-mono">
                              {shot.percentage.toFixed(1)}%
                            </TableCell>
                            <TableCell className="text-center font-mono text-muted-foreground">
                              {shot.expectedPercentage.toFixed(1)}%
                            </TableCell>
                            <TableCell className="text-center font-mono">
                              <span className={shot.percentage > shot.expectedPercentage ? 'text-green-600' : 'text-red-600'}>
                                {shot.percentage > shot.expectedPercentage ? '+' : ''}
                                {(shot.percentage - shot.expectedPercentage).toFixed(1)}%
                              </span>
                            </TableCell>
                            <TableCell className="text-center font-mono">
                              {shot.pointsPerShot.toFixed(2)}
                            </TableCell>
                            <TableCell className="text-center">
                              {getQualityBadge(shot.quality)}
                            </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="comparisons" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Users className="h-5 w-5" />
                    Player Comparisons
                  </CardTitle>
                  <CardDescription>
                    AI-powered similar player analysis based on playstyle and impact
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {isLoadingComparisons ? (
                    <div className="space-y-4">
                      {[1, 2, 3].map((i) => (
                        <Skeleton key={i} className="h-24 w-full" />
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {similarPlayers.map((comp) => (
                        <Card key={comp.playerId} className="border-l-4 border-l-blue-400">
                          <CardContent className="pt-4">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-lg">{comp.playerName}</span>
                                <Badge variant="outline">{comp.teamAbbr}</Badge>
                                <div className="flex items-center gap-1">
                                  <Progress value={comp.similarityScore} className="w-16 h-2" />
                                  <span className="text-sm text-muted-foreground">{comp.similarityScore}%</span>
                                </div>
                              </div>
                            </div>
                            <p className="text-sm text-muted-foreground mb-3">{comp.reason}</p>
                            <div className="flex flex-wrap gap-2 mb-2">
                              <span className="text-xs font-medium">Similarities:</span>
                              {comp.strengthsInCommon.map((strength) => (
                                <Badge key={strength} variant="secondary" className="text-xs">
                                  {strength}
                                </Badge>
                              ))}
                            </div>
                            <div className="flex flex-wrap gap-2">
                              <span className="text-xs font-medium">Differences:</span>
                              {comp.differentiators.map((diff) => (
                                <Badge key={diff} variant="outline" className="text-xs">
                                  {diff}
                                </Badge>
                              ))}
                            </div>
                          </CardContent>
                        </Card>
                        ))}
                    </div>
                )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="injury_impact" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Activity className="h-5 w-5" />
                    Health & Injury Impact
                  </CardTitle>
                  <CardDescription>
                    Analysis of injury impact on performance and recovery projections
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {isLoadingInjury ? (
                    <Skeleton className="h-48 w-full" />
                  ) : injuryImpact ? (
                    <div className="space-y-6">
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="space-y-2">
                          <h4 className="font-semibold text-sm">Injury Details</h4>
                          <div className="text-sm">
                            <div className="flex justify-between">
                              <span>Type:</span>
                              <span className="font-medium">{injuryImpact.injuryType}</span>
                            </div>
                            <div className="flex justify-between">
                              <span>Games Affected:</span>
                              <span className="font-medium">{injuryImpact.gamesAffected}</span>
                            </div>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <h4 className="font-semibold text-sm">Performance Impact</h4>
                          <div className="text-sm space-y-1">
                            <div className="flex justify-between">
                              <span>PPG Change:</span>
                              <span className={`font-medium ${injuryImpact.postInjuryMetrics.ppg < injuryImpact.preInjuryMetrics.ppg ? 'text-red-600' : 'text-green-600'}`}>
                                {(injuryImpact.postInjuryMetrics.ppg - injuryImpact.preInjuryMetrics.ppg).toFixed(1)}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span>Efficiency Change:</span>
                              <span className={`font-medium ${injuryImpact.postInjuryMetrics.efficiency < injuryImpact.preInjuryMetrics.efficiency ? 'text-red-600' : 'text-green-600'}`}>
                                {((injuryImpact.postInjuryMetrics.efficiency - injuryImpact.preInjuryMetrics.efficiency) * 100).toFixed(1)}%
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span>Impact Change:</span>
                              <span className={`font-medium ${injuryImpact.postInjuryMetrics.impact < injuryImpact.preInjuryMetrics.impact ? 'text-red-600' : 'text-green-600'}`}>
                                {(injuryImpact.postInjuryMetrics.impact - injuryImpact.preInjuryMetrics.impact).toFixed(1)}
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <h4 className="font-semibold text-sm">Recovery Outlook</h4>
                          <p className="text-sm text-muted-foreground">{injuryImpact.recoveryProjection}</p>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <Activity className="h-12 w-12 text-muted-foreground mx-auto mb-2" />
                      <p className="text-muted-foreground">No significant injury impact detected</p>
                      <p className="text-sm text-muted-foreground">Player performance appears consistent with health expectations</p>
                    </div>
                  )}
                </CardContent>
          </Card>
            </TabsContent>
        </Tabs>
        </>
      )}

      {!selectedPlayer && searchQuery.length < 2 && (
        <Card>
          <CardContent className="text-center py-12">
            <Search className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">Search for a Player</h3>
            <p className="text-muted-foreground">
              Enter a player's name or team abbreviation to begin advanced analysis
            </p>
            </CardContent>
          </Card>
      )}
    </div>
  );
}

