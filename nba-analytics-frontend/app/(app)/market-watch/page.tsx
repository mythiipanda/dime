"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { 
  LineChart, Users, TrendingUp, DollarSign, ShieldAlert, BarChartHorizontalBig, 
  Percent, Brain, Target, Award, AlertTriangle, Filter, Search, Star,
  TrendingDown, CheckCircle, Clock, Zap
} from "lucide-react";

// --- Existing Data Structures ---
interface GameOdds {
  gameId: string;
  homeTeamAbbr: string;
  awayTeamAbbr: string;
  gameTime: string;
  sportsbook: string;
  homeSpread: number;
  homeSpreadOdds: number;
  awaySpread: number;
  awaySpreadOdds: number;
  overUnder: number;
  overOdds: number;
  underOdds: number;
  homeMoneyline?: number;
  awayMoneyline?: number;
}

interface PlayerProp {
  playerId: string;
  playerName: string;
  teamAbbr: string;
  game: string;
  propType: "Points" | "Rebounds" | "Assists" | "3PM" | "PRA";
  line: number;
  overOdds: number;
  underOdds: number;
  sportsbook: string;
}

interface FantasyProjection {
  playerId: string;
  playerName: string;
  teamAbbr: string;
  position: string;
  opponent: string;
  salary: number;
  projection: number;
  source: string;
}

// --- New Free Agent Analysis Data Structures ---
interface FreeAgent {
  playerId: string;
  playerName: string;
  age: number;
  position: string;
  lastTeam: string;
  experienceYears: number;
  
  // Performance Metrics (from player_estimated_metrics.py, player_aggregate_stats.py)
  lastSeasonStats: {
    ppg: number;
    rpg: number;
    apg: number;
    fg_pct: number;
    three_pt_pct: number;
    ft_pct: number;
    ts_pct: number;
    per: number;
    ws: number;
    bpm: number;
    vorp: number;
  };
  
  // Advanced Metrics
  estimatedMetrics: {
    offRating: number;
    defRating: number;
    netRating: number;
    impact: number; // Overall impact score
  };
  
  // Contract Information (from contracts_data.py)
  contractHistory: {
    lastSalary: number;
    lastContractYears: number;
    totalCareerEarnings: number;
  };
  
  // Market Projections (AI-driven)
  marketProjection: {
    minSalary: number;
    maxSalary: number;
    likelySalary: number;
    contractYears: number;
    marketTier: 'Elite' | 'Starter' | 'Role Player' | 'Minimum' | 'Veteran Minimum';
    confidence: number; // 0-100
  };
  
  // Team Fit Analysis
  teamFitScores: Array<{
    teamAbbr: string;
    fitScore: number; // 0-100
    projectedRole: string;
    reasoning: string;
  }>;
  
  // Health & Risk Factors
  riskProfile: {
    injuryHistory: string[];
    ageRisk: 'Low' | 'Medium' | 'High';
    durabilityScore: number; // 0-100
    upside: 'Limited' | 'Moderate' | 'High' | 'Elite';
  };
}

interface AIMarketInsight {
  id: string;
  type: 'prediction' | 'analysis' | 'opportunity' | 'risk';
  priority: 'high' | 'medium' | 'low';
  title: string;
  summary: string;
  confidence: number;
  playersInvolved: string[];
  teamsInvolved: string[];
  timestamp: string;
}

interface ContractComparable {
  playerName: string;
  teamSigned: string;
  contract: {
    totalValue: number;
    years: number;
    avgPerYear: number;
  };
  signingYear: number;
  statsAtSigning: {
    age: number;
    ppg: number;
    efficiency: number;
  };
  similarity: number; // 0-100
}

// --- Mock API Functions ---
const mockGameOddsAPI = async (sportsbook: string): Promise<GameOdds[]> => {
    console.log(`Fetching Game Odds from: ${sportsbook}`);
    await new Promise(resolve => setTimeout(resolve, 600));
    return [
        { gameId: "G1_Odds", homeTeamAbbr: "BOS", awayTeamAbbr: "LAL", gameTime: "7:00 PM EST", sportsbook, homeSpread: -7.5, homeSpreadOdds: -110, awaySpread: 7.5, awaySpreadOdds: -110, overUnder: 225.5, overOdds: -110, underOdds: -110, homeMoneyline: -300, awayMoneyline: 240 },
        { gameId: "G2_Odds", homeTeamAbbr: "GSW", awayTeamAbbr: "DEN", gameTime: "7:30 PM EST", sportsbook, homeSpread: -2.0, homeSpreadOdds: -105, awaySpread: 2.0, awaySpreadOdds: -115, overUnder: 230.0, overOdds: -110, underOdds: -110, homeMoneyline: -130, awayMoneyline: 110 },
        { gameId: "G3_Odds", homeTeamAbbr: "MIL", awayTeamAbbr: "PHI", gameTime: "8:00 PM EST", sportsbook, homeSpread: -5.0, homeSpreadOdds: -110, awaySpread: 5.0, awaySpreadOdds: -110, overUnder: 218.5, overOdds: -105, underOdds: -115 },
    ];
};

const mockPlayerPropsAPI = async (propType: string): Promise<PlayerProp[]> => {
    console.log(`Fetching Player Props for: ${propType}`);
    await new Promise(resolve => setTimeout(resolve, 500));
    return [
        { playerId: "P1", playerName: "LeBron James", teamAbbr: "LAL", game: "LAL @ BOS", propType: "Points" as PlayerProp['propType'], line: 27.5, overOdds: -115, underOdds: -105, sportsbook: "DraftKings" },
        { playerId: "P2", playerName: "Nikola Jokic", teamAbbr: "DEN", game: "DEN @ GSW", propType: "Rebounds" as PlayerProp['propType'], line: 13.5, overOdds: -120, underOdds: 100, sportsbook: "FanDuel" },
        { playerId: "P3", playerName: "Jayson Tatum", teamAbbr: "BOS", game: "BOS vs LAL", propType: "Assists" as PlayerProp['propType'], line: 5.5, overOdds: -110, underOdds: -110, sportsbook: "BetMGM" },
        { playerId: "P4", playerName: "Stephen Curry", teamAbbr: "GSW", game: "GSW vs DEN", propType: "3PM" as PlayerProp['propType'], line: 4.5, overOdds: -105, underOdds: -115, sportsbook: "DraftKings" },
    ].filter(p => propType === "All" || p.propType === propType);
};

const mockFantasyProjectionsAPI = async (source: string): Promise<FantasyProjection[]> => {
    console.log(`Fetching Fantasy Projections from: ${source}`);
    await new Promise(resolve => setTimeout(resolve, 700));
    return [
        { playerId: "FP1", playerName: "Luka Doncic", teamAbbr: "DAL", position: "PG", opponent: "@ PHX", salary: 11500, projection: 58.5, source },
        { playerId: "FP2", playerName: "Giannis Antetokounmpo", teamAbbr: "MIL", position: "PF", opponent: "vs PHI", salary: 11200, projection: 55.2, source },
        { playerId: "FP3", playerName: "Kevin Durant", teamAbbr: "PHX", position: "SF", opponent: "vs DAL", salary: 9800, projection: 48.9, source },
        { playerId: "FP4", playerName: "Tyrese Haliburton", teamAbbr: "IND", position: "PG", opponent: "@ CLE", salary: 9500, projection: 47.5, source },
    ];
};

// --- Mock API Functions for Free Agent Analysis ---
const mockFreeAgentsAPI = async (filters: { position?: string; maxAge?: number; minImpact?: number }): Promise<FreeAgent[]> => {
  await new Promise(resolve => setTimeout(resolve, 800));
  
  const allFreeAgents: FreeAgent[] = [
    {
      playerId: "FA1",
      playerName: "Paul George",
      age: 34,
      position: "SF/PF",
      lastTeam: "LAC",
      experienceYears: 14,
      lastSeasonStats: { ppg: 22.6, rpg: 5.2, apg: 3.5, fg_pct: 0.473, three_pt_pct: 0.412, ft_pct: 0.906, ts_pct: 0.611, per: 19.5, ws: 6.8, bpm: 3.2, vorp: 2.1 },
      estimatedMetrics: { offRating: 118.2, defRating: 110.8, netRating: 7.4, impact: 4.2 },
      contractHistory: { lastSalary: 48787676, lastContractYears: 4, totalCareerEarnings: 291000000 },
      marketProjection: { minSalary: 35000000, maxSalary: 50000000, likelySalary: 42000000, contractYears: 3, marketTier: 'Elite', confidence: 87 },
      teamFitScores: [
        { teamAbbr: "PHI", fitScore: 92, projectedRole: "Secondary Star", reasoning: "Perfect wing complement to Embiid, championship window alignment" },
        { teamAbbr: "ORL", fitScore: 88, projectedRole: "Primary Option", reasoning: "Young core needs veteran leadership, ample cap space" },
        { teamAbbr: "LAC", fitScore: 85, projectedRole: "Franchise Player", reasoning: "Familiar system but aging core concerns" }
      ],
      riskProfile: { injuryHistory: ["Shoulder (2022)", "Knee (2021)"], ageRisk: 'High', durabilityScore: 68, upside: 'Moderate' }
    },
    {
      playerId: "FA2", 
      playerName: "Klay Thompson",
      age: 34,
      position: "SG",
      lastTeam: "GSW",
      experienceYears: 13,
      lastSeasonStats: { ppg: 17.9, rpg: 3.3, apg: 2.3, fg_pct: 0.433, three_pt_pct: 0.387, ft_pct: 0.927, ts_pct: 0.567, per: 14.1, ws: 4.2, bpm: -0.8, vorp: 1.2 },
      estimatedMetrics: { offRating: 115.1, defRating: 114.2, netRating: 0.9, impact: 1.8 },
      contractHistory: { lastSalary: 43219440, lastContractYears: 5, totalCareerEarnings: 245000000 },
      marketProjection: { minSalary: 15000000, maxSalary: 25000000, likelySalary: 20000000, contractYears: 2, marketTier: 'Starter', confidence: 82 },
      teamFitScores: [
        { teamAbbr: "DAL", fitScore: 94, projectedRole: "3rd Option", reasoning: "Perfect fit alongside Luka/Kyrie, championship experience" },
        { teamAbbr: "LAL", fitScore: 89, projectedRole: "Starting SG", reasoning: "LeBron connection, playoff experience valuable" },
        { teamAbbr: "MIA", fitScore: 87, projectedRole: "Veteran Leader", reasoning: "Heat culture fit, reliable playoff performer" }
      ],
      riskProfile: { injuryHistory: ["ACL (2019)", "Achilles (2020)"], ageRisk: 'High', durabilityScore: 71, upside: 'Limited' }
    },
    {
      playerId: "FA3",
      playerName: "DeMar DeRozan", 
      age: 35,
      position: "SG/SF",
      lastTeam: "CHI",
      experienceYears: 15,
      lastSeasonStats: { ppg: 24.0, rpg: 4.3, apg: 5.3, fg_pct: 0.480, three_pt_pct: 0.333, ft_pct: 0.853, ts_pct: 0.563, per: 20.1, ws: 6.1, bpm: 2.8, vorp: 2.3 },
      estimatedMetrics: { offRating: 116.8, defRating: 115.2, netRating: 1.6, impact: 3.1 },
      contractHistory: { lastSalary: 27300000, lastContractYears: 3, totalCareerEarnings: 267000000 },
      marketProjection: { minSalary: 18000000, maxSalary: 28000000, likelySalary: 23000000, contractYears: 2, marketTier: 'Starter', confidence: 91 },
      teamFitScores: [
        { teamAbbr: "LAL", fitScore: 93, projectedRole: "Secondary Scorer", reasoning: "Clutch performer, proven with LeBron, playoff experience" },
        { teamAbbr: "SAC", fitScore: 88, projectedRole: "Primary Creator", reasoning: "Homecoming story, leadership for young core" },
        { teamAbbr: "MIA", fitScore: 85, projectedRole: "Veteran Scorer", reasoning: "Heat development system, playoff mentality" }
      ],
      riskProfile: { injuryHistory: ["Minor injuries only"], ageRisk: 'Medium', durabilityScore: 88, upside: 'Moderate' }
    },
    {
      playerId: "FA4",
      playerName: "Jonas Valanciunas",
      age: 32,
      position: "C",
      lastTeam: "NOP",
      experienceYears: 12,
      lastSeasonStats: { ppg: 12.2, rpg: 8.8, apg: 2.1, fg_pct: 0.555, three_pt_pct: 0.367, ft_pct: 0.738, ts_pct: 0.601, per: 18.9, ws: 7.2, bpm: 1.4, vorp: 1.8 },
      estimatedMetrics: { offRating: 119.2, defRating: 112.1, netRating: 7.1, impact: 2.8 },
      contractHistory: { lastSalary: 14700000, lastContractYears: 2, totalCareerEarnings: 142000000 },
      marketProjection: { minSalary: 12000000, maxSalary: 18000000, likelySalary: 15000000, contractYears: 3, marketTier: 'Role Player', confidence: 94 },
      teamFitScores: [
        { teamAbbr: "LAL", fitScore: 91, projectedRole: "Starting Center", reasoning: "Addresses size need, proven playoffs performer" },
        { teamAbbr: "GSW", fitScore: 87, projectedRole: "Traditional Big", reasoning: "Complements small-ball system, rebounding upgrade" },
        { teamAbbr: "PHX", fitScore: 84, projectedRole: "Veteran Presence", reasoning: "Championship experience, fits timeline" }
      ],
      riskProfile: { injuryHistory: ["Back issues (2020)"], ageRisk: 'Low', durabilityScore: 82, upside: 'Limited' }
    },
    {
      playerId: "FA5",
      playerName: "Gary Trent Jr.",
      age: 25,
      position: "SG",
      lastTeam: "TOR", 
      experienceYears: 6,
      lastSeasonStats: { ppg: 13.7, rpg: 2.6, apg: 1.7, fg_pct: 0.427, three_pt_pct: 0.393, ft_pct: 0.825, ts_pct: 0.576, per: 12.8, ws: 3.1, bpm: -1.2, vorp: 0.8 },
      estimatedMetrics: { offRating: 112.8, defRating: 113.9, netRating: -1.1, impact: 1.2 },
      contractHistory: { lastSalary: 18500000, lastContractYears: 1, totalCareerEarnings: 45000000 },
      marketProjection: { minSalary: 8000000, maxSalary: 15000000, likelySalary: 11000000, contractYears: 3, marketTier: 'Role Player', confidence: 76 },
      teamFitScores: [
        { teamAbbr: "LAL", fitScore: 89, projectedRole: "6th Man", reasoning: "Young shooting guard, room for development" },
        { teamAbbr: "ORL", fitScore: 86, projectedRole: "Starting SG", reasoning: "Fits young timeline, shooting specialist" },
        { teamAbbr: "DET", fitScore: 83, projectedRole: "Veteran Leader", reasoning: "Young team needs experienced guard" }
      ],
      riskProfile: { injuryHistory: ["Minor injuries"], ageRisk: 'Low', durabilityScore: 85, upside: 'Moderate' }
    }
  ];
  
  return allFreeAgents.filter(fa => {
    if (filters.position && !fa.position.includes(filters.position)) return false;
    if (filters.maxAge && fa.age > filters.maxAge) return false; 
    if (filters.minImpact && fa.estimatedMetrics.impact < filters.minImpact) return false;
    return true;
  });
};

const mockAIMarketInsightsAPI = async (): Promise<AIMarketInsight[]> => {
  await new Promise(resolve => setTimeout(resolve, 600));
  return [
    {
      id: "AI1",
      type: "prediction",
      priority: "high",
      title: "Paul George's Market Value Exceeding Expectations",
      summary: "Despite age concerns, PG's shooting efficiency and playoff experience are driving bidding wars. Expect $42M+ AAV, 24% above initial projections.",
      confidence: 89,
      playersInvolved: ["Paul George"],
      teamsInvolved: ["PHI", "ORL", "LAC"],
      timestamp: "2024-07-01T14:30:00Z"
    },
    {
      id: "AI2", 
      type: "opportunity",
      priority: "high",
      title: "Undervalued Veterans Creating Championship Windows",
      summary: "DeMar DeRozan and Jonas Valanciunas represent exceptional value for contenders. Their playoff experience and fit with star players suggest immediate impact potential.",
      confidence: 84,
      playersInvolved: ["DeMar DeRozan", "Jonas Valanciunas"],
      teamsInvolved: ["LAL", "MIA", "PHX"],
      timestamp: "2024-07-01T12:15:00Z"
    },
    {
      id: "AI3",
      type: "risk",
      priority: "medium", 
      title: "Injury History Impacting Long-term Deals",
      summary: "Teams showing hesitation on multi-year deals for Klay Thompson due to injury history. Market leaning toward 2-year prove-it contracts despite shooting pedigree.",
      confidence: 78,
      playersInvolved: ["Klay Thompson"],
      teamsInvolved: ["DAL", "LAL", "GSW"],
      timestamp: "2024-07-01T10:45:00Z"
    }
  ];
};

const mockContractComparablesAPI = async (playerId: string): Promise<ContractComparable[]> => {
  await new Promise(resolve => setTimeout(resolve, 400));
  
  const comparables: Record<string, ContractComparable[]> = {
    "FA1": [ // Paul George
      { playerName: "Kawhi Leonard", teamSigned: "LAC", contract: { totalValue: 176000000, years: 4, avgPerYear: 44000000 }, signingYear: 2021, statsAtSigning: { age: 30, ppg: 24.8, efficiency: 0.588 }, similarity: 91 },
      { playerName: "Jimmy Butler", teamSigned: "MIA", contract: { totalValue: 184000000, years: 4, avgPerYear: 46000000 }, signingYear: 2021, statsAtSigning: { age: 32, ppg: 21.5, efficiency: 0.581 }, similarity: 87 }
    ],
    "FA2": [ // Klay Thompson
      { playerName: "Joe Harris", teamSigned: "BRK", contract: { totalValue: 75000000, years: 4, avgPerYear: 18750000 }, signingYear: 2021, statsAtSigning: { age: 29, ppg: 14.1, efficiency: 0.618 }, similarity: 84 },
      { playerName: "Duncan Robinson", teamSigned: "MIA", contract: { totalValue: 90000000, years: 5, avgPerYear: 18000000 }, signingYear: 2021, statsAtSigning: { age: 27, ppg: 13.1, efficiency: 0.648 }, similarity: 79 }
    ]
  };
  
  return comparables[playerId] || [];
};

export default function MarketWatchPage() {
  // Existing state
  const [oddsSportsbook, setOddsSportsbook] = useState("DraftKings");
  const [gameOdds, setGameOdds] = useState<GameOdds[]>([]);
  const [isLoadingOdds, setIsLoadingOdds] = useState(false);

  const [propTypeFilter, setPropTypeFilter] = useState("Points");
  const [playerProps, setPlayerProps] = useState<PlayerProp[]>([]);
  const [isLoadingProps, setIsLoadingProps] = useState(false);

  const [fantasySource, setFantasySource] = useState("DraftKings");
  const [fantasyProjections, setFantasyProjections] = useState<FantasyProjection[]>([]);
  const [isLoadingFantasy, setIsLoadingFantasy] = useState(false);

  // New Free Agent Analysis state
  const [freeAgents, setFreeAgents] = useState<FreeAgent[]>([]);
  const [filteredFreeAgents, setFilteredFreeAgents] = useState<FreeAgent[]>([]);
  const [aiMarketInsights, setAIMarketInsights] = useState<AIMarketInsight[]>([]);
  const [selectedFreeAgent, setSelectedFreeAgent] = useState<FreeAgent | null>(null);
  const [contractComparables, setContractComparables] = useState<ContractComparable[]>([]);
  const [isLoadingFreeAgents, setIsLoadingFreeAgents] = useState(false);
  const [isLoadingInsights, setIsLoadingInsights] = useState(false);
  
  // Free Agent filters
  const [positionFilter, setPositionFilter] = useState<string>("All");
  const [maxAgeFilter, setMaxAgeFilter] = useState<number>(40);
  const [minImpactFilter, setMinImpactFilter] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Existing useEffects
  useEffect(() => {
    const fetchOdds = async () => {
      setIsLoadingOdds(true);
      const data = await mockGameOddsAPI(oddsSportsbook);
      setGameOdds(data);
      setIsLoadingOdds(false);
    };
    fetchOdds();
  }, [oddsSportsbook]);

  useEffect(() => {
    const fetchProps = async () => {
      setIsLoadingProps(true);
      const data = await mockPlayerPropsAPI(propTypeFilter);
      setPlayerProps(data);
      setIsLoadingProps(false);
    };
    fetchProps();
  }, [propTypeFilter]);

  useEffect(() => {
    const fetchFantasy = async () => {
      setIsLoadingFantasy(true);
      const data = await mockFantasyProjectionsAPI(fantasySource);
      setFantasyProjections(data);
      setIsLoadingFantasy(false);
    };
    fetchFantasy();
  }, [fantasySource]);

  // New Free Agent Analysis useEffects
  useEffect(() => {
    const fetchFreeAgents = async () => {
      setIsLoadingFreeAgents(true);
      const filters = {
        position: positionFilter === "All" ? undefined : positionFilter,
        maxAge: maxAgeFilter,
        minImpact: minImpactFilter
      };
      const data = await mockFreeAgentsAPI(filters);
      setFreeAgents(data);
      setIsLoadingFreeAgents(false);
    };
    fetchFreeAgents();
  }, [positionFilter, maxAgeFilter, minImpactFilter]);

  useEffect(() => {
    const fetchInsights = async () => {
      setIsLoadingInsights(true);
      const data = await mockAIMarketInsightsAPI();
      setAIMarketInsights(data);
      setIsLoadingInsights(false);
    };
    fetchInsights();
  }, []);

  // Filter free agents by search query
  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredFreeAgents(freeAgents);
    } else {
      const filtered = freeAgents.filter(fa => 
        fa.playerName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        fa.position.toLowerCase().includes(searchQuery.toLowerCase()) ||
        fa.lastTeam.toLowerCase().includes(searchQuery.toLowerCase())
      );
      setFilteredFreeAgents(filtered);
    }
  }, [freeAgents, searchQuery]);

  // Helper functions
  const formatCurrency = (amount: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const getTierBadgeColor = (tier: string) => {
    switch (tier) {
      case 'Elite': return 'bg-purple-100 text-purple-800 border-purple-300';
      case 'Starter': return 'bg-blue-100 text-blue-800 border-blue-300';
      case 'Role Player': return 'bg-green-100 text-green-800 border-green-300';
      case 'Minimum': return 'bg-gray-100 text-gray-800 border-gray-300';
      case 'Veteran Minimum': return 'bg-orange-100 text-orange-800 border-orange-300';
      default: return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'Low': return 'text-green-600';
      case 'Medium': return 'text-yellow-600';
      case 'High': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const getInsightIcon = (type: string) => {
    switch (type) {
      case 'prediction': return <Brain className="h-4 w-4" />;
      case 'opportunity': return <Target className="h-4 w-4" />;
      case 'risk': return <AlertTriangle className="h-4 w-4" />;
      default: return <Zap className="h-4 w-4" />;
    }
  };

  const handleFreeAgentSelect = async (freeAgent: FreeAgent) => {
    setSelectedFreeAgent(freeAgent);
    const comparables = await mockContractComparablesAPI(freeAgent.playerId);
    setContractComparables(comparables);
  };

  return (
    <div className="flex-1 space-y-8 p-4 md:p-6 lg:p-8">
      <div className="flex items-center justify-between space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Market Watch</h1>
      </div>

      <Tabs defaultValue="game_odds" className="w-full">
        <TabsList className="grid w-full grid-cols-2 sm:grid-cols-4 gap-1 h-auto mb-6">
          <TabsTrigger value="game_odds" className="py-2 text-xs sm:text-sm">
            <DollarSign className="hidden sm:inline h-4 w-4 mr-1 sm:mr-2" />Game Lines
          </TabsTrigger>
          <TabsTrigger value="player_props" className="py-2 text-xs sm:text-sm">
            <Users className="hidden sm:inline h-4 w-4 mr-1 sm:mr-2" />Player Props
          </TabsTrigger>
          <TabsTrigger value="fantasy_intel" className="py-2 text-xs sm:text-sm">
            <TrendingUp className="hidden sm:inline h-4 w-4 mr-1 sm:mr-2" />Fantasy Intel
          </TabsTrigger>
          <TabsTrigger value="free_agents" className="py-2 text-xs sm:text-sm">
            <Brain className="hidden sm:inline h-4 w-4 mr-1 sm:mr-2" />Free Agent Intel
          </TabsTrigger>
        </TabsList>

        <TabsContent value="game_odds">
          <Card>
            <CardHeader>
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center">
                    <div>
                        <CardTitle>NBA Game Lines</CardTitle>
                        <CardDescription>Spreads, totals, and moneylines from leading sportsbooks.</CardDescription>
                    </div>
                     <Select value={oddsSportsbook} onValueChange={setOddsSportsbook}>
                        <SelectTrigger className="w-full sm:w-[180px] mt-2 sm:mt-0">
                            <SelectValue placeholder="Select Sportsbook" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="DraftKings">DraftKings</SelectItem>
                            <SelectItem value="FanDuel">FanDuel</SelectItem>
                            <SelectItem value="BetMGM">BetMGM</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </CardHeader>
            <CardContent>
              {isLoadingOdds ? (
                <Skeleton className="h-96 w-full" />
              ) : gameOdds.length > 0 ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="text-xs">
                        <TableHead className="min-w-[120px]">Matchup</TableHead>
                        <TableHead>Time</TableHead>
                        <TableHead className="text-center">Spread</TableHead>
                        <TableHead className="text-center">Total (O/U)</TableHead>
                        <TableHead className="text-center min-w-[150px]">Moneyline (H/A)</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {gameOdds.map((game) => (
                        <TableRow key={game.gameId} className="text-sm">
                          <TableCell className="font-medium">{game.awayTeamAbbr} @ {game.homeTeamAbbr}</TableCell>
                          <TableCell>{game.gameTime}</TableCell>
                          <TableCell className="text-center">
                            <div>{game.homeTeamAbbr} {game.homeSpread > 0 ? `+${game.homeSpread}` : game.homeSpread} ({game.homeSpreadOdds > 0 ? `+${game.homeSpreadOdds}`: game.homeSpreadOdds})</div>
                            <div>{game.awayTeamAbbr} {game.awaySpread > 0 ? `+${game.awaySpread}`: game.awaySpread} ({game.awaySpreadOdds > 0 ? `+${game.awaySpreadOdds}`: game.awaySpreadOdds})</div>
                          </TableCell>
                          <TableCell className="text-center">
                            <div>O {game.overUnder} ({game.overOdds > 0 ? `+${game.overOdds}`: game.overOdds})</div>
                            <div>U {game.overUnder} ({game.underOdds > 0 ? `+${game.underOdds}`: game.underOdds})</div>
                          </TableCell>
                          <TableCell className="text-center">
                            {game.homeMoneyline && game.awayMoneyline ? 
                                `${game.homeMoneyline > 0 ? `+${game.homeMoneyline}`: game.homeMoneyline} / ${game.awayMoneyline > 0 ? `+${game.awayMoneyline}`: game.awayMoneyline}` 
                                : 'N/A'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <p className="text-muted-foreground text-center py-10">No game odds available for {oddsSportsbook}.</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="player_props">
          <Card>
            <CardHeader>
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center">
                    <div>
                        <CardTitle>Player Props Market</CardTitle>
                        <CardDescription>Popular player props and their odds.</CardDescription>
                    </div>
                    <Select value={propTypeFilter} onValueChange={setPropTypeFilter}>
                        <SelectTrigger className="w-full sm:w-[180px] mt-2 sm:mt-0">
                            <SelectValue placeholder="Select Prop Type" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="Points">Points</SelectItem>
                            <SelectItem value="Rebounds">Rebounds</SelectItem>
                            <SelectItem value="Assists">Assists</SelectItem>
                            <SelectItem value="3PM">3-Pointers Made</SelectItem>
                            <SelectItem value="PRA">Pts+Reb+Ast</SelectItem>
                            <SelectItem value="All">All Props</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </CardHeader>
            <CardContent>
              {isLoadingProps ? (
                <Skeleton className="h-96 w-full" />
              ) : playerProps.length > 0 ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="text-xs">
                        <TableHead className="min-w-[150px]">Player</TableHead>
                        <TableHead>Team</TableHead>
                        <TableHead>Game</TableHead>
                        <TableHead>Prop</TableHead>
                        <TableHead className="text-center">Line</TableHead>
                        <TableHead className="text-center">Over</TableHead>
                        <TableHead className="text-center">Under</TableHead>
                        <TableHead>Book</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {playerProps.map((prop) => (
                        <TableRow key={`${prop.playerId}-${prop.propType}-${prop.sportsbook}`} className="text-sm">
                          <TableCell className="font-medium">{prop.playerName}</TableCell>
                          <TableCell>{prop.teamAbbr}</TableCell>
                          <TableCell>{prop.game}</TableCell>
                          <TableCell>{prop.propType}</TableCell>
                          <TableCell className="text-center font-semibold">{prop.line}</TableCell>
                          <TableCell className="text-center">{prop.overOdds > 0 ? `+${prop.overOdds}`: prop.overOdds}</TableCell>
                          <TableCell className="text-center">{prop.underOdds > 0 ? `+${prop.underOdds}`: prop.underOdds}</TableCell>
                          <TableCell>{prop.sportsbook}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <p className="text-muted-foreground text-center py-10">No player props available for this filter.</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="fantasy_intel">
          <Card>
            <CardHeader>
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center">
                    <div>
                        <CardTitle>Daily Fantasy Projections</CardTitle>
                        <CardDescription>Player projections for popular DFS platforms.</CardDescription>
                    </div>
                    <Select value={fantasySource} onValueChange={setFantasySource}>
                        <SelectTrigger className="w-full sm:w-[180px] mt-2 sm:mt-0">
                            <SelectValue placeholder="Select DFS Source" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="DraftKings">DraftKings</SelectItem>
                            <SelectItem value="FanDuel">FanDuel</SelectItem>
                            <SelectItem value="Yahoo">Yahoo Fantasy</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </CardHeader>
            <CardContent>
              {isLoadingFantasy ? (
                <Skeleton className="h-96 w-full" />
              ) : fantasyProjections.length > 0 ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="text-xs">
                        <TableHead className="min-w-[150px]">Player</TableHead>
                        <TableHead>Pos</TableHead>
                        <TableHead>Team</TableHead>
                        <TableHead>Opp</TableHead>
                        <TableHead className="text-right">Salary</TableHead>
                        <TableHead className="text-right">Projection</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {fantasyProjections.map((player) => (
                        <TableRow key={`${player.playerId}-${player.source}`} className="text-sm">
                          <TableCell className="font-medium">{player.playerName}</TableCell>
                          <TableCell>{player.position}</TableCell>
                          <TableCell>{player.teamAbbr}</TableCell>
                          <TableCell>{player.opponent}</TableCell>
                          <TableCell className="text-right">${player.salary.toLocaleString()}</TableCell>
                          <TableCell className="text-right font-semibold">{player.projection.toFixed(1)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <p className="text-muted-foreground text-center py-10">No fantasy projections available for {fantasySource}.</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="free_agents">
          <div className="space-y-6">
            {/* AI Market Insights Section */}
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Brain className="h-5 w-5" />
                  <CardTitle>Dime's Market Intelligence</CardTitle>
                </div>
                <CardDescription>
                  AI-powered analysis of free agent market trends and opportunities
                </CardDescription>
              </CardHeader>
              <CardContent>
                {isLoadingInsights ? (
                  <div className="space-y-4">
                    {[1, 2, 3].map((i) => (
                      <Skeleton key={i} className="h-20 w-full" />
                    ))}
                  </div>
                ) : (
                  <div className="space-y-4">
                    {aiMarketInsights.map((insight) => (
                      <Card key={insight.id} className="border-l-4 border-l-primary">
                        <CardContent className="pt-4">
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2">
                              {getInsightIcon(insight.type)}
                              <Badge variant={insight.priority === 'high' ? 'destructive' : insight.priority === 'medium' ? 'default' : 'secondary'}>
                                {insight.priority.toUpperCase()}
                              </Badge>
                              <Badge variant="outline" className="text-xs">
                                {insight.type}
                              </Badge>
                            </div>
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                              <span>{insight.confidence}% confidence</span>
                            </div>
                          </div>
                          <h4 className="font-semibold mb-2">{insight.title}</h4>
                          <p className="text-sm text-muted-foreground mb-3">{insight.summary}</p>
                          <div className="flex items-center justify-between">
                            <div className="flex gap-2">
                              {insight.playersInvolved.map((player) => (
                                <Badge key={player} variant="secondary" className="text-xs">
                                  {player}
                                </Badge>
                              ))}
                              {insight.teamsInvolved.map((team) => (
                                <Badge key={team} variant="outline" className="text-xs">
                                  {team}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Free Agent Database */}
            <Card>
              <CardHeader>
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Users className="h-5 w-5" />
                      Free Agent Database
                    </CardTitle>
                    <CardDescription>
                      Advanced analytics and projections for available players
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2 w-full sm:w-auto">
                    <div className="relative flex-1 sm:flex-none">
                      <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                      <Input
                        placeholder="Search players..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-8 w-full sm:w-[200px]"
                      />
                    </div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 mt-4">
                  <Select value={positionFilter} onValueChange={setPositionFilter}>
                    <SelectTrigger className="w-[120px]">
                      <SelectValue placeholder="Position" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="All">All Positions</SelectItem>
                      <SelectItem value="PG">Point Guard</SelectItem>
                      <SelectItem value="SG">Shooting Guard</SelectItem>
                      <SelectItem value="SF">Small Forward</SelectItem>
                      <SelectItem value="PF">Power Forward</SelectItem>
                      <SelectItem value="C">Center</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={maxAgeFilter.toString()} onValueChange={(value) => setMaxAgeFilter(parseInt(value))}>
                    <SelectTrigger className="w-[120px]">
                      <SelectValue placeholder="Max Age" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="25">Under 25</SelectItem>
                      <SelectItem value="30">Under 30</SelectItem>
                      <SelectItem value="35">Under 35</SelectItem>
                      <SelectItem value="40">All Ages</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardHeader>
              <CardContent>
                {isLoadingFreeAgents ? (
                  <Skeleton className="h-96 w-full" />
                ) : (
                  <div className="space-y-4">
                    {filteredFreeAgents.map((player) => (
                      <Card 
                        key={player.playerId} 
                        className="cursor-pointer hover:shadow-md transition-shadow border-l-4 border-l-blue-500"
                        onClick={() => handleFreeAgentSelect(player)}
                      >
                        <CardContent className="pt-4">
                          <div className="flex flex-col lg:flex-row justify-between gap-4">
                            {/* Player Info */}
                            <div className="flex items-center gap-4">
                              <Avatar className="h-12 w-12">
                                <AvatarFallback className="bg-primary/10">
                                  {player.playerName.split(' ').map(n => n[0]).join('')}
                                </AvatarFallback>
                              </Avatar>
                              <div>
                                <h3 className="font-semibold text-lg">{player.playerName}</h3>
                                <p className="text-sm text-muted-foreground">
                                  {player.position} • Age {player.age} • {player.experienceYears} years exp.
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  Last team: {player.lastTeam}
                                </p>
                              </div>
                            </div>

                            {/* Key Stats */}
                            <div className="flex flex-wrap gap-4 lg:gap-6">
                              <div className="text-center">
                                <p className="text-xl font-bold">{player.lastSeasonStats.ppg}</p>
                                <p className="text-xs text-muted-foreground">PPG</p>
                              </div>
                              <div className="text-center">
                                <p className="text-xl font-bold">{player.lastSeasonStats.ts_pct.toFixed(1)}%</p>
                                <p className="text-xs text-muted-foreground">TS%</p>
                              </div>
                              <div className="text-center">
                                <p className="text-xl font-bold">{player.estimatedMetrics.impact.toFixed(1)}</p>
                                <p className="text-xs text-muted-foreground">Impact</p>
                              </div>
                            </div>

                            {/* Market Projection */}
                            <div className="text-right">
                              <div className="flex flex-col items-end gap-1">
                                <Badge className={getTierBadgeColor(player.marketProjection.marketTier)}>
                                  {player.marketProjection.marketTier}
                                </Badge>
                                <p className="font-semibold">
                                  {formatCurrency(player.marketProjection.likelySalary)}/yr
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  {player.marketProjection.contractYears} years
                                </p>
                                <div className="flex items-center gap-1">
                                  <span className="text-xs text-muted-foreground">Confidence:</span>
                                  <span className="text-xs font-medium">{player.marketProjection.confidence}%</span>
                                </div>
                              </div>
                            </div>
                          </div>

                          {/* Team Fit Preview */}
                          <div className="mt-4 pt-4 border-t">
                            <p className="text-sm font-medium mb-2">Best Team Fits:</p>
                            <div className="flex gap-2">
                              {player.teamFitScores.slice(0, 3).map((fit) => (
                                <Badge key={fit.teamAbbr} variant="outline" className="text-xs">
                                  {fit.teamAbbr} ({fit.fitScore}%)
                                </Badge>
                              ))}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Selected Player Deep Dive */}
            {selectedFreeAgent && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Target className="h-5 w-5" />
                    Deep Dive: {selectedFreeAgent.playerName}
                  </CardTitle>
                  <CardDescription>
                    Comprehensive analysis and team fit projections
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Performance Analysis */}
                    <div className="space-y-4">
                      <h4 className="font-semibold">Performance Metrics</h4>
                      <div className="grid grid-cols-2 gap-4">
                        <Card className="p-4">
                          <div className="text-center">
                            <p className="text-2xl font-bold">{selectedFreeAgent.lastSeasonStats.per}</p>
                            <p className="text-sm text-muted-foreground">PER</p>
                          </div>
                        </Card>
                        <Card className="p-4">
                          <div className="text-center">
                            <p className="text-2xl font-bold">{selectedFreeAgent.lastSeasonStats.bpm.toFixed(1)}</p>
                            <p className="text-sm text-muted-foreground">BPM</p>
                          </div>
                        </Card>
                        <Card className="p-4">
                          <div className="text-center">
                            <p className="text-2xl font-bold">{selectedFreeAgent.lastSeasonStats.vorp.toFixed(1)}</p>
                            <p className="text-sm text-muted-foreground">VORP</p>
                          </div>
                        </Card>
                        <Card className="p-4">
                          <div className="text-center">
                            <p className="text-2xl font-bold">{selectedFreeAgent.estimatedMetrics.netRating.toFixed(1)}</p>
                            <p className="text-sm text-muted-foreground">Net Rating</p>
                          </div>
                        </Card>
                      </div>

                      {/* Risk Profile */}
                      <div>
                        <h4 className="font-semibold mb-2">Risk Assessment</h4>
                        <div className="space-y-2">
                          <div className="flex justify-between">
                            <span>Age Risk:</span>
                            <span className={getRiskColor(selectedFreeAgent.riskProfile.ageRisk)}>
                              {selectedFreeAgent.riskProfile.ageRisk}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span>Durability:</span>
                            <div className="flex items-center gap-2">
                              <Progress value={selectedFreeAgent.riskProfile.durabilityScore} className="w-16 h-2" />
                              <span className="text-sm">{selectedFreeAgent.riskProfile.durabilityScore}%</span>
                            </div>
                          </div>
                          <div className="flex justify-between">
                            <span>Upside:</span>
                            <span>{selectedFreeAgent.riskProfile.upside}</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Team Fit Analysis */}
                    <div className="space-y-4">
                      <h4 className="font-semibold">Team Fit Analysis</h4>
                      <div className="space-y-3">
                        {selectedFreeAgent.teamFitScores.map((fit) => (
                          <div key={fit.teamAbbr} className="p-3 border rounded-lg">
                            <div className="flex justify-between items-center mb-2">
                              <span className="font-medium">{fit.teamAbbr}</span>
                              <div className="flex items-center gap-2">
                                <Progress value={fit.fitScore} className="w-20 h-2" />
                                <span className="text-sm font-medium">{fit.fitScore}%</span>
                              </div>
                            </div>
                            <p className="text-sm text-muted-foreground mb-1">
                              Role: {fit.projectedRole}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {fit.reasoning}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Contract Comparables */}
                  {contractComparables.length > 0 && (
                    <div className="mt-6 pt-6 border-t">
                      <h4 className="font-semibold mb-4">Contract Comparables</h4>
                      <div className="overflow-x-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Player</TableHead>
                              <TableHead>Team</TableHead>
                              <TableHead>Contract</TableHead>
                              <TableHead>Year</TableHead>
                              <TableHead>Age at Signing</TableHead>
                              <TableHead>Similarity</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {contractComparables.map((comp, idx) => (
                              <TableRow key={idx}>
                                <TableCell className="font-medium">{comp.playerName}</TableCell>
                                <TableCell>{comp.teamSigned}</TableCell>
                                <TableCell>
                                  <div>
                                    <p className="font-medium">{formatCurrency(comp.contract.totalValue)}</p>
                                    <p className="text-xs text-muted-foreground">
                                      {comp.contract.years} years • {formatCurrency(comp.contract.avgPerYear)}/yr
                                    </p>
                                  </div>
                                </TableCell>
                                <TableCell>{comp.signingYear}</TableCell>
                                <TableCell>{comp.statsAtSigning.age}</TableCell>
                                <TableCell>
                                  <div className="flex items-center gap-2">
                                    <Progress value={comp.similarity} className="w-16 h-2" />
                                    <span className="text-sm">{comp.similarity}%</span>
                                  </div>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
} 