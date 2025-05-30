"use client";

import React, { useState, useEffect, useCallback } from 'react';
import Link from "next/link"; // Added Link import
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area"; // For horizontal scroll sections
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"; // If needed for content switching
import { Separator } from "@/components/ui/separator";
import { Flame, BarChart, Users, CalendarClock, Newspaper, TrendingUp } from "lucide-react"; // Example icons
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { BarChart3, ListChecks, ShieldCheck, Activity, Building } from 'lucide-react'; // Example icons

// Placeholder data - In a real scenario, this would come from API calls
// const liveGames = [
//   { id: 1, teamA: "LAL", scoreA: 102, teamB: "BOS", scoreB: 98, period: "Q4", time: "2:30" },
//   { id: 2, teamA: "GSW", scoreA: 115, teamB: "DEN", scoreB: 110, period: "Q4", time: "5:15" },
//   { id: 3, teamA: "MIL", scoreA: 90, teamB: "PHI", scoreB: 92, period: "HALFTIME" },
//   // ... more games
// ];

const topPerformers = [
  { id: 1, name: "LeBron James", team: "LAL", statLine: "35 PTS, 10 REB, 8 AST", avatar: "/avatars/lebron.png" },
  { id: 2, name: "Nikola Jokic", team: "DEN", statLine: "28 PTS, 15 REB, 12 AST", avatar: "/avatars/jokic.png" },
  // ... more performers
];

const leagueStandingsEast = [
  { rank: 1, team: "Boston Celtics", wins: 50, losses: 12 },
  { rank: 2, team: "Milwaukee Bucks", wins: 45, losses: 17 },
  // ... more teams
];

const leagueStandingsWest = [
  { rank: 1, team: "Denver Nuggets", wins: 48, losses: 14 },
  { rank: 2, team: "Golden State Warriors", wins: 46, losses: 16 },
  // ... more teams
];

const dimesInsights = [
  { id: 1, title: "Rookie Spotlight: Future All-Star Potential?", date: "2024-03-15", summary: "Analyzing the latest rookie performances and their trajectory..." },
  { id: 2, title: "Trade Deadline Impact on Western Conference", date: "2024-03-14", summary: "How recent trades have shifted the balance of power..." },
];

// export const metadata: Metadata = {
//   title: "Dime | Overview",
//   description: "NBA league overview, live scores, top performers, and insights.",
// };

// --- Start of Placeholder Data Structures ---
interface LeagueLeader {
  rank: number;
  playerId?: string;
  playerName?: string;
  teamId?: string;
  teamName?: string;
  teamAbbr?: string;
  value: string | number;
  profileUrl?: string;
}

interface LeagueLineup {
  lineupId: string;
  players: Array<{ id: string; name: string }>;
  teamId: string;
  teamName: string;
  teamAbbr: string;
  minutes: number;
  offRtg: number;
  defRtg: number;
  netRtg: number;
  efgPct?: number;
  tovPct?: number;
  pace?: number;
}

interface Team {
    id: string;
    name: string;
    abbreviation: string;
}

interface TeamSnapshot extends Team {
  record: string; 
  offRtg: number;
  defRtg: number;
  netRtg: number;
  pace: number;
  efgPct: number;
  oppEfgPct: number;
  tovPct: number;
}
// --- End of Placeholder Data Structures ---

// --- Start of Mock API Functions ---
const mockTeamsAPI = async (): Promise<Team[]> => {
    await new Promise(resolve => setTimeout(resolve, 200));
    return [
        { id: "1610612737", name: "Atlanta Hawks", abbreviation: "ATL" },
        { id: "1610612738", name: "Boston Celtics", abbreviation: "BOS" },
        { id: "1610612747", name: "Los Angeles Lakers", abbreviation: "LAL" },
        { id: "1610612744", name: "Golden State Warriors", abbreviation: "GSW" },
        { id: "1610612743", name: "Denver Nuggets", abbreviation: "DEN" },
        // Add more teams as needed for a more complete dropdown
    ];
};

const getAdvancedLeagueLeadersAPI = async (category: string, season: string): Promise<LeagueLeader[]> => {
    console.log(`Fetching Advanced League Leaders for: ${category}, Season: ${season}`);
    await new Promise(resolve => setTimeout(resolve, 600));
    const leaders: LeagueLeader[] = [];
    const playerNames = ["Nikola Jokic", "Luka Doncic", "Shai Gilgeous-Alexander", "Giannis Antetokounmpo", "Jayson Tatum", "Joel Embiid", "Kevin Durant", "Stephen Curry", "LeBron James", "Anthony Davis"];
    const teamAbbrs = ["DEN", "DAL", "OKC", "MIL", "BOS", "PHI", "PHX", "GSW", "LAL", "LAL"];
    const numLeaders = Math.floor(Math.random() * 6) + 5; // 5 to 10 leaders

    for (let i = 0; i < numLeaders; i++) {
        leaders.push({
            rank: i + 1,
            playerName: playerNames[i % playerNames.length],
            teamAbbr: teamAbbrs[i % teamAbbrs.length],
            value: category === "PER" ? (30 - i * 1.2).toFixed(1) :
                   category === "WS" ? (15 - i * 0.7).toFixed(1) :
                   category === "OffRtg" ? (120 - i * 1.8).toFixed(1) :
                   category === "DefRtg" ? (105 + i * 0.8).toFixed(1) :
                   category === "ContestedS_PG" ? (15 - i * 0.5).toFixed(1) :
                   (Math.random() * 20 + 5).toFixed(1), // Random value for other categories
            profileUrl: "/player-intel?id=mock" // Placeholder link
        });
    }
    return leaders;
};

const getTopLineupsAPI = async (season: string, minMinutes: number): Promise<LeagueLineup[]> => {
    console.log(`Fetching Top Lineups for season: ${season}, minMinutes: ${minMinutes}`);
    await new Promise(resolve => setTimeout(resolve, 700));
    return [
        { lineupId: "L1", players: [{id: "P1", name:"J. Murray"}, {id: "P2", name:"K. Caldwell-Pope"}, {id: "P3", name:"M. Porter Jr."}, {id: "P4", name:"A. Gordon"}, {id: "P5", name:"N. Jokic"}], teamId: "T1", teamName: "Denver Nuggets", teamAbbr: "DEN", minutes: Math.floor(Math.random()*200) + minMinutes, offRtg: 125.5, defRtg: 108.2, netRtg: 17.3, efgPct: 0.58, tovPct: 0.12 },
        { lineupId: "L2", players: [{id: "P6", name:"D. White"}, {id: "P7", name:"J. Holiday"}, {id: "P8", name:"J. Brown"}, {id: "P9", name:"J. Tatum"}, {id: "P10", name:"K. Porzingis"}], teamId: "T2", teamName: "Boston Celtics", teamAbbr: "BOS", minutes: Math.floor(Math.random()*150) + minMinutes, offRtg: 122.1, defRtg: 106.5, netRtg: 15.6, efgPct: 0.57, tovPct: 0.13 },
        { lineupId: "L3", players: [{id: "P11", name:"M. Conley"}, {id: "P12", name:"A. Edwards"}, {id: "P13", name:"J. McDaniels"}, {id: "P14", name:"K.A. Towns"}, {id: "P15", name:"R. Gobert"}], teamId: "T3", teamName: "Minnesota Timberwolves", teamAbbr: "MIN", minutes: Math.floor(Math.random()*100) + minMinutes, offRtg: 119.8, defRtg: 105.1, netRtg: 14.7, efgPct: 0.56, tovPct: 0.14 },
    ];
};

const getTeamSnapshotAPI = async (teamId: string, season: string): Promise<TeamSnapshot | null> => {
    console.log(`Fetching Team Snapshot for team: ${teamId}, season: ${season}`);
    await new Promise(resolve => setTimeout(resolve, 500));
    const teamsMockDb: TeamSnapshot[] = [
        { id: "1610612743", name: "Denver Nuggets", abbreviation: "DEN", record: "57-25", offRtg: 118.5, defRtg: 112.3, netRtg: 6.2, pace: 98.5, efgPct: 0.572, oppEfgPct: 0.540, tovPct: 0.135 },
        { id: "1610612738", name: "Boston Celtics", abbreviation: "BOS", record: "64-18", offRtg: 120.2, defRtg: 110.1, netRtg: 10.1, pace: 99.2, efgPct: 0.581, oppEfgPct: 0.530, tovPct: 0.128 },
        { id: "1610612747", name: "Los Angeles Lakers", abbreviation: "LAL", record: "47-35", offRtg: 115.0, defRtg: 114.5, netRtg: 0.5, pace: 101.3, efgPct: 0.555, oppEfgPct: 0.550, tovPct: 0.140 },
        { id: "1610612737", name: "Atlanta Hawks", abbreviation: "ATL", record: "36-46", offRtg: 116.7, defRtg: 119.3, netRtg: -2.6, pace: 100.8, efgPct: 0.548, oppEfgPct: 0.565, tovPct: 0.130 },
        { id: "1610612744", name: "Golden State Warriors", abbreviation: "GSW", record: "46-36", offRtg: 117.2, defRtg: 115.1, netRtg: 2.1, pace: 100.1, efgPct: 0.560, oppEfgPct: 0.542, tovPct: 0.138 },
    ];
    return teamsMockDb.find(t => t.id === teamId) || null;
};
// --- End of Mock API Functions ---

export default function OverviewPage() {
  const [currentSeason, setCurrentSeason] = useState("2023-24");
  const [allTeams, setAllTeams] = useState<Team[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);

  const [leagueLeaders, setLeagueLeaders] = useState<LeagueLeader[]>([]);
  const [currentLeaderCategory, setCurrentLeaderCategory] = useState("PER");
  const [isLoadingLeaders, setIsLoadingLeaders] = useState(false);

  const [topLineups, setTopLineups] = useState<LeagueLineup[]>([]);
  const [minLineupMinutes, setMinLineupMinutes] = useState(200);
  const [isLoadingLineups, setIsLoadingLineups] = useState(false);

  const [teamSnapshot, setTeamSnapshot] = useState<TeamSnapshot | null>(null);
  const [isLoadingSnapshot, setIsLoadingSnapshot] = useState(false);

  useEffect(() => {
    const fetchLeaders = async () => {
        setIsLoadingLeaders(true);
        const leaders = await getAdvancedLeagueLeadersAPI(currentLeaderCategory, currentSeason);
        setLeagueLeaders(leaders);
        setIsLoadingLeaders(false);
    };
    fetchLeaders();
  }, [currentSeason, currentLeaderCategory]);

  useEffect(() => {
    const fetchLineups = async () => {
        setIsLoadingLineups(true);
        const lineups = await getTopLineupsAPI(currentSeason, minLineupMinutes);
        setTopLineups(lineups);
        setIsLoadingLineups(false);
    };
    fetchLineups();
  }, [currentSeason, minLineupMinutes]);

  useEffect(() => {
    const fetchTeams = async () => {
        const teams = await mockTeamsAPI();
        setAllTeams(teams);
        if (teams.length > 0 && !selectedTeamId) { // Set initial selected team only if not already set
            setSelectedTeamId(teams[0].id);
        }
    };
    fetchTeams();
  }, [selectedTeamId]); // Added selectedTeamId to deps to avoid resetting selection if it was already made

  useEffect(() => {
    if (selectedTeamId) {
        const fetchSnapshot = async () => {
            setIsLoadingSnapshot(true);
            const snapshot = await getTeamSnapshotAPI(selectedTeamId, currentSeason);
            setTeamSnapshot(snapshot);
            setIsLoadingSnapshot(false);
        };
        fetchSnapshot();
    }
  }, [selectedTeamId, currentSeason]);

  return (
    <div className="flex-1 space-y-8 p-4 md:p-6 lg:p-8">
      <div className="flex items-center justify-between space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">League Overview</h1>
        <div className="flex items-center space-x-2">
          <Select value={currentSeason} onValueChange={setCurrentSeason}>
            <SelectTrigger className="w-[180px]">
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

      {/* Advanced League Leaders Section */}
      <Card>
        <CardHeader>
          <CardTitle>Advanced League Leaders</CardTitle>
          <CardDescription>Top players across key advanced statistical categories for {currentSeason}.</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={currentLeaderCategory} onValueChange={setCurrentLeaderCategory}>
            <TabsList className="grid w-full grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-1 mb-4 h-auto">
              <TabsTrigger value="PER" className="py-2 text-xs sm:text-sm"><Activity className="hidden sm:inline h-4 w-4 mr-1 sm:mr-2" />PER</TabsTrigger>
              <TabsTrigger value="WS" className="py-2 text-xs sm:text-sm"><ListChecks className="hidden sm:inline h-4 w-4 mr-1 sm:mr-2" />Win Shares</TabsTrigger>
              <TabsTrigger value="OffRtg" className="py-2 text-xs sm:text-sm"><BarChart3 className="hidden sm:inline h-4 w-4 mr-1 sm:mr-2" />Off. Rating</TabsTrigger>
              <TabsTrigger value="DefRtg" className="py-2 text-xs sm:text-sm"><ShieldCheck className="hidden sm:inline h-4 w-4 mr-1 sm:mr-2" />Def. Rating</TabsTrigger>
              <TabsTrigger value="ContestedS_PG" className="py-2 text-xs sm:text-sm"><Users className="hidden sm:inline h-4 w-4 mr-1 sm:mr-2" />Contested S/G</TabsTrigger>
            </TabsList>
            {isLoadingLeaders ? (
                <Skeleton className="h-72 w-full" />
            ) : leagueLeaders.length > 0 ? (
                <div className="overflow-x-auto">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-[50px]">Rank</TableHead>
                            <TableHead>Player</TableHead>
                            <TableHead>Team</TableHead>
                            <TableHead className="text-right">Value</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {leagueLeaders.map((leader) => (
                            <TableRow key={`${leader.rank}-${leader.playerName}-${leader.teamAbbr}`}>
                                <TableCell>{leader.rank}</TableCell>
                                <TableCell className="font-medium">{leader.playerName}</TableCell>
                                <TableCell>{leader.teamAbbr}</TableCell>
                                <TableCell className="text-right">{leader.value}</TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
                </div>
            ) : (
                <p className="text-muted-foreground text-center py-10">No leader data available for this category/season.</p>
            )}
          </Tabs>
        </CardContent>
      </Card>

      {/* Top Performing Lineups Section */}
      <Card>
        <CardHeader>
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center">
                <div>
                    <CardTitle>Top Performing Lineups</CardTitle>
                    <CardDescription>Most effective 5-player lineups in {currentSeason}.</CardDescription>
                </div>
                <div className="flex items-center space-x-2 mt-2 sm:mt-0">
                    <span className="text-sm text-muted-foreground">Min. Mins:</span>
                    <Select value={String(minLineupMinutes)} onValueChange={(value) => setMinLineupMinutes(Number(value))}>
                        <SelectTrigger className="w-[100px]">
                            <SelectValue placeholder="Mins" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="100">100</SelectItem>
                            <SelectItem value="200">200</SelectItem>
                            <SelectItem value="300">300</SelectItem>
                            <SelectItem value="400">400</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </div>
        </CardHeader>
        <CardContent>
        {isLoadingLineups ? (
            <Skeleton className="h-60 w-full" />
        ) : topLineups.length > 0 ? (
            <div className="overflow-x-auto">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead className="min-w-[250px]">Lineup</TableHead>
                        <TableHead>Team</TableHead>
                        <TableHead className="text-right">Minutes</TableHead>
                        <TableHead className="text-right">Off Rtg</TableHead>
                        <TableHead className="text-right">Def Rtg</TableHead>
                        <TableHead className="text-right">Net Rtg</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {topLineups.map((lineup) => (
                        <TableRow key={lineup.lineupId}>
                            <TableCell className="font-medium text-xs">{lineup.players.map(p => p.name).join(', ')}</TableCell>
                            <TableCell>{lineup.teamAbbr}</TableCell>
                            <TableCell className="text-right">{lineup.minutes}</TableCell>
                            <TableCell className="text-right">{lineup.offRtg.toFixed(1)}</TableCell>
                            <TableCell className="text-right">{lineup.defRtg.toFixed(1)}</TableCell>
                            <TableCell className="text-right font-semibold">{lineup.netRtg.toFixed(1)}</TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
            </div>
        ) : (
            <p className="text-muted-foreground text-center py-10">No lineup data available for this criteria.</p>
        )}
        </CardContent>
      </Card>

      {/* Team Analytics Snapshot Section */}
      <Card>
        <CardHeader>
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center">
            <div>
              <CardTitle>Team Analytics Snapshot</CardTitle>
              <CardDescription>Key performance indicators for the selected team in {currentSeason}.</CardDescription>
            </div>
            {allTeams.length > 0 && (
                <Select value={selectedTeamId || ""} onValueChange={setSelectedTeamId} disabled={isLoadingSnapshot || allTeams.length === 0}>
                    <SelectTrigger className="w-full md:w-[220px] mt-2 md:mt-0">
                        <SelectValue placeholder="Select Team" />
                    </SelectTrigger>
                    <SelectContent>
                        {allTeams.map(team => (
                            <SelectItem key={team.id} value={team.id}>{team.name}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            )}
          </div>
        </CardHeader>
        <CardContent>
        {isLoadingSnapshot ? (
            <div className="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-24 w-full" /> )}
            </div>
        ) : teamSnapshot ? (
            <div className="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {renderStatCardMini("Record", teamSnapshot.record, <Building className="h-4 w-4 text-muted-foreground" />)}
                {renderStatCardMini("Off. Rating", teamSnapshot.offRtg.toFixed(1), <BarChart3 className="h-4 w-4 text-muted-foreground" />)}
                {renderStatCardMini("Def. Rating", teamSnapshot.defRtg.toFixed(1), <ShieldCheck className="h-4 w-4 text-muted-foreground" />)}
                {renderStatCardMini("Net Rating", teamSnapshot.netRtg.toFixed(1), <Activity className="h-4 w-4 text-muted-foreground" />)}
                {renderStatCardMini("Pace", teamSnapshot.pace.toFixed(1))}
                {renderStatCardMini("eFG%", (teamSnapshot.efgPct * 100).toFixed(1) + "%")}
                {renderStatCardMini("Opp. eFG%", (teamSnapshot.oppEfgPct * 100).toFixed(1) + "%")}
                {renderStatCardMini("TOV%", (teamSnapshot.tovPct * 100).toFixed(1) + "%")}
            </div>
        ) : selectedTeamId ? (
            <p className="text-muted-foreground text-center py-10">No snapshot data available for {allTeams.find(t => t.id === selectedTeamId)?.name || "selected team"}.</p>
        ) : (
             <p className="text-muted-foreground text-center py-10">Select a team to view their snapshot.</p>
        )}
        </CardContent>
      </Card>

    </div>
  );
}

// Helper for Team Snapshot cards - can be moved to a shared util if used elsewhere
const renderStatCardMini = (title: string, value: string | number, icon?: React.ReactNode) => (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1 pt-3 px-4">
        <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent className="pb-3 px-4">
        <div className="text-2xl font-bold">{value}</div>
      </CardContent>
    </Card>
  );
