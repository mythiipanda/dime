"use client";

import React, { useState, useEffect, useCallback } from 'react';
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, BarChart, Bar,
  ScatterChart, Scatter, Cell,
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis
} from 'recharts';
import {
  Search, UserCircle, BarChart3, TrendingUp, Target, ListFilter, Users, SlidersHorizontal, BotMessageSquare, Brain, Info
} from "lucide-react";
import { Separator } from '@/components/ui/separator';
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

interface Player { id: string; name: string; }
interface PlayerBio {
  id: string; name: string; team: string; position: string; jersey: string;
  height: string; weight: string; dob: string; age?: number; experience?: string;
  college: string; draftInfo: string; imageUrl?: string; contractInfo?: string;
}
interface PlayerGameLog { game_id: string; game_date: string; matchup: string; wl: string; min: number; pts: number; reb: number; ast: number; stl: number; blk: number; fgm: number; fga: number; fg_pct: number; fg3m: number; fg3a: number; fg3_pct: number; ftm: number; fta: number; ft_pct: number; oreb: number; dreb: number; pf: number; plus_minus: number; }
interface PlayerAdvancedStat { metric: string; value: string | number; percentile?: number; description?: string; }
interface Shot { x: number; y: number; made: boolean; shot_zone_basic: string; shot_zone_area: string; shot_distance: number; event_type?: string; }

// --- Start of NEW Advanced Data Structures ---
interface SynergyPlayType {
  playType: string;
  teamAbbreviation?: string; // Optional, if data is team-specific for the player
  frequencyPct: number;
  ppp: number; // Points Per Possession
  rankPPP?: number; // Percentile or rank for PPP
  fgPct: number;
  ftFreqPct?: number; // Free throw frequency
  sfFreqPct?: number; // Shooting foul frequency
  plusOneFreqPct?: number; // And-one frequency
  scoreFreqPct?: number; // Scoring frequency
  possCount?: number; // Total possessions for this play type
}

interface OnOffImpactStat {
  category: string; // e.g., "Team Performance", "Opponent Performance"
  metric: string; // e.g., "Offensive Rating", "Defensive Rating", "Net Rating", "eFG%", "TOV%", "Pace"
  onCourt: string | number;
  offCourt: string | number;
  difference: string | number; // Calculated: onCourt - offCourt
}

// Expanded PlayerAdvancedStat to include more common advanced metrics
// No change needed here if we add new metric keys directly to the existing interface string literal type for `metric`
// --- End of NEW Advanced Data Structures ---

// --- End of placeholder types and data ---

const searchPlayersAPI = async (query: string): Promise<Player[]> => {
  console.log(`Searching for: ${query}`);
  await new Promise(resolve => setTimeout(resolve, 300));
  if (query.toLowerCase().includes("lebron")) return [{ id: "2544", name: "LeBron James" }];
  if (query.toLowerCase().includes("curry")) return [{ id: "201939", name: "Stephen Curry" }];
  if (query.toLowerCase().includes("jokic")) return [{ id: "203999", name: "Nikola Jokic" }];
  return [];
};

const getPlayerBioAPI = async (playerId: string): Promise<PlayerBio | null> => {
  console.log(`Fetching bio for: ${playerId}`);
  await new Promise(resolve => setTimeout(resolve, 500));
  if (playerId === "2544") return {
    id: "2544", name: "LeBron James", team: "Los Angeles Lakers (LAL)", position: "Forward", jersey: "23",
    height: "6'9\"", weight: "250 lbs", dob: "Dec 30, 1984", age: 39, experience: "21 seasons",
    college: "St. Vincent-St. Mary HS (OH)", draftInfo: "2003 R1, Pick 1 (CLE)",
    imageUrl: "https://cdn.nba.com/headshots/nba/latest/1040x760/2544.png",
    contractInfo: "2 years / $99.02M"
  };
  return null;
};

const getPlayerGameLogsAPI = async (playerId: string, season: string): Promise<PlayerGameLog[]> => {
  console.log(`Fetching game logs for: ${playerId}, season: ${season}`);
  await new Promise(resolve => setTimeout(resolve, 600));
  return [
    { game_id: "0022300100", game_date: "2023-11-10", matchup: "LAL vs. PHX", wl: "W", min: 35, pts: 28, reb: 10, ast: 8, stl: 1, blk: 0, fgm: 10, fga: 20, fg_pct: 0.500, fg3m: 2, fg3a: 5, fg3_pct: 0.400, ftm: 6, fta: 7, ft_pct: 0.857, oreb: 2, dreb: 8, pf: 3, plus_minus: 12 },
    { game_id: "0022300090", game_date: "2023-11-08", matchup: "LAL @ HOU", wl: "L", min: 32, pts: 22, reb: 7, ast: 5, stl: 0, blk: 1, fgm: 8, fga: 18, fg_pct: 0.444, fg3m: 1, fg3a: 6, fg3_pct: 0.167, ftm: 5, fta: 5, ft_pct: 1.000, oreb: 1, dreb: 6, pf: 2, plus_minus: -5 },
  ];
};

const getPlayerShotChartAPI = async (playerId: string, season: string): Promise<Shot[]> => {
    console.log(`Fetching shot chart for: ${playerId}, season: ${season}`);
    await new Promise(resolve => setTimeout(resolve, 700));
    return [
        { x: 0, y: 0, made: true, shot_zone_basic: "Restricted Area", shot_zone_area: "Center", shot_distance: 1, event_type: "Made Shot" },
        { x: 50, y: 140, made: false, shot_zone_basic: "Mid-Range", shot_zone_area: "Right Side(R)", shot_distance: 15, event_type: "Missed Shot" },
        { x: -220, y: 70, made: true, shot_zone_basic: "Above the Break 3", shot_zone_area: "Left Side Center(LC)", shot_distance: 23, event_type: "Made Shot" },
    ];
};

const getPlayerAdvancedStatsAPI = async (playerId: string, season: string): Promise<PlayerAdvancedStat[]> => {
    console.log(`Fetching advanced stats for: ${playerId}, season: ${season}`);
    await new Promise(resolve => setTimeout(resolve, 400));
    // Ensure consistent metric names for radar chart mapping
    return [
        { metric: "PER", value: 25.5, percentile: 90, description: "Player Efficiency Rating" },
        { metric: "TS%", value: 0.602, percentile: 85, description: "True Shooting Percentage" }, // Store as decimal for radar
        { metric: "USG%", value: 30.1, percentile: 92, description: "Usage Percentage" }, // Store as raw value for radar
        { metric: "AST_Ratio", value: 18.5, percentile: 80, description: "Assist Ratio (AST per 100 poss for player)" }, // Renamed for consistency
        { metric: "REB_PCT", value: 10.2, percentile: 70, description: "Rebound Percentage" }, // Store as raw value
        { metric: "NetRtg_Est", value: 10.1, percentile: 90, description: "Estimated Net Rating" }, // Renamed for consistency
        // Non-radar stats (can still be displayed as cards)
        { metric: "E_OFF_RATING", value: 115.2, percentile: 88, description: "Estimated Offensive Rating" },
        { metric: "E_DEF_RATING", value: 105.1, percentile: 75, description: "Estimated Defensive Rating" },
        { metric: "PIE", value: 15.5, percentile: 85, description: "Player Impact Estimate (%)" }, // Store as raw value
    ];
};

const getPlayerSynergyStatsAPI = async (playerId: string, season: string): Promise<SynergyPlayType[]> => {
    console.log(`Fetching Synergy stats for: ${playerId}, season: ${season}`);
    await new Promise(resolve => setTimeout(resolve, 550));
    if (playerId === "2544") {
        return [
            { playType: "Transition", frequencyPct: 22.5, ppp: 1.15, fgPct: 0.58, rankPPP: 75, possCount: 150 },
            { playType: "PnR Ball Handler", frequencyPct: 25.0, ppp: 0.98, fgPct: 0.47, rankPPP: 65, possCount: 180 },
            { playType: "Isolation", frequencyPct: 15.0, ppp: 0.92, fgPct: 0.45, rankPPP: 60, possCount: 100 },
            { playType: "Post Up", frequencyPct: 10.5, ppp: 1.05, fgPct: 0.52, rankPPP: 70, possCount: 70 },
            { playType: "Spot Up", frequencyPct: 12.0, ppp: 1.10, fgPct: 0.50, rankPPP: 72, possCount: 80 },
            { playType: "Cut", frequencyPct: 5.0, ppp: 1.30, fgPct: 0.65, rankPPP: 85, possCount: 35 },
        ];
    }
    return [];
};

const getPlayerOnOffImpactAPI = async (playerId: string, season: string): Promise<OnOffImpactStat[]> => {
    console.log(`Fetching On/Off Impact stats for: ${playerId}, season: ${season}`);
    await new Promise(resolve => setTimeout(resolve, 450));
    if (playerId === "2544") { // LeBron James
        return [
            { category: "Team Performance", metric: "Offensive Rating", onCourt: 118.5, offCourt: 110.2, difference: (118.5 - 110.2).toFixed(1) },
            { category: "Team Performance", metric: "Defensive Rating", onCourt: 112.0, offCourt: 115.5, difference: (112.0 - 115.5).toFixed(1) },
            { category: "Team Performance", metric: "Net Rating", onCourt: "+6.5", offCourt: "-5.3", difference: "+11.8" }, // Example with string for +/- consistency
            { category: "Team Performance", metric: "eFG%", onCourt: "55.2%", offCourt: "52.1%", difference: "+3.1%" },
            { category: "Team Performance", metric: "TOV%", onCourt: "13.5%", offCourt: "14.8%", difference: "-1.3%" },
            { category: "Team Performance", metric: "Pace", onCourt: 100.5, offCourt: 98.2, difference: (100.5 - 98.2).toFixed(1) },
            { category: "Opponent Performance", metric: "Opponent eFG%", onCourt: "51.0%", offCourt: "54.5%", difference: "-3.5%" },
            { category: "Opponent Performance", metric: "Opponent TOV%", onCourt: "15.2%", offCourt: "13.8%", difference: "+1.4%" },
        ];
    }
    return [];
};

export default function PlayerIntelPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Player[]>([]);
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [playerBio, setPlayerBio] = useState<PlayerBio | null>(null);
  const [gameLogs, setGameLogs] = useState<PlayerGameLog[]>([]);
  const [shotChartData, setShotChartData] = useState<Shot[]>([]);
  const [advancedStats, setAdvancedStats] = useState<PlayerAdvancedStat[]>([]);
  const [synergyStats, setSynergyStats] = useState<SynergyPlayType[]>([]);
  const [onOffImpactStats, setOnOffImpactStats] = useState<OnOffImpactStat[]>([]);
  const [isLoadingSearch, setIsLoadingSearch] = useState(false);
  const [isLoadingBio, setIsLoadingBio] = useState(false);
  const [isLoadingLogs, setIsLoadingLogs] = useState(false);
  const [isLoadingShots, setIsLoadingShots] = useState(false);
  const [isLoadingAdvStats, setIsLoadingAdvStats] = useState(false);
  const [isLoadingSynergy, setIsLoadingSynergy] = useState(false);
  const [isLoadingOnOffImpact, setIsLoadingOnOffImpact] = useState(false);
  const [currentSeason, setCurrentSeason] = useState("2023-24");

  const handleSearch = useCallback(async () => {
    if (searchQuery.trim() === "") {
      setSearchResults([]);
      return;
    }
    setIsLoadingSearch(true);
    const results = await searchPlayersAPI(searchQuery);
    setSearchResults(results);
    setIsLoadingSearch(false);
  }, [searchQuery]);

  const loadPlayerData = useCallback(async (player: Player) => {
    setSelectedPlayer(player);
    setSearchResults([]);
    setSearchQuery(player.name);

    setIsLoadingBio(true); setIsLoadingLogs(true); setIsLoadingShots(true); setIsLoadingAdvStats(true); setIsLoadingSynergy(true); setIsLoadingOnOffImpact(true);
    setPlayerBio(null); setGameLogs([]); setShotChartData([]); setAdvancedStats([]); setSynergyStats([]); setOnOffImpactStats([]);

    Promise.all([
        getPlayerBioAPI(player.id),
        getPlayerGameLogsAPI(player.id, currentSeason),
        getPlayerShotChartAPI(player.id, currentSeason),
        getPlayerAdvancedStatsAPI(player.id, currentSeason),
        getPlayerSynergyStatsAPI(player.id, currentSeason),
        getPlayerOnOffImpactAPI(player.id, currentSeason)
    ]).then(([bio, logs, shots, advStats, synergy, onOff]) => {
        setPlayerBio(bio);
        setGameLogs(logs);
        setShotChartData(shots);
        setAdvancedStats(advStats);
        setSynergyStats(synergy);
        setOnOffImpactStats(onOff);
    }).catch(error => {
        console.error("Error loading player data:", error);
    }).finally(() => {
        setIsLoadingBio(false); setIsLoadingLogs(false); setIsLoadingShots(false); setIsLoadingAdvStats(false); setIsLoadingSynergy(false); setIsLoadingOnOffImpact(false);
    });
  }, [currentSeason]);

  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      if (searchQuery && (!selectedPlayer || searchQuery !== selectedPlayer.name)) {
         handleSearch();
      }
    }, 300);
    return () => clearTimeout(delayDebounceFn);
  }, [searchQuery, handleSearch, selectedPlayer]);
  
  useEffect(() => {
    if (selectedPlayer) {
      loadPlayerData(selectedPlayer);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSeason]);

  const renderStatCard = (title: string, value: string | number, subtitle?: string, icon?: React.ReactNode) => (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      </CardContent>
    </Card>
  );

  const renderShotChart = () => {
    if (isLoadingShots) return <Skeleton className="h-[400px] w-full" />;
    if (!shotChartData || shotChartData.length === 0) return <p className="text-center text-muted-foreground">No shot data available.</p>; 

    // Simplified NBA court dimensions for viewBox. This would need a real court overlay image.
    const courtWidth = 500;
    const courtHeight = 470; // Half court
    const basketOffset = { x: courtWidth / 2, y: 52.5 }; // Approximate basket position

    return (
      <div className="relative w-full max-w-2xl mx-auto aspect-[500/470]">
        <img src="/figma/nba-half-court-wood.svg" alt="NBA Court" className="absolute inset-0 w-full h-full" />
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
            <XAxis type="number" dataKey="x" hide domain={[-250, 250]} />
            <YAxis type="number" dataKey="y" hide domain={[-47.5, 422.5]} />
            <RechartsTooltip cursor={{ strokeDasharray: '3 3' }} content={({ active, payload }) => {
                if (active && payload && payload.length) {
                    const data = payload[0].payload as Shot;
                    return (
                        <div className="bg-background border p-2 rounded shadow-lg">
                            <p className="font-bold">{data.event_type}</p>
                            <p>Zone: {data.shot_zone_basic}</p>
                            <p>Area: {data.shot_zone_area}</p>
                            <p>Distance: {data.shot_distance} ft</p>
                        </div>
                    );
                }
                return null;
            }} />
            <Scatter name="Shots" data={shotChartData} fill="#8884d8">
              {shotChartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.made ? '#4ade80' : '#f87171'} />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    );
  };

  return (
    <div className="flex-1 space-y-6 p-4 md:p-6 lg:p-8">
      <div className="flex flex-col md:flex-row items-start justify-between gap-4">
        <div className="flex-1 w-full md:max-w-md">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search player (e.g., LeBron James)"
              className="pl-10 w-full"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                if (selectedPlayer && e.target.value !== selectedPlayer.name) {
                    setSelectedPlayer(null);
                    setPlayerBio(null);
                    setGameLogs([]);
                    setShotChartData([]);
                    setAdvancedStats([]);
                }
              }}
            />
          </div>
          {isLoadingSearch && <p className="text-sm text-muted-foreground mt-1 px-1">Searching...</p>}
          {searchResults.length > 0 && (
            <Card className="absolute z-10 mt-1 w-full md:max-w-md shadow-lg border bg-background max-h-60 overflow-y-auto">
              <CardContent className="p-1">
                {searchResults.map(player => (
                  <Button
                    key={player.id}
                    variant="ghost"
                    className="w-full justify-start p-2 h-auto font-normal text-sm rounded-md hover:bg-accent"
                    onClick={() => loadPlayerData(player)}
                  >
                    {player.name}
                  </Button>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
        <div className="flex items-center space-x-2 mt-2 md:mt-0">
            <Select value={currentSeason} onValueChange={setCurrentSeason} disabled={!selectedPlayer || isLoadingBio || isLoadingLogs || isLoadingShots || isLoadingAdvStats || isLoadingSynergy || isLoadingOnOffImpact}>
                <SelectTrigger className="w-[160px]">
                    <SelectValue placeholder="Select Season" />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="2023-24">2023-24 Season</SelectItem>
                    <SelectItem value="2022-23">2022-23 Season</SelectItem>
                    <SelectItem value="2021-22">2021-22 Season</SelectItem>
                </SelectContent>
            </Select>
        </div>
      </div>

      { (isLoadingBio && selectedPlayer && !playerBio) ? (
           <Card className="mt-6">
            <CardHeader className="flex flex-col md:flex-row items-center gap-6 p-6">
                <Skeleton className="h-24 w-24 md:h-32 md:w-32 rounded-full" />
                <div className="flex-1 space-y-2"><Skeleton className="h-8 w-3/4" /><Skeleton className="h-5 w-1/2" /><Skeleton className="h-5 w-3/5" /></div>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
                    <Skeleton className="h-20 w-full" />
                    <Skeleton className="h-20 w-full" />
                    <Skeleton className="h-20 w-full" />
                    <Skeleton className="h-20 w-full md:col-span-1" />
                    <Skeleton className="h-20 w-full md:col-span-1" />
                    <Skeleton className="h-20 w-full md:col-span-1" />
                </div>
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-40 w-full" />
            </CardContent>
           </Card>
      ) : selectedPlayer && playerBio ? (
        <Tabs defaultValue="overview" className="mt-6">
          <Card>
            <CardHeader className="p-4 md:p-6">
              <div className="flex flex-col md:flex-row items-start md:items-center gap-4 md:gap-6">
                {playerBio.imageUrl ? (
                  <img src={playerBio.imageUrl} alt={playerBio.name} className="h-24 w-24 md:h-32 md:w-32 rounded-full border object-cover" />
                ) : (
                  <Skeleton className="h-24 w-24 md:h-32 md:w-32 rounded-full" />
                )}
                <div className="flex-1">
                  <CardTitle className="text-2xl md:text-3xl font-bold flex items-center">
                    {playerBio.name}
                    <Badge variant="secondary" className="ml-3 text-sm">#{playerBio.jersey}</Badge>
                  </CardTitle>
                  <CardDescription className="text-base text-muted-foreground mt-1">
                    {playerBio.team} &bull; {playerBio.position}
                  </CardDescription>
                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-sm text-muted-foreground">
                    <span><Brain className="inline h-4 w-4 mr-1.5" />Age: {playerBio.age}</span>
                    <span><SlidersHorizontal className="inline h-4 w-4 mr-1.5" />{playerBio.height}, {playerBio.weight}</span>
                    <span><Users className="inline h-4 w-4 mr-1.5" />College: {playerBio.college}</span>
                    <span><ListFilter className="inline h-4 w-4 mr-1.5" />Exp: {playerBio.experience}</span>
                    <span><Info className="inline h-4 w-4 mr-1.5" />Draft: {playerBio.draftInfo}</span>
                    {playerBio.contractInfo && <span><ListFilter className="inline h-4 w-4 mr-1.5" />Contract: {playerBio.contractInfo}</span>}
                  </div>
                </div>
              </div>
              <TabsList className="mt-4 md:mt-6 grid w-full grid-cols-2 sm:grid-cols-3 md:grid-cols-6 h-auto">
                <TabsTrigger value="overview" className="py-2"><BarChart3 className="inline h-4 w-4 mr-2" />Overview</TabsTrigger>
                <TabsTrigger value="gameLogs" className="py-2"><ListFilter className="inline h-4 w-4 mr-2" />Game Logs</TabsTrigger>
                <TabsTrigger value="shotCharts" className="py-2"><Target className="inline h-4 w-4 mr-2" />Shot Charts</TabsTrigger>
                <TabsTrigger value="advancedStats" className="py-2"><TrendingUp className="inline h-4 w-4 mr-2" />Advanced Stats</TabsTrigger>
                <TabsTrigger value="synergy" className="py-2"><BotMessageSquare className="inline h-4 w-4 mr-2" />Play Types</TabsTrigger>
                <TabsTrigger value="impact" className="py-2"><Users className="inline h-4 w-4 mr-2" />On/Off Impact</TabsTrigger>
              </TabsList>
            </CardHeader>
            <TabsContent value="overview" className="p-4 md:p-6">
              <CardTitle className="mb-4 text-xl">Season Averages ({currentSeason})</CardTitle>
              {isLoadingLogs ? (
                <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-5">
                    {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
                </div>
              ) : gameLogs.length > 0 ? (
                <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-5">
                    {/* Placeholder for actual averages. This would require calculation. */}
                    {renderStatCard("Points", gameLogs.reduce((acc,g) => acc+g.pts,0)/gameLogs.length || 0, "PPG")}
                    {renderStatCard("Rebounds", gameLogs.reduce((acc,g) => acc+g.reb,0)/gameLogs.length || 0, "RPG")}
                    {renderStatCard("Assists", gameLogs.reduce((acc,g) => acc+g.ast,0)/gameLogs.length || 0, "APG")}
                    {renderStatCard("FG%", `${((gameLogs.reduce((acc,g) => acc+g.fgm,0)/gameLogs.reduce((acc,g) => acc+g.fga,0) || 0)*100).toFixed(1)}%`)}
                    {renderStatCard("3P%", `${((gameLogs.reduce((acc,g) => acc+g.fg3m,0)/gameLogs.reduce((acc,g) => acc+g.fg3a,0) || 0)*100).toFixed(1)}%`)}
                </div>
              ) : <p className="text-muted-foreground">No game logs found for this season to calculate averages.</p>}
            </TabsContent>
            <TabsContent value="gameLogs" className="p-4 md:p-6">
                <CardTitle className="mb-4 text-xl">Game Logs ({currentSeason})</CardTitle>
                {isLoadingLogs ? <Skeleton className="h-60 w-full" /> : gameLogs.length > 0 ? (
                    <div className="overflow-x-auto">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Date</TableHead><TableHead>Matchup</TableHead><TableHead>W/L</TableHead>
                                    <TableHead>MIN</TableHead><TableHead>PTS</TableHead><TableHead>REB</TableHead><TableHead>AST</TableHead><TableHead>STL</TableHead><TableHead>BLK</TableHead>
                                    <TableHead>FG%</TableHead><TableHead>3P%</TableHead><TableHead>FT%</TableHead><TableHead>+/-</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {gameLogs.map((log) => (
                                    <TableRow key={log.game_id}>
                                        <TableCell>{log.game_date}</TableCell><TableCell>{log.matchup}</TableCell><TableCell>{log.wl}</TableCell>
                                        <TableCell>{log.min}</TableCell><TableCell>{log.pts}</TableCell><TableCell>{log.reb}</TableCell><TableCell>{log.ast}</TableCell><TableCell>{log.stl}</TableCell><TableCell>{log.blk}</TableCell>
                                        <TableCell>{(log.fg_pct * 100).toFixed(1)}%</TableCell><TableCell>{(log.fg3_pct * 100).toFixed(1)}%</TableCell><TableCell>{(log.ft_pct * 100).toFixed(1)}%</TableCell><TableCell>{log.plus_minus}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                ) : <p className="text-muted-foreground">No game logs available for this season.</p>}
            </TabsContent>
            <TabsContent value="shotCharts" className="p-4 md:p-6">
                <CardTitle className="mb-4 text-xl">Shot Chart ({currentSeason})</CardTitle>
                {renderShotChart()}
            </TabsContent>
            <TabsContent value="advancedStats" className="p-4 md:p-6">
                <CardTitle className="mb-4 text-xl">Advanced Metrics ({currentSeason})</CardTitle>
                {isLoadingAdvStats ? (
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 mb-6">
                        {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-32 w-full" />)}
                    </div>
                 ) : advancedStats.length > 0 ? (
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 mb-6">
                        {advancedStats.filter(stat => !["PER", "TS%", "USG%", "AST_Ratio", "REB_PCT", "NetRtg_Est"].includes(stat.metric)).map(stat => ( // Filter out radar stats from cards if shown separately
                            <Card key={stat.metric}>
                                <CardHeader className="pb-2">
                                    <div className="flex items-center justify-between">
                                        <CardTitle className="text-lg">{stat.metric.replace("_", " ")}</CardTitle>
                                        {stat.percentile && <Badge variant={stat.percentile > 75 ? "default" : stat.percentile > 50 ? "secondary" : "outline"}>{stat.percentile}th</Badge>}
                                    </div>
                                    {stat.description && <CardDescription className="text-xs mt-1">{stat.description}</CardDescription>}
                                </CardHeader>
                                <CardContent>
                                    <p className="text-3xl font-bold">
                                        {stat.metric === "PIE" || stat.metric === "USG%" || stat.metric === "REB_PCT" ? `${stat.value}%` : 
                                         stat.metric === "TS%" ? `${(Number(stat.value) * 100).toFixed(1)}%` : 
                                         stat.value}
                                    </p>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                ) : <p className="text-muted-foreground">No advanced stats available for this season.</p>}

                {isLoadingAdvStats ? (
                    <Skeleton className="h-80 w-full" />
                ) : advancedStats.length > 0 ? (
                    <Card className="col-span-1 md:col-span-2 lg:col-span-3">
                        <CardHeader>
                            <CardTitle className="text-lg">Key Metrics Overview</CardTitle>
                            <CardDescription className="text-xs">Player percentiles against league average (mock data: 50th percentile is average).</CardDescription>
                        </CardHeader>
                        <CardContent className="h-[350px] w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <RadarChart cx="50%" cy="50%" outerRadius="80%" data={[
                                    {
                                        subject: 'PER',
                                        value: advancedStats.find(s => s.metric === "PER")?.percentile || 0,
                                        fullMark: 100,
                                    },
                                    {
                                        subject: 'TS%',
                                        value: advancedStats.find(s => s.metric === "TS%")?.percentile || 0,
                                        fullMark: 100,
                                    },
                                    {
                                        subject: 'USG%',
                                        value: advancedStats.find(s => s.metric === "USG%")?.percentile || 0,
                                        fullMark: 100,
                                    },
                                    {
                                        subject: 'AST Ratio',
                                        value: advancedStats.find(s => s.metric === "AST_Ratio")?.percentile || 0,
                                        fullMark: 100,
                                    },
                                    {
                                        subject: 'REB Pct',
                                        value: advancedStats.find(s => s.metric === "REB_PCT")?.percentile || 0,
                                        fullMark: 100,
                                    },
                                    {
                                        subject: 'NetRtg Est',
                                        value: advancedStats.find(s => s.metric === "NetRtg_Est")?.percentile || 0,
                                        fullMark: 100,
                                    },
                                ]}>
                                    <PolarGrid />
                                    <PolarAngleAxis dataKey="subject" />
                                    <PolarRadiusAxis angle={30} domain={[0, 100]} tickFormatter={(tick) => `${tick}%`} />
                                    <Radar name={playerBio?.name || "Player"} dataKey="value" stroke="#8884d8" fill="#8884d8" fillOpacity={0.6} />
                                    <Legend />
                                    <RechartsTooltip />
                                </RadarChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>
                ) : null}
            </TabsContent>

            <TabsContent value="synergy" className="p-4 md:p-6">
                <CardTitle className="mb-4 text-xl">Synergy Play Types ({currentSeason})</CardTitle>
                {isLoadingSynergy ? (
                    <div className="space-y-4">
                        <Skeleton className="h-10 w-1/3" />
                        <Skeleton className="h-40 w-full" />
                    </div>
                ) : synergyStats.length > 0 ? (
                    <div className="overflow-x-auto">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead className="w-[200px]">Play Type</TableHead>
                                    <TableHead className="text-right">Frequency</TableHead>
                                    <TableHead className="text-right">PPP</TableHead>
                                    <TableHead className="text-right">FG%</TableHead>
                                    <TableHead className="text-right">Rank (PPP)</TableHead>
                                    <TableHead className="text-right">Possessions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {synergyStats.map((stat) => (
                                    <TableRow key={stat.playType}>
                                        <TableCell className="font-medium">{stat.playType}</TableCell>
                                        <TableCell className="text-right">{stat.frequencyPct.toFixed(1)}%</TableCell>
                                        <TableCell className="text-right">{stat.ppp.toFixed(2)}</TableCell>
                                        <TableCell className="text-right">{(stat.fgPct * 100).toFixed(1)}%</TableCell>
                                        <TableCell className="text-right">{stat.rankPPP ? `${stat.rankPPP}th` : "N/A"}</TableCell>
                                        <TableCell className="text-right">{stat.possCount || "N/A"}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                ) : (
                    <p className="text-muted-foreground">No Synergy play type data available for this season.</p>
                )}
            </TabsContent>

            <TabsContent value="impact" className="p-4 md:p-6">
                <CardTitle className="mb-4 text-xl">On/Off Court Impact ({currentSeason})</CardTitle>
                {isLoadingOnOffImpact ? (
                    <div className="space-y-4">
                        <Skeleton className="h-10 w-1/3" />
                        <Skeleton className="h-48 w-full" />
                    </div>
                ) : onOffImpactStats.length > 0 ? (
                    <div className="space-y-6">
                        {[...new Set(onOffImpactStats.map(s => s.category))].map(category => (
                            <div key={category}>
                                <h3 className="text-lg font-semibold mb-2 text-muted-foreground">{category}</h3>
                                <div className="overflow-x-auto">
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead className="w-[250px]">Metric</TableHead>
                                                <TableHead className="text-right">On Court</TableHead>
                                                <TableHead className="text-right">Off Court</TableHead>
                                                <TableHead className="text-right">Difference</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {onOffImpactStats.filter(s => s.category === category).map((stat) => (
                                                <TableRow key={stat.metric}>
                                                    <TableCell className="font-medium">{stat.metric}</TableCell>
                                                    <TableCell className="text-right">{stat.onCourt}</TableCell>
                                                    <TableCell className="text-right">{stat.offCourt}</TableCell>
                                                    <TableCell 
                                                        className={`text-right font-semibold ${
                                                            typeof stat.difference === 'string' && stat.difference.startsWith('+') ? 'text-green-600' : 
                                                            typeof stat.difference === 'string' && stat.difference.startsWith('-') ? 'text-red-600' : ''
                                                        }`}
                                                    >
                                                        {stat.difference}
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="text-muted-foreground">No On/Off Court Impact data available for this season.</p>
                )}
            </TabsContent>

          </Card>
        </Tabs>
      ) : (
         !isLoadingSearch && !selectedPlayer && searchResults.length === 0 && (
          <Card className="mt-6 border-dashed border-muted-foreground/50">
            <CardHeader className="text-center p-6">
              <UserCircle className="h-16 w-16 mx-auto text-muted-foreground/30 mb-4" />
              <CardTitle className="text-xl font-semibold">Player Intelligence Hub</CardTitle>
              <CardDescription className="mt-1 text-muted-foreground">Search for an NBA player to view detailed information and advanced analytics.</CardDescription>
            </CardHeader>
             <CardContent className="text-center pb-6">
                <p className="text-sm text-muted-foreground">Examples: LeBron James, Stephen Curry, Nikola Jokic</p>
            </CardContent>
          </Card>
        )
      )}
    </div>
  );
}

