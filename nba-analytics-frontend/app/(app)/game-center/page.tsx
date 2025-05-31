"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
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
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { 
  CalendarDays, ListFilter, Tv, BarChartHorizontalBig, Users, Percent, PlayCircle, 
  Dribbble, ListOrdered, TrendingUp, Target, Zap, Brain, AlertTriangle, 
  Activity, Clock, Award, ArrowUp, ArrowDown, Flame, Snowflake, Eye, 
  Crosshair, Shield, Swords, Timer, TrendingDown
} from "lucide-react";

// --- Enhanced Data Structures ---
interface GameInfo {
  gameId: string;
  date: string;
  time: string;
  homeTeamId: string;
  homeTeamName: string;
  homeTeamAbbr: string;
  homeTeamScore: number;
  awayTeamId: string;
  awayTeamName: string;
  awayTeamAbbr: string;
  awayTeamScore: number;
  status: "Scheduled" | "Live Q1" | "Live Q2" | "Halftime" | "Live Q3" | "Live Q4" | "OT" | "Final";
  livePeriod?: number;
  liveClock?: string;
  
  // Advanced game context
  venue?: string;
  attendance?: number;
  referees?: string[];
  gameImportance?: 'Regular' | 'Rivalry' | 'Playoff Race' | 'Playoff' | 'Finals';
  nationalTV?: boolean;
}

// Enhanced play-by-play with AI analysis
interface PlayByPlayEntry {
  id: string;
  period: string;
  clock: string;
  teamAbbr?: string;
  description: string;
  score?: string;
  
  // Advanced analytics
  playType: 'Shot' | 'Turnover' | 'Foul' | 'Substitution' | 'Timeout' | 'Other';
  winProbabilityChange?: number; // +/- percentage points
  momentumImpact?: 'High' | 'Medium' | 'Low';
  aiInsight?: string; // AI-generated context
  keyPlay?: boolean;
}

// Enhanced box score with impact metrics
interface BoxScorePlayerStats {
  playerId: string;
  playerName: string;
  starter: boolean;
  minutes: string;
  fgm: number; fga: number; fgPct: number;
  fg3m: number; fg3a: number; fg3Pct: number;
  ftm: number; fta: number; ftPct: number;
  oreb: number; dreb: number; reb: number;
  ast: number; stl: number; blk: number; tov: number; pf: number; pts: number;
  plusMinus?: number;
  
  // Advanced impact metrics
  impactRating?: number; // 0-10 scale
  clutchPerformance?: number; // Performance in crucial moments
  efficiencyRating?: number; // Overall efficiency
  defenseGrade?: 'A+' | 'A' | 'B+' | 'B' | 'C+' | 'C' | 'D' | 'F';
  momentumPlays?: number; // Number of momentum-shifting plays
}

// Advanced team analytics
interface TeamGameStatsSummary {
  teamId: string;
  teamAbbr: string;
  fgPct: number;
  fg3Pct: number;
  ftPct: number;
  rebounds: number;
  assists: number;
  turnovers: number;
  
  // Advanced metrics
  possessions: number;
  pace: number;
  offensiveRating: number;
  defensiveRating: number;
  effectiveFgPct: number;
  trueShootingPct: number;
  assistTurnoverRatio: number;
  reboundingRate: number;
  
  // Game flow metrics
  fastBreakPoints: number;
  pointsInPaint: number;
  secondChancePoints: number;
  benchPoints: number;
  biggestLead: number;
  timeWithLead: string; // "23:45"
  leadChanges: number;
}

// Player matchup analysis
interface PlayerMatchup {
  offensivePlayer: {
    id: string;
    name: string;
    position: string;
  };
  defensivePlayer: {
    id: string;
    name: string;
    position: string;
  };
  possessions: number;
  points: number;
  fgAttempts: number;
  fgMade: number;
  efficiency: number;
  advantageRating: number; // -10 to +10 (defensive advantage to offensive advantage)
  keyMoments: string[];
}

// Game momentum tracking
interface MomentumData {
  timestamp: string; // Game time
  homeTeamMomentum: number; // -100 to +100
  awayTeamMomentum: number;
  triggerEvent?: string; // What caused the momentum shift
  significance: 'Major' | 'Moderate' | 'Minor';
}

// AI Game insights
interface GameInsight {
  id: string;
  type: 'trend' | 'prediction' | 'key_player' | 'strategy' | 'momentum';
  priority: 'critical' | 'high' | 'medium' | 'low';
  title: string;
  description: string;
  confidence: number; // 0-100
  timestamp: string;
  relatedPlayers?: string[];
  impactLevel: 'Game-Changing' | 'Significant' | 'Notable' | 'Minor';
}

// Win probability with enhanced context
interface WinProbabilityDataPoint {
  time: string;
  homeWinProb: number;
  awayWinProb: number;
  
  // Enhanced context
  keyEvent?: string;
  volatility?: number; // How much the probability has been changing
  clutchFactor?: number; // How important this moment is (0-100)
}

// --- Enhanced Mock API Functions ---
const determineGameStatus = (gameDateTime: Date, currentApiStatus: GameInfo["status"] = "Scheduled"): GameInfo["status"] => {
    const now = new Date();
    const gameEndTime = new Date(gameDateTime.getTime() + 3 * 60 * 60 * 1000);

    if (currentApiStatus === "Final" || gameEndTime < now) return "Final";
    
    if (gameDateTime <= now && gameEndTime >= now) {
        const minutesIntoGame = (now.getTime() - gameDateTime.getTime()) / (60 * 1000);
        if (minutesIntoGame < 14) return "Live Q1";
        if (minutesIntoGame < 28) return "Live Q2";
        if (minutesIntoGame < 45) return "Halftime";
        if (minutesIntoGame < 60) return "Live Q3";
        if (minutesIntoGame < 75) return "Live Q4";
        return "OT";
    }
    return "Scheduled";
};

const mockGetRecentGamesAPI = async (date?: string): Promise<GameInfo[]> => {
    await new Promise(resolve => setTimeout(resolve, 400));
    const today = new Date();
    const referenceDate = date ? new Date(date) : today;
    referenceDate.setHours(0,0,0,0); 
    today.setHours(0,0,0,0); 

    let gameDate1 = new Date(referenceDate);
    let gameDate2 = new Date(referenceDate);
    let gameDate3 = new Date(referenceDate);
    gameDate3.setDate(gameDate3.getDate() + 1);

    const game1DateTime = new Date(gameDate1.toISOString().split('T')[0] + 'T19:00:00');
    const game2DateTime = new Date(gameDate2.toISOString().split('T')[0] + 'T21:30:00');
    const game3DateTime = new Date(gameDate3.toISOString().split('T')[0] + 'T20:00:00');

    const game1Status = determineGameStatus(game1DateTime);
    const game2Status = determineGameStatus(game2DateTime);
    const game3Status = determineGameStatus(game3DateTime, "Scheduled");

    return [
        { 
          gameId: "G20240320_LALBOS", 
          date: gameDate1.toISOString().split('T')[0], 
          time: "7:00 PM EST", 
          homeTeamId: "T01", 
          homeTeamName: "Boston Celtics", 
          homeTeamAbbr: "BOS", 
          homeTeamScore: game1Status !== "Scheduled" ? 110 : 0, 
          awayTeamId: "T02", 
          awayTeamName: "Los Angeles Lakers", 
          awayTeamAbbr: "LAL", 
          awayTeamScore: game1Status !== "Scheduled" ? 105 : 0, 
          status: game1Status,
          venue: "TD Garden",
          attendance: 19156,
          referees: ["Scott Foster", "Tony Brothers", "Courtney Kirkland"],
          gameImportance: "Rivalry",
          nationalTV: true
        },
        { 
          gameId: "G20240320_GSWDEN", 
          date: gameDate2.toISOString().split('T')[0], 
          time: "9:30 PM EST", 
          homeTeamId: "T03", 
          homeTeamName: "Denver Nuggets", 
          homeTeamAbbr: "DEN", 
          homeTeamScore: game2Status !== "Scheduled" ? 118 : 0, 
          awayTeamId: "T04", 
          awayTeamName: "Golden State Warriors", 
          awayTeamAbbr: "GSW", 
          awayTeamScore: game2Status !== "Scheduled" ? 112 : 0, 
          status: game2Status,
          venue: "Ball Arena",
          attendance: 19520,
          referees: ["Marc Davis", "Mitchell Ervin", "Phenizee Ransom"],
          gameImportance: "Playoff Race",
          nationalTV: false
        },
        { 
          gameId: "G20240321_MILPHI", 
          date: gameDate3.toISOString().split('T')[0], 
          time: "8:00 PM EST", 
          homeTeamId: "T05", 
          homeTeamName: "Philadelphia 76ers", 
          homeTeamAbbr: "PHI", 
          homeTeamScore: game3Status !== "Scheduled" ? 100 : 0, 
          awayTeamId: "T06", 
          awayTeamName: "Milwaukee Bucks", 
          awayTeamAbbr: "MIL", 
          awayTeamScore: game3Status !== "Scheduled" ? 102 : 0, 
          status: game3Status,
          venue: "Wells Fargo Center",
          attendance: 20478,
          referees: ["James Capers", "Tre Maddox", "Andy Nagy"],
          gameImportance: "Regular",
          nationalTV: false
        },
    ];
};

const mockGetGameDetailsAPI = async (gameId: string): Promise<GameInfo | null> => {
    console.log(`Fetching details for game: ${gameId}`);
    await new Promise(resolve => setTimeout(resolve, 300));
    const games = await mockGetRecentGamesAPI(); 
    let game = games.find(g => g.gameId === gameId);

    if (game) {
        let gameDateTime;
        try {
            let hours = parseInt(game.time.split(':')[0]);
            const minutes = parseInt(game.time.split(':')[1].split(' ')[0]);
            const isPM = game.time.includes('PM');
            if (isPM && hours !== 12) hours += 12;
            if (!isPM && hours === 12) hours = 0; 
            gameDateTime = new Date(game.date);
            gameDateTime.setHours(hours, minutes, 0, 0);

            const newStatus = determineGameStatus(gameDateTime, game.status);

            if (newStatus !== game.status) {
                 game = { ...game, status: newStatus };
            }

            if (newStatus !== "Scheduled" && newStatus !== "Final") { 
                game = {
                    ...game,
                    livePeriod: newStatus.includes("Q1") ? 1 : newStatus.includes("Q2") ? 2 : newStatus.includes("Halftime") ? 2 : newStatus.includes("Q3") ? 3 : newStatus.includes("Q4") ? 4 : newStatus.includes("OT") ? 5 : undefined,
                    liveClock: newStatus.includes("Halftime") ? "00:00" : `${Math.floor(Math.random()*10)}:${('0' + Math.floor(Math.random()*60)).slice(-2)}`,
                    homeTeamScore: game.homeTeamScore || Math.floor(Math.random() * 30) + 40,
                    awayTeamScore: game.awayTeamScore || Math.floor(Math.random() * 30) + 40,
                };
            } else if (newStatus === "Final" && game.status !== "Final") {
                 game = {
                    ...game,
                    status: "Final",
                    homeTeamScore: game.homeTeamScore || Math.floor(Math.random() * 20) + 90, 
                    awayTeamScore: game.awayTeamScore || Math.floor(Math.random() * 20) + 90,
                    livePeriod: undefined,
                    liveClock: undefined,
                };
            }

        } catch (e) {
            console.error("Error processing game time for details: ", e);
        }
    }
    return game || null;
};

const mockGetBoxScoreAPI = async (gameId: string): Promise<BoxScorePlayerStats[]> => {
    await new Promise(resolve => setTimeout(resolve, 500));
    const basePlayers = [
        { pId: "P1", pName: "LeBron James", starter: true, pos: "F" }, 
        { pId: "P2", pName: "Anthony Davis", starter: true, pos: "C" },
        { pId: "P3", pName: "Russell Westbrook", starter: true, pos: "G" }, 
        { pId: "P4", pName: "Austin Reaves", starter: true, pos: "G" },
        { pId: "P5", pName: "Jarred Vanderbilt", starter: true, pos: "F" }, 
        { pId: "P6", pName: "Malik Monk", starter: false, pos: "G" },
        { pId: "P7", pName: "Carmelo Anthony", starter: false, pos: "F" }, 
        { pId: "P8", pName: "Dwight Howard", starter: false, pos: "C" },
    ];
    
    return basePlayers.map(p => {
        const isStarter = p.starter;
        const fgm = Math.floor(Math.random() * (isStarter ? 8 : 4)) + (isStarter ? 2 : 0);
        const fga = fgm + Math.floor(Math.random() * 6) + 2;
        const fg3m = Math.floor(Math.random() * (isStarter ? 4 : 2));
        const fg3a = fg3m + Math.floor(Math.random() * 3) + 1;
        const ftm = Math.floor(Math.random() * (isStarter ? 6 : 3));
        const fta = ftm + Math.floor(Math.random() * 2);
        const oreb = Math.floor(Math.random() * 3);
        const dreb = Math.floor(Math.random() * 6) + 2;
        const reb = oreb + dreb;
        const pts = (fgm * 2) + fg3m + ftm;
        
        return {
            playerId: p.pId, 
            playerName: p.pName, 
            starter: p.starter,
            minutes: isStarter ? `${Math.floor(Math.random() * 8) + 28}:${String(Math.floor(Math.random() * 60)).padStart(2,'0')}` : `${Math.floor(Math.random() * 15) + 10}:${String(Math.floor(Math.random() * 60)).padStart(2,'0')}`,
            fgm, fga, fgPct: fga > 0 ? fgm / fga : 0,
            fg3m, fg3a, fg3Pct: fg3a > 0 ? fg3m / fg3a : 0,
            ftm, fta, ftPct: fta > 0 ? ftm / fta : 0,
            oreb, dreb, reb,
            ast: Math.floor(Math.random() * (isStarter ? 6 : 2)) + 1, 
            stl: Math.floor(Math.random() * 3), 
            blk: Math.floor(Math.random() * 2),
            tov: Math.floor(Math.random() * 4), 
            pf: Math.floor(Math.random() * 4), 
            pts,
            plusMinus: Math.floor(Math.random() * 21) - 10, // -10 to +10
            
            // Advanced impact metrics
            impactRating: Math.random() * 4 + (isStarter ? 6 : 4), // 4-10 for starters, 4-8 for bench
            clutchPerformance: Math.random() * 100,
            efficiencyRating: Math.random() * 40 + 60, // 60-100
            defenseGrade: ['A+', 'A', 'B+', 'B', 'C+', 'C', 'D', 'F'][Math.floor(Math.random() * 8)] as 'A+' | 'A' | 'B+' | 'B' | 'C+' | 'C' | 'D' | 'F',
            momentumPlays: Math.floor(Math.random() * (isStarter ? 4 : 2))
        };
    });
};

const mockGetPlayByPlayAPI = async (gameId: string): Promise<PlayByPlayEntry[]> => {
    await new Promise(resolve => setTimeout(resolve, 600));
    return [
        { 
          id: "PBP1", 
          period: "Q4", 
          clock: "2:45", 
          teamAbbr: "LAL", 
          description: "LeBron James makes driving layup", 
          score: "105-108",
          playType: "Shot",
          winProbabilityChange: 3.2,
          momentumImpact: "High",
          aiInsight: "Crucial basket in final minutes - LeBron showing championship experience",
          keyPlay: true
        },
        { 
          id: "PBP2", 
          period: "Q4", 
          clock: "2:30", 
          teamAbbr: "BOS", 
          description: "Jayson Tatum misses 3PT shot", 
          playType: "Shot",
          winProbabilityChange: -2.1,
          momentumImpact: "Medium",
          aiInsight: "Missed opportunity to extend lead in crucial moment",
          keyPlay: false
        },
        { 
          id: "PBP3", 
          period: "Q4", 
          clock: "2:15", 
          teamAbbr: "LAL", 
          description: "Anthony Davis defensive rebound", 
          playType: "Other",
          winProbabilityChange: 1.1,
          momentumImpact: "Low",
          keyPlay: false
        }
    ];
};

const mockGetTeamGameStatsSummaryAPI = async (gameId: string, teamId: string): Promise<TeamGameStatsSummary> => {
    await new Promise(resolve => setTimeout(resolve, 400));
    const isHome = teamId.includes("Home") || Math.random() > 0.5;
    return {
        teamId,
        teamAbbr: isHome ? "BOS" : "LAL",
        fgPct: 0.47 + (Math.random() * 0.15),
        fg3Pct: 0.35 + (Math.random() * 0.15),
        ftPct: 0.78 + (Math.random() * 0.15),
        rebounds: Math.floor(Math.random() * 10) + 40,
        assists: Math.floor(Math.random() * 8) + 20,
        turnovers: Math.floor(Math.random() * 5) + 12,
        
        // Advanced metrics
        possessions: Math.floor(Math.random() * 10) + 95,
        pace: Math.random() * 5 + 98,
        offensiveRating: Math.random() * 15 + 110,
        defensiveRating: Math.random() * 15 + 105,
        effectiveFgPct: 0.52 + (Math.random() * 0.12),
        trueShootingPct: 0.56 + (Math.random() * 0.12),
        assistTurnoverRatio: Math.random() * 1.0 + 1.5,
        reboundingRate: Math.random() * 0.1 + 0.48,
        
        // Game flow metrics
        fastBreakPoints: Math.floor(Math.random() * 10) + 8,
        pointsInPaint: Math.floor(Math.random() * 15) + 35,
        secondChancePoints: Math.floor(Math.random() * 8) + 6,
        benchPoints: Math.floor(Math.random() * 20) + 25,
        biggestLead: Math.floor(Math.random() * 12) + 5,
        timeWithLead: `${Math.floor(Math.random() * 30) + 15}:${String(Math.floor(Math.random() * 60)).padStart(2, '0')}`,
        leadChanges: Math.floor(Math.random() * 8) + 3
    };
};

const mockGetWinProbabilityAPI = async (gameId: string): Promise<WinProbabilityDataPoint[]> => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return [
        { 
          time: "Start", 
          homeWinProb: 0.52, 
          awayWinProb: 0.48,
          keyEvent: "Game starts",
          volatility: 5,
          clutchFactor: 10
        },
        { 
          time: "Q1 6:00", 
          homeWinProb: 0.58, 
          awayWinProb: 0.42,
          keyEvent: "8-0 run by home team",
          volatility: 12,
          clutchFactor: 15
        },
        { 
          time: "Q2 3:00", 
          homeWinProb: 0.45, 
          awayWinProb: 0.55,
          keyEvent: "Away team takes lead",
          volatility: 18,
          clutchFactor: 25
        },
        { 
          time: "Halftime", 
          homeWinProb: 0.48, 
          awayWinProb: 0.52,
          keyEvent: "Close at half",
          volatility: 8,
          clutchFactor: 30
        },
        { 
          time: "Q3 9:00", 
          homeWinProb: 0.62, 
          awayWinProb: 0.38,
          keyEvent: "Third quarter surge",
          volatility: 22,
          clutchFactor: 40
        },
        { 
          time: "Q4 5:00", 
          homeWinProb: 0.35, 
          awayWinProb: 0.65,
          keyEvent: "Away team pulling away",
          volatility: 25,
          clutchFactor: 70
        },
        { 
          time: "Q4 2:00", 
          homeWinProb: 0.28, 
          awayWinProb: 0.72,
          keyEvent: "Clutch time advantage",
          volatility: 35,
          clutchFactor: 95
        },
        { 
          time: "Final", 
          homeWinProb: 0.0, 
          awayWinProb: 1.0,
          keyEvent: "Game over",
          volatility: 0,
          clutchFactor: 100
        }
    ];
};

// New API functions for advanced analytics
const mockGetPlayerMatchupsAPI = async (gameId: string): Promise<PlayerMatchup[]> => {
    await new Promise(resolve => setTimeout(resolve, 700));
    return [
        {
            offensivePlayer: { id: "P1", name: "LeBron James", position: "F" },
            defensivePlayer: { id: "P21", name: "Jayson Tatum", position: "F" },
            possessions: 18,
            points: 12,
            fgAttempts: 8,
            fgMade: 5,
            efficiency: 62.5,
            advantageRating: 3.2,
            keyMoments: ["4th quarter clutch drive", "3rd quarter momentum shift"]
        },
        {
            offensivePlayer: { id: "P2", name: "Anthony Davis", position: "C" },
            defensivePlayer: { id: "P22", name: "Robert Williams", position: "C" },
            possessions: 15,
            points: 18,
            fgAttempts: 10,
            fgMade: 8,
            efficiency: 80.0,
            advantageRating: 6.1,
            keyMoments: ["Dominant paint presence", "Key defensive stops"]
        },
        {
            offensivePlayer: { id: "P21", name: "Jayson Tatum", position: "F" },
            defensivePlayer: { id: "P4", name: "Austin Reaves", position: "G" },
            possessions: 22,
            points: 24,
            fgAttempts: 15,
            fgMade: 9,
            efficiency: 60.0,
            advantageRating: 4.8,
            keyMoments: ["Exploited size advantage", "Fourth quarter takeover"]
        }
    ];
};

const mockGetMomentumDataAPI = async (gameId: string): Promise<MomentumData[]> => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return [
        {
            timestamp: "Q1 8:45",
            homeTeamMomentum: 15,
            awayTeamMomentum: -15,
            triggerEvent: "8-0 run by Boston",
            significance: "Moderate"
        },
        {
            timestamp: "Q2 3:20",
            homeTeamMomentum: -25,
            awayTeamMomentum: 25,
            triggerEvent: "LeBron 3-pointer + steal",
            significance: "Major"
        },
        {
            timestamp: "Q3 6:15",
            homeTeamMomentum: 35,
            awayTeamMomentum: -35,
            triggerEvent: "Tatum back-to-back threes",
            significance: "Major"
        },
        {
            timestamp: "Q4 2:45",
            homeTeamMomentum: -30,
            awayTeamMomentum: 30,
            triggerEvent: "AD block + LeBron dunk",
            significance: "Major"
        }
    ];
};

const mockGetGameInsightsAPI = async (gameId: string): Promise<GameInsight[]> => {
    await new Promise(resolve => setTimeout(resolve, 600));
    return [
        {
            id: "INS1",
            type: "trend",
            priority: "critical",
            title: "Lakers Exploiting Boston's Paint Defense",
            description: "LA has scored 58 points in the paint vs Boston's season average of 42 allowed. Davis is dominating the interior.",
            confidence: 92,
            timestamp: "Q4 5:23",
            relatedPlayers: ["Anthony Davis", "LeBron James"],
            impactLevel: "Game-Changing"
        },
        {
            id: "INS2",
            type: "prediction",
            priority: "high",
            title: "Fourth Quarter Fatigue Factor",
            description: "Both teams showing signs of fatigue. Expect increased turnovers and decreased shooting efficiency in final 6 minutes.",
            confidence: 78,
            timestamp: "Q4 6:00",
            impactLevel: "Significant"
        },
        {
            id: "INS3",
            type: "key_player",
            priority: "high",
            title: "Tatum's Clutch Time Performance",
            description: "Jayson Tatum is 4/6 from three in clutch situations this season. He's the key to Boston's comeback chances.",
            confidence: 85,
            timestamp: "Q4 4:12",
            relatedPlayers: ["Jayson Tatum"],
            impactLevel: "Game-Changing"
        },
        {
            id: "INS4",
            type: "strategy",
            priority: "medium",
            title: "Lineup Adjustment Needed",
            description: "Boston should consider going small to match LA's pace. Current lineup is struggling with defensive rotations.",
            confidence: 71,
            timestamp: "Q4 7:30",
            impactLevel: "Notable"
        }
    ];
};

export default function GameCenterPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const gameIdParam = searchParams.get('game');

  // Existing state
  const [gameDate, setGameDate] = useState<string>(() => {
    const today = new Date();
    return today.toISOString().split('T')[0];
  });
  const [games, setGames] = useState<GameInfo[]>([]);
  const [selectedGame, setSelectedGame] = useState<GameInfo | null>(null);
  const [gameDetails, setGameDetails] = useState<GameInfo | null>(null);
  const [boxScoreData, setBoxScoreData] = useState<BoxScorePlayerStats[]>([]);
  const [playByPlayData, setPlayByPlayData] = useState<PlayByPlayEntry[]>([]);
  const [teamStatsHome, setTeamStatsHome] = useState<TeamGameStatsSummary | null>(null);
  const [teamStatsAway, setTeamStatsAway] = useState<TeamGameStatsSummary | null>(null);
  const [winProbData, setWinProbData] = useState<WinProbabilityDataPoint[]>([]);
  
  // New advanced analytics state
  const [playerMatchups, setPlayerMatchups] = useState<PlayerMatchup[]>([]);
  const [momentumData, setMomentumData] = useState<MomentumData[]>([]);
  const [gameInsights, setGameInsights] = useState<GameInsight[]>([]);
  const [selectedMatchup, setSelectedMatchup] = useState<PlayerMatchup | null>(null);

  // Loading states
  const [isLoadingGames, setIsLoadingGames] = useState(true);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [isLoadingBoxScore, setIsLoadingBoxScore] = useState(false);
  const [isLoadingPlayByPlay, setIsLoadingPlayByPlay] = useState(false);
  const [isLoadingAdvanced, setIsLoadingAdvanced] = useState(false);

  // Filter states for enhanced experience
  const [playTypeFilter, setPlayTypeFilter] = useState<string>("all");
  const [insightTypeFilter, setInsightTypeFilter] = useState<string>("all");

  const fetchGames = async () => {
    setIsLoadingGames(true);
    try {
      const fetchedGames = await mockGetRecentGamesAPI(gameDate);
      setGames(fetchedGames);
      
      if (fetchedGames.length > 0) {
        const gameToSelect = gameIdParam 
          ? fetchedGames.find(g => g.gameId === gameIdParam) || fetchedGames[0]
          : fetchedGames[0];
        setSelectedGame(gameToSelect);
      }
    } catch (error) {
      console.error("Error fetching games:", error);
    }
    setIsLoadingGames(false);
  };

  const fetchGameDetails = async (gameId: string) => {
    setIsLoadingDetails(true);
    try {
      const details = await mockGetGameDetailsAPI(gameId);
      setGameDetails(details);
    } catch (error) {
      console.error("Error fetching game details:", error);
    }
    setIsLoadingDetails(false);
  };

  const fetchAdvancedAnalytics = async (gameId: string) => {
    setIsLoadingAdvanced(true);
    try {
      const [matchups, momentum, insights] = await Promise.all([
        mockGetPlayerMatchupsAPI(gameId),
        mockGetMomentumDataAPI(gameId),
        mockGetGameInsightsAPI(gameId)
      ]);
      
      setPlayerMatchups(matchups);
      setMomentumData(momentum);
      setGameInsights(insights);
    } catch (error) {
      console.error("Error fetching advanced analytics:", error);
    }
    setIsLoadingAdvanced(false);
  };

  useEffect(() => {
    fetchGames();
  }, [gameDate]);

  useEffect(() => {
    if (selectedGame) {
      const loadGameData = async () => {
        await fetchGameDetails(selectedGame.gameId);
        
        // Load basic game data
        setIsLoadingBoxScore(true);
        setIsLoadingPlayByPlay(true);
        
        try {
          const [boxScore, playByPlay, homeStats, awayStats, winProb] = await Promise.all([
            mockGetBoxScoreAPI(selectedGame.gameId),
            mockGetPlayByPlayAPI(selectedGame.gameId),
            mockGetTeamGameStatsSummaryAPI(selectedGame.gameId, selectedGame.homeTeamId),
            mockGetTeamGameStatsSummaryAPI(selectedGame.gameId, selectedGame.awayTeamId),
            mockGetWinProbabilityAPI(selectedGame.gameId)
          ]);
          
          setBoxScoreData(boxScore);
          setPlayByPlayData(playByPlay);
          setTeamStatsHome(homeStats);
          setTeamStatsAway(awayStats);
          setWinProbData(winProb);
        } catch (error) {
          console.error("Error loading game data:", error);
        }
        
        setIsLoadingBoxScore(false);
        setIsLoadingPlayByPlay(false);
        
        // Load advanced analytics
        await fetchAdvancedAnalytics(selectedGame.gameId);
      };
      
      loadGameData();
    }
  }, [selectedGame]);

  const handleGameSelect = async (gameId: string) => {
    const game = games.find(g => g.gameId === gameId);
    setSelectedGame(game || null);
    
    // Update URL
    const params = new URLSearchParams(searchParams);
    if (game) {
      params.set('game', gameId);
    } else {
      params.delete('game');
    }
    router.push(`/game-center?${params.toString()}`);
  };

  const formatDateForInput = (dateStr: string) => {
    return dateStr; // Already in YYYY-MM-DD format
  };

  // Helper functions for UI
  const getGameStatusBadge = (status: GameInfo["status"]) => {
    const variants: Record<GameInfo["status"], string> = {
      "Scheduled": "secondary",
      "Live Q1": "destructive",
      "Live Q2": "destructive", 
      "Live Q3": "destructive",
      "Live Q4": "destructive",
      "Halftime": "outline",
      "OT": "destructive",
      "Final": "default"
    };
    
    return (
      <Badge variant={variants[status] as any} className="ml-2">
        {status.includes("Live") ? (
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
            {status}
          </div>
        ) : status}
      </Badge>
    );
  };

  const getImportanceBadge = (importance?: GameInfo["gameImportance"]) => {
    if (!importance || importance === 'Regular') return null;
    
    const colors = {
      'Rivalry': 'bg-orange-500',
      'Playoff Race': 'bg-blue-500',
      'Playoff': 'bg-purple-500',
      'Finals': 'bg-gold-500'
    };
    
    return (
      <Badge className={`${colors[importance]} text-white ml-2`}>
        {importance}
      </Badge>
    );
  };

  const getMomentumColor = (momentum: number) => {
    const intensity = Math.abs(momentum);
    if (intensity > 30) return momentum > 0 ? 'text-green-600' : 'text-red-600';
    if (intensity > 15) return momentum > 0 ? 'text-green-500' : 'text-red-500';
    return 'text-gray-500';
  };

  const getInsightPriorityIcon = (priority: GameInsight["priority"]) => {
    switch (priority) {
      case 'critical': return <AlertTriangle className="w-4 h-4 text-red-500" />;
      case 'high': return <Brain className="w-4 h-4 text-orange-500" />;
      case 'medium': return <Eye className="w-4 h-4 text-blue-500" />;
      case 'low': return <Activity className="w-4 h-4 text-gray-500" />;
      default: return <Activity className="w-4 h-4" />;
    }
  };

  const filteredPlayByPlay = playByPlayData.filter(play => 
    playTypeFilter === "all" || play.playType === playTypeFilter
  );

  const filteredInsights = gameInsights.filter(insight =>
    insightTypeFilter === "all" || insight.type === insightTypeFilter
  );

  return (
    <div className="flex-1 space-y-6 p-4 md:p-6 lg:p-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Game Center</h1>
          <p className="text-muted-foreground">Real-time game analytics and insights powered by Dime AI</p>
        </div>
        
        <div className="flex items-center space-x-2">
          <Input
            type="date"
            value={formatDateForInput(gameDate)}
            onChange={(e) => setGameDate(e.target.value)}
            className="w-40"
          />
          <Button variant="outline" size="sm">
            <CalendarDays className="w-4 h-4 mr-2" />
            Today
          </Button>
        </div>
      </div>

      {/* Game Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Tv className="w-5 h-5" />
            Games for {new Date(gameDate).toLocaleDateString()}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoadingGames ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : games.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No games scheduled for this date
            </p>
          ) : (
            <div className="space-y-2">
              {games.map((game) => (
                <Card 
                  key={game.gameId} 
                  className={`cursor-pointer transition-colors hover:bg-accent ${
                    selectedGame?.gameId === game.gameId ? 'bg-accent border-primary' : ''
                  }`}
                  onClick={() => handleGameSelect(game.gameId)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-4">
                        <div className="text-center">
                          <div className="font-semibold">{game.awayTeamAbbr}</div>
                          <div className="text-2xl font-bold">{game.awayTeamScore}</div>
                        </div>
                        <div className="text-muted-foreground">@</div>
                        <div className="text-center">
                          <div className="font-semibold">{game.homeTeamAbbr}</div>
                          <div className="text-2xl font-bold">{game.homeTeamScore}</div>
                        </div>
                      </div>
                      
                      <div className="flex items-center">
                        <div className="text-right mr-4">
                          <div className="text-sm text-muted-foreground">{game.time}</div>
                          {game.venue && (
                            <div className="text-xs text-muted-foreground">{game.venue}</div>
                          )}
                        </div>
                        <div className="flex flex-col items-end">
                          {getGameStatusBadge(game.status)}
                          {getImportanceBadge(game.gameImportance)}
                          {game.nationalTV && (
                            <Badge variant="outline" className="mt-1">
                              <Tv className="w-3 h-3 mr-1" />
                              National TV
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Selected Game Details Section */} 
      {isLoadingDetails && selectedGame && (
        <Skeleton className="h-[600px] w-full" />
      )}
      {!isLoadingDetails && selectedGame && (
        <Card className="shadow-xl">
            <CardHeader className="bg-muted/30">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center">
                    <div>
                        <CardTitle className="text-xl">{selectedGame.awayTeamName} vs {selectedGame.homeTeamName}</CardTitle>
                        <CardDescription>{new Date(selectedGame.date).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })} at {selectedGame.time}</CardDescription>
                    </div>
                     <Badge variant={(selectedGame.status.startsWith("Live") || selectedGame.status === "OT") ? "destructive" : "secondary"} className="mt-2 sm:mt-0 text-md px-4 py-1.5">
                        {selectedGame.status}{(selectedGame.status.startsWith("Live") || selectedGame.status === "OT") && ` - ${selectedGame.livePeriod} ${selectedGame.liveClock}`}
                    </Badge>
                </div>
                 <div className="flex justify-center items-baseline space-x-4 mt-4 text-center">
                    <div className="flex flex-col items-center w-1/3">
                        <span className="text-3xl md:text-4xl font-bold">{selectedGame.awayTeamScore ?? '-'}</span>
                        <span className="text-sm font-semibold text-muted-foreground">{selectedGame.awayTeamAbbr}</span>
                    </div>
                     <span className="text-xl text-muted-foreground">-</span>
                    <div className="flex flex-col items-center w-1/3">
                        <span className="text-3xl md:text-4xl font-bold">{selectedGame.homeTeamScore ?? '-'}</span>
                        <span className="text-sm font-semibold text-muted-foreground">{selectedGame.homeTeamAbbr}</span>
                    </div>
                </div>
            </CardHeader>
            <Tabs defaultValue="ai_insights" className="w-full">
                <TabsList className="grid w-full grid-cols-6">
                    <TabsTrigger value="ai_insights" className="flex items-center gap-2">
                        <Brain className="w-4 h-4" />
                        AI Insights
                    </TabsTrigger>
                    <TabsTrigger value="momentum" className="flex items-center gap-2">
                        <Activity className="w-4 h-4" />
                        Momentum
                    </TabsTrigger>
                    <TabsTrigger value="matchups" className="flex items-center gap-2">
                        <Swords className="w-4 h-4" />
                        Matchups
                    </TabsTrigger>
                    <TabsTrigger value="advanced_box" className="flex items-center gap-2">
                        <Target className="w-4 h-4" />
                        Impact Metrics
                    </TabsTrigger>
                    <TabsTrigger value="play_analysis" className="flex items-center gap-2">
                        <Eye className="w-4 h-4" />
                        Play Analysis
                    </TabsTrigger>
                    <TabsTrigger value="team_analytics" className="flex items-center gap-2">
                        <BarChartHorizontalBig className="w-4 h-4" />
                        Team Analytics
                    </TabsTrigger>
                </TabsList>

                {/* AI Insights Tab */}
                <TabsContent value="ai_insights" className="space-y-4">
                    <div className="flex items-center justify-between">
                        <h3 className="text-lg font-semibold flex items-center gap-2">
                            <Brain className="w-5 h-5 text-blue-500" />
                            Dime's Game Intelligence
                        </h3>
                        <Select value={insightTypeFilter} onValueChange={setInsightTypeFilter}>
                            <SelectTrigger className="w-48">
                                <SelectValue placeholder="Filter insights" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All Insights</SelectItem>
                                <SelectItem value="trend">Trends</SelectItem>
                                <SelectItem value="prediction">Predictions</SelectItem>
                                <SelectItem value="key_player">Key Players</SelectItem>
                                <SelectItem value="strategy">Strategy</SelectItem>
                                <SelectItem value="momentum">Momentum</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {isLoadingAdvanced ? (
                        <div className="space-y-4">
                            {Array.from({ length: 4 }).map((_, i) => (
                                <Skeleton key={i} className="h-24 w-full" />
                            ))}
                        </div>
                    ) : (
                        <div className="grid gap-4">
                            {filteredInsights.map((insight) => (
                                <Card key={insight.id} className="border-l-4 border-l-blue-500">
                                    <CardContent className="p-4">
                                        <div className="flex items-start justify-between">
                                            <div className="flex items-center gap-3">
                                                {getInsightPriorityIcon(insight.priority)}
                                                <div>
                                                    <h4 className="font-semibold text-sm">{insight.title}</h4>
                                                    <p className="text-sm text-muted-foreground mt-1">{insight.description}</p>
                                                </div>
                                            </div>
                                            <div className="flex flex-col items-end gap-2">
                                                <Badge variant="outline">
                                                    {insight.confidence}% confidence
                                                </Badge>
                                                <Badge 
                                                    variant={insight.impactLevel === 'Game-Changing' ? 'destructive' : 
                                                            insight.impactLevel === 'Significant' ? 'default' : 'secondary'}
                                                >
                                                    {insight.impactLevel}
                                                </Badge>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
                                            <span className="flex items-center gap-1">
                                                <Clock className="w-3 h-3" />
                                                {insight.timestamp}
                                            </span>
                                            {insight.relatedPlayers && insight.relatedPlayers.length > 0 && (
                                                <span className="flex items-center gap-1">
                                                    <Users className="w-3 h-3" />
                                                    {insight.relatedPlayers.join(', ')}
                                                </span>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </TabsContent>

                {/* Momentum Tab */}
                <TabsContent value="momentum" className="space-y-4">
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                        <Activity className="w-5 h-5 text-green-500" />
                        Game Momentum Tracking
                    </h3>

                    {isLoadingAdvanced ? (
                        <Skeleton className="h-80 w-full" />
                    ) : (
                        <div className="space-y-4">
                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-sm">Live Momentum</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="space-y-3">
                                        {momentumData.map((momentum, index) => (
                                            <div key={index} className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                                                <div className="flex items-center gap-3">
                                                    <div className="text-sm font-mono">{momentum.timestamp}</div>
                                                    <div className="text-sm">{momentum.triggerEvent}</div>
                                                </div>
                                                <div className="flex items-center gap-3">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-xs">{selectedGame.homeTeamAbbr}</span>
                                                        <Progress 
                                                            value={Math.abs(momentum.homeTeamMomentum)} 
                                                            className="w-20 h-2" 
                                                        />
                                                        <span className={`text-sm font-semibold ${getMomentumColor(momentum.homeTeamMomentum)}`}>
                                                            {momentum.homeTeamMomentum > 0 ? '+' : ''}{momentum.homeTeamMomentum}
                                                        </span>
                                                    </div>
                                                    <Badge variant={momentum.significance === 'Major' ? 'destructive' : 
                                                                    momentum.significance === 'Moderate' ? 'default' : 'secondary'}>
                                                        {momentum.significance}
                                                    </Badge>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    )}
                </TabsContent>

                {/* Player Matchups Tab */}
                <TabsContent value="matchups" className="space-y-4">
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                        <Swords className="w-5 h-5 text-orange-500" />
                        Player Matchup Analysis
                    </h3>

                    {isLoadingAdvanced ? (
                        <div className="grid gap-4">
                            {Array.from({ length: 3 }).map((_, i) => (
                                <Skeleton key={i} className="h-32 w-full" />
                            ))}
                        </div>
                    ) : (
                        <div className="grid gap-4">
                            {playerMatchups.map((matchup, index) => (
                                <Card 
                                    key={index} 
                                    className={`cursor-pointer transition-colors hover:bg-accent ${
                                        selectedMatchup === matchup ? 'bg-accent border-primary' : ''
                                    }`}
                                    onClick={() => setSelectedMatchup(matchup)}
                                >
                                    <CardContent className="p-4">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-4">
                                                <div className="text-center">
                                                    <div className="font-semibold text-sm">{matchup.offensivePlayer.name}</div>
                                                    <div className="text-xs text-muted-foreground">{matchup.offensivePlayer.position}</div>
                                                    <div className="text-xs">Offense</div>
                                                </div>
                                                <div className="text-muted-foreground">
                                                    <Crosshair className="w-4 h-4" />
                                                </div>
                                                <div className="text-center">
                                                    <div className="font-semibold text-sm">{matchup.defensivePlayer.name}</div>
                                                    <div className="text-xs text-muted-foreground">{matchup.defensivePlayer.position}</div>
                                                    <div className="text-xs">Defense</div>
                                                </div>
                                            </div>
                                            
                                            <div className="flex items-center gap-6">
                                                <div className="text-center">
                                                    <div className="text-lg font-bold">{matchup.points}</div>
                                                    <div className="text-xs text-muted-foreground">Points</div>
                                                </div>
                                                <div className="text-center">
                                                    <div className="text-lg font-bold">{matchup.fgMade}/{matchup.fgAttempts}</div>
                                                    <div className="text-xs text-muted-foreground">FG</div>
                                                </div>
                                                <div className="text-center">
                                                    <div className="text-lg font-bold">{matchup.efficiency.toFixed(1)}%</div>
                                                    <div className="text-xs text-muted-foreground">Efficiency</div>
                                                </div>
                                                <div className="text-center">
                                                    <div className={`text-lg font-bold ${
                                                        matchup.advantageRating > 3 ? 'text-green-600' : 
                                                        matchup.advantageRating < -3 ? 'text-red-600' : 'text-gray-600'
                                                    }`}>
                                                        {matchup.advantageRating > 0 ? '+' : ''}{matchup.advantageRating}
                                                    </div>
                                                    <div className="text-xs text-muted-foreground">Advantage</div>
                                                </div>
                                            </div>
                                        </div>
                                        
                                        {selectedMatchup === matchup && (
                                            <div className="mt-4 pt-4 border-t">
                                                <h5 className="font-semibold text-sm mb-2">Key Moments:</h5>
                                                <div className="space-y-1">
                                                    {matchup.keyMoments.map((moment, i) => (
                                                        <div key={i} className="text-sm text-muted-foreground">
                                                            • {moment}
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </TabsContent>

                {/* Advanced Box Score Tab */}
                <TabsContent value="advanced_box" className="space-y-4">
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                        <Target className="w-5 h-5 text-purple-500" />
                        Impact Metrics & Advanced Stats
                    </h3>

                    {isLoadingBoxScore ? (
                        <Skeleton className="h-96 w-full" />
                    ) : (
                        <div className="space-y-6">
                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-sm">{selectedGame.awayTeamName} - Impact Leaders</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="overflow-x-auto">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Player</TableHead>
                                                    <TableHead>MIN</TableHead>
                                                    <TableHead>PTS</TableHead>
                                                    <TableHead>Impact</TableHead>
                                                    <TableHead>Efficiency</TableHead>
                                                    <TableHead>Defense</TableHead>
                                                    <TableHead>Clutch</TableHead>
                                                    <TableHead>+/-</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {boxScoreData.slice(0, 5).map((player) => (
                                                    <TableRow key={player.playerId}>
                                                        <TableCell className="font-medium">{player.playerName}</TableCell>
                                                        <TableCell>{player.minutes}</TableCell>
                                                        <TableCell>{player.pts}</TableCell>
                                                        <TableCell>
                                                            <div className="flex items-center gap-2">
                                                                <Progress value={(player.impactRating || 0) * 10} className="w-12 h-2" />
                                                                <span className="text-sm">{(player.impactRating || 0).toFixed(1)}</span>
                                                            </div>
                                                        </TableCell>
                                                        <TableCell>
                                                            <span className={`${
                                                                (player.efficiencyRating || 0) > 80 ? 'text-green-600' : 
                                                                (player.efficiencyRating || 0) > 60 ? 'text-yellow-600' : 'text-red-600'
                                                            }`}>
                                                                {(player.efficiencyRating || 0).toFixed(0)}
                                                            </span>
                                                        </TableCell>
                                                        <TableCell>
                                                            <Badge variant="outline">{player.defenseGrade}</Badge>
                                                        </TableCell>
                                                        <TableCell>
                                                            <Progress value={player.clutchPerformance || 0} className="w-12 h-2" />
                                                        </TableCell>
                                                        <TableCell className={`${
                                                            (player.plusMinus || 0) > 0 ? 'text-green-600' : 
                                                            (player.plusMinus || 0) < 0 ? 'text-red-600' : 'text-gray-600'
                                                        }`}>
                                                            {player.plusMinus || 0 > 0 ? '+' : ''}{player.plusMinus || 0}
                                                        </TableCell>
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    )}
                </TabsContent>

                {/* Play Analysis Tab */}
                <TabsContent value="play_analysis" className="space-y-4">
                    <div className="flex items-center justify-between">
                        <h3 className="text-lg font-semibold flex items-center gap-2">
                            <Eye className="w-5 h-5 text-indigo-500" />
                            AI-Enhanced Play Analysis
                        </h3>
                        <Select value={playTypeFilter} onValueChange={setPlayTypeFilter}>
                            <SelectTrigger className="w-48">
                                <SelectValue placeholder="Filter plays" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All Plays</SelectItem>
                                <SelectItem value="Shot">Shots</SelectItem>
                                <SelectItem value="Turnover">Turnovers</SelectItem>
                                <SelectItem value="Foul">Fouls</SelectItem>
                                <SelectItem value="Timeout">Timeouts</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {isLoadingPlayByPlay ? (
                        <Skeleton className="h-96 w-full" />
                    ) : (
                        <div className="space-y-3">
                            {filteredPlayByPlay.map((play) => (
                                <Card key={play.id} className={`${play.keyPlay ? 'border-l-4 border-l-yellow-500' : ''}`}>
                                    <CardContent className="p-4">
                                        <div className="flex items-start justify-between">
                                            <div className="flex items-center gap-4">
                                                <div className="text-center min-w-[60px]">
                                                    <div className="font-mono text-sm">{play.period}</div>
                                                    <div className="font-mono text-xs text-muted-foreground">{play.clock}</div>
                                                </div>
                                                <div className="flex-1">
                                                    <div className="flex items-center gap-2 mb-1">
                                                        <Badge variant="outline" className="text-xs">
                                                            {play.playType}
                                                        </Badge>
                                                        {play.teamAbbr && (
                                                            <span className="text-sm font-semibold">{play.teamAbbr}</span>
                                                        )}
                                                        {play.keyPlay && (
                                                            <Badge variant="default" className="text-xs">
                                                                <Award className="w-3 h-3 mr-1" />
                                                                Key Play
                                                            </Badge>
                                                        )}
                                                    </div>
                                                    <div className="text-sm">{play.description}</div>
                                                    {play.aiInsight && (
                                                        <div className="text-xs text-muted-foreground mt-2 p-2 bg-muted/30 rounded">
                                                            <Brain className="w-3 h-3 inline mr-1" />
                                                            {play.aiInsight}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                            
                                            <div className="flex items-center gap-4 min-w-[200px]">
                                                {play.score && (
                                                    <div className="text-sm font-mono">{play.score}</div>
                                                )}
                                                {play.winProbabilityChange && (
                                                    <div className="flex items-center gap-1">
                                                        {play.winProbabilityChange > 0 ? (
                                                            <ArrowUp className="w-3 h-3 text-green-500" />
                                                        ) : (
                                                            <ArrowDown className="w-3 h-3 text-red-500" />
                                                        )}
                                                        <span className={`text-xs ${
                                                            play.winProbabilityChange > 0 ? 'text-green-600' : 'text-red-600'
                                                        }`}>
                                                            {Math.abs(play.winProbabilityChange).toFixed(1)}%
                                                        </span>
                                                    </div>
                                                )}
                                                {play.momentumImpact && (
                                                    <Badge 
                                                        variant={play.momentumImpact === 'High' ? 'destructive' : 
                                                                play.momentumImpact === 'Medium' ? 'default' : 'secondary'}
                                                        className="text-xs"
                                                    >
                                                        {play.momentumImpact === 'High' ? (
                                                            <Flame className="w-3 h-3 mr-1" />
                                                        ) : play.momentumImpact === 'Medium' ? (
                                                            <Activity className="w-3 h-3 mr-1" />
                                                        ) : (
                                                            <Snowflake className="w-3 h-3 mr-1" />
                                                        )}
                                                        {play.momentumImpact}
                                                    </Badge>
                                                )}
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </TabsContent>

                {/* Team Analytics Tab */}
                <TabsContent value="team_analytics" className="space-y-4">
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                        <BarChartHorizontalBig className="w-5 h-5 text-cyan-500" />
                        Advanced Team Analytics
                    </h3>

                    {teamStatsHome && teamStatsAway ? (
                        <div className="grid gap-6">
                            {/* Team Comparison */}
                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-sm">Team Performance Comparison</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-2 gap-8">
                                        <div>
                                            <h4 className="font-semibold mb-4 text-center">{teamStatsHome.teamAbbr}</h4>
                                            <div className="space-y-3">
                                                <div className="flex justify-between items-center">
                                                    <span className="text-sm">Offensive Rating</span>
                                                    <span className="font-semibold">{teamStatsHome.offensiveRating.toFixed(1)}</span>
                                                </div>
                                                <div className="flex justify-between items-center">
                                                    <span className="text-sm">Defensive Rating</span>
                                                    <span className="font-semibold">{teamStatsHome.defensiveRating.toFixed(1)}</span>
                                                </div>
                                                <div className="flex justify-between items-center">
                                                    <span className="text-sm">Pace</span>
                                                    <span className="font-semibold">{teamStatsHome.pace.toFixed(1)}</span>
                                                </div>
                                                <div className="flex justify-between items-center">
                                                    <span className="text-sm">True Shooting %</span>
                                                    <span className="font-semibold">{(teamStatsHome.trueShootingPct * 100).toFixed(1)}%</span>
                                                </div>
                                                <div className="flex justify-between items-center">
                                                    <span className="text-sm">Fast Break Points</span>
                                                    <span className="font-semibold">{teamStatsHome.fastBreakPoints}</span>
                                                </div>
                                                <div className="flex justify-between items-center">
                                                    <span className="text-sm">Points in Paint</span>
                                                    <span className="font-semibold">{teamStatsHome.pointsInPaint}</span>
                                                </div>
                                            </div>
                                        </div>
                                        
                                        <div>
                                            <h4 className="font-semibold mb-4 text-center">{teamStatsAway.teamAbbr}</h4>
                                            <div className="space-y-3">
                                                <div className="flex justify-between items-center">
                                                    <span className="text-sm">Offensive Rating</span>
                                                    <span className="font-semibold">{teamStatsAway.offensiveRating.toFixed(1)}</span>
                                                </div>
                                                <div className="flex justify-between items-center">
                                                    <span className="text-sm">Defensive Rating</span>
                                                    <span className="font-semibold">{teamStatsAway.defensiveRating.toFixed(1)}</span>
                                                </div>
                                                <div className="flex justify-between items-center">
                                                    <span className="text-sm">Pace</span>
                                                    <span className="font-semibold">{teamStatsAway.pace.toFixed(1)}</span>
                                                </div>
                                                <div className="flex justify-between items-center">
                                                    <span className="text-sm">True Shooting %</span>
                                                    <span className="font-semibold">{(teamStatsAway.trueShootingPct * 100).toFixed(1)}%</span>
                                                </div>
                                                <div className="flex justify-between items-center">
                                                    <span className="text-sm">Fast Break Points</span>
                                                    <span className="font-semibold">{teamStatsAway.fastBreakPoints}</span>
                                                </div>
                                                <div className="flex justify-between items-center">
                                                    <span className="text-sm">Points in Paint</span>
                                                    <span className="font-semibold">{teamStatsAway.pointsInPaint}</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Game Flow Metrics */}
                            <div className="grid grid-cols-2 gap-4">
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="text-sm">Game Flow - {teamStatsHome.teamAbbr}</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-3">
                                            <div className="flex justify-between items-center">
                                                <span className="text-sm">Biggest Lead</span>
                                                <span className="font-semibold">{teamStatsHome.biggestLead}</span>
                                            </div>
                                            <div className="flex justify-between items-center">
                                                <span className="text-sm">Time with Lead</span>
                                                <span className="font-semibold">{teamStatsHome.timeWithLead}</span>
                                            </div>
                                            <div className="flex justify-between items-center">
                                                <span className="text-sm">Lead Changes</span>
                                                <span className="font-semibold">{teamStatsHome.leadChanges}</span>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                                
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="text-sm">Game Flow - {teamStatsAway.teamAbbr}</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-3">
                                            <div className="flex justify-between items-center">
                                                <span className="text-sm">Biggest Lead</span>
                                                <span className="font-semibold">{teamStatsAway.biggestLead}</span>
                                            </div>
                                            <div className="flex justify-between items-center">
                                                <span className="text-sm">Time with Lead</span>
                                                <span className="font-semibold">{teamStatsAway.timeWithLead}</span>
                                            </div>
                                            <div className="flex justify-between items-center">
                                                <span className="text-sm">Lead Changes</span>
                                                <span className="font-semibold">{teamStatsAway.leadChanges}</span>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    ) : (
                        <Skeleton className="h-96 w-full" />
                    )}
                </TabsContent>
            </Tabs>
        </Card>
      )}
      {!selectedGame && !isLoadingGames && (
        <p className="text-center text-muted-foreground py-10">Select a game to view details.</p>
      )}
    </div>
  );
}
