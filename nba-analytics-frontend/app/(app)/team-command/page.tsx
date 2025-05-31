"use client";

import React, { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
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
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { 
  ArrowLeft, Users, BarChart3, CalendarDays, Briefcase, ShieldCheck, Building, List,
  TrendingUp, TrendingDown, DollarSign, Target, Brain, AlertTriangle, Activity, 
  Zap, Star, Award, Trophy, Clock, ArrowUpDown, Calculator, Lightbulb, Eye,
  Flame, Settings, ChevronUp, ChevronDown, Plus, Minus
} from "lucide-react";

// --- Enhanced Data Structures ---
interface TeamDetails {
  id: string;
  fullName: string;
  abbreviation: string;
  nickname: string;
  city: string;
  conference: string;
  division: string;
  yearFounded?: number;
  arena?: string;
  headCoach?: string;
  generalManager?: string;
  logoUrl?: string;
  championships?: number[];
  currentRecord?: string;
  
  // Advanced team analytics
  payroll: number;
  salaryCap: number;
  luxuryTax: number;
  teamChemistry: number; // 0-100
  injuryRisk: 'Low' | 'Medium' | 'High';
  averageAge: number;
  veteranLeadership: number; // 0-100
  youthDevelopment: number; // 0-100
}

interface PlayerRosterEntry {
  id: string;
  fullName: string;
  jerseyNumber?: string;
  position: string;
  height: string;
  weight: string;
  age: number;
  experience: string;
  college?: string;
  
  // Contract & Financial
  salary: number;
  contractYears: number;
  tradeValue: number; // Market value
  
  // Performance metrics
  currentSeasonStats: {
    ppg: number;
    rpg: number;
    apg: number;
    per: number;
    ws: number;
    vorp: number;
  };
  
  // Advanced analytics
  impactRating: number; // 0-10
  injuryRisk: 'Low' | 'Medium' | 'High';
  developmentPotential: number; // 0-100 (for younger players)
  veteranLeadership: number; // 0-100 (for experienced players)
  teamChemistryImpact: number; // -10 to +10
  
  // Role and fit
  primaryRole: 'Superstar' | 'All-Star' | 'Starter' | 'Sixth Man' | 'Role Player' | 'Bench' | 'Development';
  positionFlexibility: string[]; // Multiple positions they can play
  offenseGrade: 'A+' | 'A' | 'B+' | 'B' | 'C+' | 'C' | 'D' | 'F';
  defenseGrade: 'A+' | 'A' | 'B+' | 'B' | 'C+' | 'C' | 'D' | 'F';
}

interface TeamStatSummary {
  offRtg: number;
  defRtg: number;
  netRtg: number;
  pace: number;
  efgPct: number;
  tovPct: number;
  rebPct: number;
  pie: number;
  
  // Advanced team metrics
  clutchRecord: string; // "12-8" in clutch situations
  homeRecord: string;
  awayRecord: string;
  vsPlayoffTeams: string;
  
  // Team strengths/weaknesses
  strengthAreas: string[];
  weaknessAreas: string[];
  improvementSuggestions: string[];
}

// Lineup analysis
interface LineupAnalysis {
  players: string[]; // 5 player names
  minutesTogether: number;
  plusMinus: number;
  netRating: number;
  offRating: number;
  defRating: number;
  usage: number; // How often this lineup is used
  effectiveness: 'Elite' | 'Good' | 'Average' | 'Poor';
  chemistryScore: number; // 0-100
  recommendations: string[];
}

// Trade scenario modeling
interface TradeScenario {
  id: string;
  description: string;
  outgoingPlayers: PlayerRosterEntry[];
  incomingPlayers: {
    name: string;
    position: string;
    salary: number;
    stats: any;
  }[];
  
  // Analysis
  salaryCapImpact: number;
  teamChemistryImpact: number; // -10 to +10
  winImpact: number; // Projected wins added/lost
  feasibilityScore: number; // 0-100, likelihood of trade happening
  pros: string[];
  cons: string[];
  aiRecommendation: 'Strongly Recommend' | 'Recommend' | 'Neutral' | 'Not Recommended' | 'Strongly Against';
}

// AI insights for team
interface TeamInsight {
  id: string;
  type: 'roster_move' | 'development' | 'chemistry' | 'strategy' | 'injury_management';
  priority: 'critical' | 'high' | 'medium' | 'low';
  title: string;
  description: string;
  actionable: boolean;
  confidence: number; // 0-100
  timeframe: 'Immediate' | 'Short-term' | 'Long-term';
  impactLevel: 'Game-Changing' | 'Significant' | 'Notable' | 'Minor';
  relatedPlayers?: string[];
}

// --- Enhanced Mock API Functions ---
const mockAllTeamsAPI = async (): Promise<TeamDetails[]> => {
    await new Promise(resolve => setTimeout(resolve, 200));
    return [
        { 
          id: "1610612737", 
          fullName: "Atlanta Hawks", 
          abbreviation: "ATL", 
          nickname: "Hawks", 
          city: "Atlanta", 
          conference: "Eastern", 
          division: "Southeast", 
          logoUrl: "/logos/atl.svg", 
          currentRecord: "36-46",
          payroll: 142500000,
          salaryCap: 155000000,
          luxuryTax: 0,
          teamChemistry: 72,
          injuryRisk: "Medium",
          averageAge: 26.3,
          veteranLeadership: 65,
          youthDevelopment: 78
        },
        { 
          id: "1610612738", 
          fullName: "Boston Celtics", 
          abbreviation: "BOS", 
          nickname: "Celtics", 
          city: "Boston", 
          conference: "Eastern", 
          division: "Atlantic", 
          logoUrl: "/logos/bos.svg", 
          currentRecord: "64-18",
          payroll: 175200000,
          salaryCap: 155000000,
          luxuryTax: 20200000,
          teamChemistry: 91,
          injuryRisk: "Low",
          averageAge: 27.1,
          veteranLeadership: 89,
          youthDevelopment: 74
        },
        { 
          id: "1610612747", 
          fullName: "Los Angeles Lakers", 
          abbreviation: "LAL", 
          nickname: "Lakers", 
          city: "Los Angeles", 
          conference: "Western", 
          division: "Pacific", 
          logoUrl: "/logos/lal.svg", 
          currentRecord: "47-35",
          payroll: 184300000,
          salaryCap: 155000000,
          luxuryTax: 29300000,
          teamChemistry: 79,
          injuryRisk: "High",
          averageAge: 29.8,
          veteranLeadership: 95,
          youthDevelopment: 58
        },
        { 
          id: "1610612744", 
          fullName: "Golden State Warriors", 
          abbreviation: "GSW", 
          nickname: "Warriors", 
          city: "Golden State", 
          conference: "Western", 
          division: "Pacific", 
          logoUrl: "/logos/gsw.svg", 
          currentRecord: "46-36",
          payroll: 193800000,
          salaryCap: 155000000,
          luxuryTax: 38800000,
          teamChemistry: 85,
          injuryRisk: "Medium",
          averageAge: 28.9,
          veteranLeadership: 92,
          youthDevelopment: 61
        },
        { 
          id: "1610612743", 
          fullName: "Denver Nuggets", 
          abbreviation: "DEN", 
          nickname: "Nuggets", 
          city: "Denver", 
          conference: "Western", 
          division: "Northwest", 
          logoUrl: "/logos/den.svg", 
          currentRecord: "57-25",
          payroll: 167900000,
          salaryCap: 155000000,
          luxuryTax: 12900000,
          teamChemistry: 94,
          injuryRisk: "Low",
          averageAge: 26.8,
          veteranLeadership: 82,
          youthDevelopment: 85
        },
    ];
};

const mockTeamDetailsAPI = async (teamId: string): Promise<TeamDetails | null> => {
    console.log(`Fetching Team Details for: ${teamId}`);
    await new Promise(resolve => setTimeout(resolve, 300));
    const allTeams = await mockAllTeamsAPI();
    return allTeams.find(t => t.id === teamId) || allTeams[0]; // Default to first if not found
};

const mockTeamRosterAPI = async (teamId: string): Promise<PlayerRosterEntry[]> => {
    await new Promise(resolve => setTimeout(resolve, 500));
    if (teamId === "1610612743") { // Denver Nuggets
        return [
            { 
              id: "P1", 
              fullName: "Jamal Murray", 
              jerseyNumber: "27", 
              position: "G", 
              height: "6-4", 
              weight: "215", 
              age: 27, 
              experience: "7th", 
              college: "Kentucky",
              salary: 36000000,
              contractYears: 3,
              tradeValue: 32000000,
              currentSeasonStats: {
                ppg: 20.3,
                rpg: 4.1,
                apg: 6.5,
                per: 18.7,
                ws: 8.2,
                vorp: 2.8
              },
              impactRating: 8.1,
              injuryRisk: "Medium",
              developmentPotential: 25,
              veteranLeadership: 78,
              teamChemistryImpact: 7,
              primaryRole: "All-Star",
              positionFlexibility: ["PG", "SG"],
              offenseGrade: "A",
              defenseGrade: "B+"
            },
            { 
              id: "P2", 
              fullName: "Kentavious Caldwell-Pope", 
              jerseyNumber: "5", 
              position: "G", 
              height: "6-5", 
              weight: "205", 
              age: 31, 
              experience: "11th", 
              college: "Georgia",
              salary: 14000000,
              contractYears: 1,
              tradeValue: 12000000,
              currentSeasonStats: {
                ppg: 10.1,
                rpg: 2.4,
                apg: 2.1,
                per: 11.8,
                ws: 4.1,
                vorp: 1.2
              },
              impactRating: 6.8,
              injuryRisk: "Low",
              developmentPotential: 5,
              veteranLeadership: 85,
              teamChemistryImpact: 6,
              primaryRole: "Starter",
              positionFlexibility: ["SG", "SF"],
              offenseGrade: "B",
              defenseGrade: "A"
            },
            { 
              id: "P3", 
              fullName: "Michael Porter Jr.", 
              jerseyNumber: "1", 
              position: "F", 
              height: "6-10", 
              weight: "218", 
              age: 25, 
              experience: "5th", 
              college: "Missouri",
              salary: 35700000,
              contractYears: 4,
              tradeValue: 28000000,
              currentSeasonStats: {
                ppg: 16.7,
                rpg: 7.1,
                apg: 1.5,
                per: 16.3,
                ws: 6.8,
                vorp: 1.9
              },
              impactRating: 7.4,
              injuryRisk: "High",
              developmentPotential: 45,
              veteranLeadership: 55,
              teamChemistryImpact: 4,
              primaryRole: "Starter",
              positionFlexibility: ["SF", "PF"],
              offenseGrade: "A",
              defenseGrade: "C+"
            },
            { 
              id: "P4", 
              fullName: "Aaron Gordon", 
              jerseyNumber: "50", 
              position: "F", 
              height: "6-8", 
              weight: "235", 
              age: 28, 
              experience: "10th", 
              college: "Arizona",
              salary: 22300000,
              contractYears: 2,
              tradeValue: 20000000,
              currentSeasonStats: {
                ppg: 13.9,
                rpg: 6.5,
                apg: 3.5,
                per: 16.1,
                ws: 7.3,
                vorp: 2.1
              },
              impactRating: 7.6,
              injuryRisk: "Low",
              developmentPotential: 15,
              veteranLeadership: 82,
              teamChemistryImpact: 8,
              primaryRole: "Starter",
              positionFlexibility: ["PF", "SF"],
              offenseGrade: "B+",
              defenseGrade: "A"
            },
            { 
              id: "P5", 
              fullName: "Nikola Jokic", 
              jerseyNumber: "15", 
              position: "C", 
              height: "7-0", 
              weight: "284", 
              age: 29, 
              experience: "9th", 
              college: "Mega Basket (Serbia)",
              salary: 47600000,
              contractYears: 4,
              tradeValue: 85000000,
              currentSeasonStats: {
                ppg: 26.4,
                rpg: 12.4,
                apg: 9.0,
                per: 32.1,
                ws: 15.7,
                vorp: 8.8
              },
              impactRating: 9.8,
              injuryRisk: "Low",
              developmentPotential: 10,
              veteranLeadership: 94,
              teamChemistryImpact: 10,
              primaryRole: "Superstar",
              positionFlexibility: ["C"],
              offenseGrade: "A+",
              defenseGrade: "B+"
            },
        ];
    }
    return [
        { 
          id: "PX1", 
          fullName: "Player One", 
          jerseyNumber: "10", 
          position: "G", 
          height: "6-2", 
          weight: "190", 
          age: 25, 
          experience: "3rd", 
          college: "State U",
          salary: 8000000,
          contractYears: 2,
          tradeValue: 6000000,
          currentSeasonStats: {
            ppg: 12.5,
            rpg: 3.2,
            apg: 4.8,
            per: 14.2,
            ws: 3.1,
            vorp: 1.1
          },
          impactRating: 6.2,
          injuryRisk: "Low",
          developmentPotential: 65,
          veteranLeadership: 35,
          teamChemistryImpact: 3,
          primaryRole: "Role Player",
          positionFlexibility: ["PG", "SG"],
          offenseGrade: "B",
          defenseGrade: "C+"
        },
        { 
          id: "PX2", 
          fullName: "Player Two", 
          jerseyNumber: "22", 
          position: "F", 
          height: "6-7", 
          weight: "220", 
          age: 28, 
          experience: "6th", 
          college: "Tech College",
          salary: 15000000,
          contractYears: 3,
          tradeValue: 12000000,
          currentSeasonStats: {
            ppg: 15.8,
            rpg: 6.9,
            apg: 2.1,
            per: 16.8,
            ws: 5.2,
            vorp: 1.8
          },
          impactRating: 7.1,
          injuryRisk: "Medium",
          developmentPotential: 30,
          veteranLeadership: 68,
          teamChemistryImpact: 5,
          primaryRole: "Starter",
          positionFlexibility: ["SF", "PF"],
          offenseGrade: "B+",
          defenseGrade: "B"
        },
    ];
};

const mockTeamStatsAPI = async (teamId: string, season: string): Promise<TeamStatSummary | null> => {
    await new Promise(resolve => setTimeout(resolve, 400));
    const teamData: Record<string, TeamStatSummary> = {
        "1610612743": { 
          offRtg: 118.5, 
          defRtg: 112.3, 
          netRtg: 6.2, 
          pace: 98.5, 
          efgPct: 0.572, 
          tovPct: 0.135, 
          rebPct: 0.515, 
          pie: 0.530,
          clutchRecord: "15-7",
          homeRecord: "34-7",
          awayRecord: "23-18",
          vsPlayoffTeams: "28-15",
          strengthAreas: ["Interior Scoring", "Passing", "Rebounding", "Clutch Performance"],
          weaknessAreas: ["Perimeter Defense", "Bench Depth", "Fast Break Defense"],
          improvementSuggestions: [
            "Add perimeter defender",
            "Develop bench scoring",
            "Improve transition defense"
          ]
        },
        "1610612738": { 
          offRtg: 120.2, 
          defRtg: 110.1, 
          netRtg: 10.1, 
          pace: 99.2, 
          efgPct: 0.581, 
          tovPct: 0.128, 
          rebPct: 0.520, 
          pie: 0.555,
          clutchRecord: "18-4",
          homeRecord: "37-4",
          awayRecord: "27-14",
          vsPlayoffTeams: "32-10",
          strengthAreas: ["Three-Point Shooting", "Defense", "Depth", "Experience"],
          weaknessAreas: ["Interior Scoring", "Rebounding vs Bigger Teams"],
          improvementSuggestions: [
            "Add interior presence",
            "Develop young players",
            "Rest management for veterans"
          ]
        },
    };
    return teamData[teamId] || { 
      offRtg: 110, 
      defRtg: 110, 
      netRtg: 0, 
      pace: 100, 
      efgPct: 0.500, 
      tovPct: 0.150, 
      rebPct: 0.500, 
      pie: 0.500,
      clutchRecord: "10-10",
      homeRecord: "25-16",
      awayRecord: "22-19",
      vsPlayoffTeams: "20-25",
      strengthAreas: ["Balanced Scoring"],
      weaknessAreas: ["Consistency", "Depth"],
      improvementSuggestions: ["Improve team chemistry", "Add veteran leadership"]
    };
};

// Enhanced mock API functions for advanced features
const mockGetLineupAnalysisAPI = async (teamId: string): Promise<LineupAnalysis[]> => {
    await new Promise(resolve => setTimeout(resolve, 600));
    if (teamId === "1610612743") { // Denver Nuggets
        return [
            {
              players: ["Nikola Jokic", "Aaron Gordon", "Michael Porter Jr.", "Kentavious Caldwell-Pope", "Jamal Murray"],
              minutesTogether: 1247,
              plusMinus: 187,
              netRating: 14.8,
              offRating: 122.3,
              defRating: 107.5,
              usage: 78,
              effectiveness: "Elite",
              chemistryScore: 94,
              recommendations: [
                "This is your championship lineup - maximize their minutes together",
                "Consider load management during regular season",
                "Elite in clutch situations"
              ]
            },
            {
              players: ["Nikola Jokic", "Aaron Gordon", "Michael Porter Jr.", "Bruce Brown", "Jamal Murray"],
              minutesTogether: 623,
              plusMinus: 89,
              netRating: 11.2,
              offRating: 118.7,
              defRating: 107.5,
              usage: 45,
              effectiveness: "Good",
              chemistryScore: 87,
              recommendations: [
                "Strong backup option when KCP rests",
                "Better defensive rebounding with Brown",
                "Less three-point shooting than primary lineup"
              ]
            },
            {
              players: ["Reggie Jackson", "Kentavious Caldwell-Pope", "Vlatko Cancar", "Jeff Green", "DeAndre Jordan"],
              minutesTogether: 189,
              plusMinus: -12,
              netRating: -5.8,
              offRating: 108.3,
              defRating: 114.1,
              usage: 12,
              effectiveness: "Poor",
              chemistryScore: 61,
              recommendations: [
                "Avoid this lineup in crucial moments",
                "Consider developing younger players instead",
                "Lacks offensive creation and rim protection"
              ]
            }
        ];
    }
    return [
        {
          players: ["Player A", "Player B", "Player C", "Player D", "Player E"],
          minutesTogether: 800,
          plusMinus: 45,
          netRating: 6.2,
          offRating: 115.0,
          defRating: 108.8,
          usage: 60,
          effectiveness: "Good",
          chemistryScore: 78,
          recommendations: ["Primary lineup shows good chemistry", "Consider more minutes together"]
        }
    ];
};

const mockGetTradeScenarioAPI = async (teamId: string): Promise<TradeScenario[]> => {
    await new Promise(resolve => setTimeout(resolve, 700));
    if (teamId === "1610612743") { // Denver Nuggets
        return [
            {
              id: "TRADE_1",
              description: "Acquire Perimeter Defender",
              outgoingPlayers: [
                {
                  id: "P6",
                  fullName: "Bones Hyland",
                  jerseyNumber: "3",
                  position: "G",
                  height: "6-3",
                  weight: "173",
                  age: 23,
                  experience: "2nd",
                  college: "VCU",
                  salary: 2200000,
                  contractYears: 2,
                  tradeValue: 3500000,
                  currentSeasonStats: { ppg: 8.1, rpg: 2.1, apg: 2.4, per: 12.3, ws: 1.8, vorp: 0.4 },
                  impactRating: 5.8,
                  injuryRisk: "Low",
                  developmentPotential: 70,
                  veteranLeadership: 25,
                  teamChemistryImpact: 3,
                  primaryRole: "Bench",
                  positionFlexibility: ["PG", "SG"],
                  offenseGrade: "B",
                  defenseGrade: "C"
                }
              ],
              incomingPlayers: [
                {
                  name: "Alex Caruso",
                  position: "G",
                  salary: 9400000,
                  stats: { ppg: 9.8, rpg: 2.9, apg: 3.8, per: 13.7, ws: 5.1, vorp: 1.8 }
                }
              ],
              salaryCapImpact: -7200000,
              teamChemistryImpact: 4,
              winImpact: 3.2,
              feasibilityScore: 72,
              pros: [
                "Elite perimeter defender",
                "Championship experience",
                "Improves bench defense significantly",
                "High basketball IQ"
              ],
              cons: [
                "Expensive for limited offensive production",
                "Age concerns (30+)",
                "Less offensive upside than Hyland"
              ],
              aiRecommendation: "Recommend"
            },
            {
              id: "TRADE_2", 
              description: "Add Backup Center",
              outgoingPlayers: [
                {
                  id: "P7",
                  fullName: "Zeke Nnaji",
                  jerseyNumber: "22",
                  position: "F",
                  height: "6-9",
                  weight: "240",
                  age: 23,
                  experience: "3rd",
                  college: "Arizona",
                  salary: 8500000,
                  contractYears: 3,
                  tradeValue: 6000000,
                  currentSeasonStats: { ppg: 3.2, rpg: 2.8, apg: 0.5, per: 9.1, ws: 1.2, vorp: -0.3 },
                  impactRating: 4.1,
                  injuryRisk: "Low",
                  developmentPotential: 40,
                  veteranLeadership: 25,
                  teamChemistryImpact: 1,
                  primaryRole: "Bench",
                  positionFlexibility: ["PF", "C"],
                  offenseGrade: "C",
                  defenseGrade: "C+"
                }
              ],
              incomingPlayers: [
                {
                  name: "Robert Williams III",
                  position: "C",
                  salary: 12400000,
                  stats: { ppg: 8.0, rpg: 9.6, apg: 2.2, per: 19.8, ws: 4.8, vorp: 1.6 }
                }
              ],
              salaryCapImpact: -3900000,
              teamChemistryImpact: 2,
              winImpact: 4.1,
              feasibilityScore: 45,
              pros: [
                "Elite rim protection",
                "Excellent rebounder",
                "Perfect complement to Jokic",
                "Young with upside"
              ],
              cons: [
                "Injury history concerns",
                "Limited offensive game",
                "Higher salary burden",
                "Boston unlikely to trade"
              ],
              aiRecommendation: "Neutral"
            }
        ];
    }
    return [
        {
          id: "TRADE_DEFAULT",
          description: "Sample Trade Scenario",
          outgoingPlayers: [],
          incomingPlayers: [{
            name: "Trade Target",
            position: "F",
            salary: 15000000,
            stats: { ppg: 12.0, rpg: 6.0, apg: 3.0 }
          }],
          salaryCapImpact: 0,
          teamChemistryImpact: 0,
          winImpact: 1.5,
          feasibilityScore: 50,
          pros: ["Adds depth"],
          cons: ["Unknown fit"],
          aiRecommendation: "Neutral"
        }
    ];
};

const mockGetTeamInsightsAPI = async (teamId: string): Promise<TeamInsight[]> => {
    await new Promise(resolve => setTimeout(resolve, 500));
    if (teamId === "1610612743") { // Denver Nuggets
        return [
            {
              id: "INSIGHT_1",
              type: "roster_move",
              priority: "high",
              title: "Perimeter Defense Weakness",
              description: "Team ranks 24th in opponent 3P% and struggles against elite wing scorers. Consider targeting a defensive specialist at the deadline.",
              actionable: true,
              confidence: 87,
              timeframe: "Short-term",
              impactLevel: "Significant",
              relatedPlayers: ["Kentavious Caldwell-Pope", "Bruce Brown"]
            },
            {
              id: "INSIGHT_2",
              type: "development", 
              priority: "medium",
              title: "Maximize Christian Braun's Growth",
              description: "Braun shows excellent defensive instincts and improving three-point shot. Increase his rotation minutes to accelerate development.",
              actionable: true,
              confidence: 78,
              timeframe: "Long-term",
              impactLevel: "Notable",
              relatedPlayers: ["Christian Braun"]
            },
            {
              id: "INSIGHT_3",
              type: "chemistry",
              priority: "low",
              title: "Bench Unit Chemistry",
              description: "Second unit has improved significantly with Russell Westbrook's leadership. Chemistry score up 12 points from early season.",
              actionable: false,
              confidence: 92,
              timeframe: "Immediate",
              impactLevel: "Notable",
              relatedPlayers: ["Russell Westbrook", "Reggie Jackson"]
            },
            {
              id: "INSIGHT_4",
              type: "injury_management",
              priority: "critical",
              title: "Monitor Michael Porter Jr.'s Back",
              description: "MPJ showing signs of back stiffness. Consider load management during back-to-backs to prevent re-injury.",
              actionable: true,
              confidence: 91,
              timeframe: "Immediate",
              impactLevel: "Game-Changing",
              relatedPlayers: ["Michael Porter Jr."]
            },
            {
              id: "INSIGHT_5",
              type: "strategy",
              priority: "medium",
              title: "Exploit Pace Advantage", 
              description: "Team performs significantly better when pace exceeds 100. Consider pushing tempo more consistently.",
              actionable: true,
              confidence: 83,
              timeframe: "Immediate",
              impactLevel: "Significant",
              relatedPlayers: []
            }
        ];
    }
    return [
        {
          id: "DEFAULT_INSIGHT",
          type: "roster_move",
          priority: "medium",
          title: "General Team Assessment",
          description: "Team shows solid foundation with room for improvement in key areas.",
          actionable: false,
          confidence: 65,
          timeframe: "Long-term",
          impactLevel: "Notable",
          relatedPlayers: []
        }
    ];
};

export default function TeamCommandPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const teamIdParam = searchParams.get('team');

  // State management
  const [allTeams, setAllTeams] = useState<TeamDetails[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<TeamDetails | null>(null);
  const [teamRoster, setTeamRoster] = useState<PlayerRosterEntry[]>([]);
  const [teamStats, setTeamStats] = useState<TeamStatSummary | null>(null);
  const [lineupAnalysis, setLineupAnalysis] = useState<LineupAnalysis[]>([]);
  const [tradeScenarios, setTradeScenarios] = useState<TradeScenario[]>([]);
  const [teamInsights, setTeamInsights] = useState<TeamInsight[]>([]);
  
  // Loading states
  const [isLoadingTeams, setIsLoadingTeams] = useState(true);
  const [isLoadingTeamData, setIsLoadingTeamData] = useState(false);
  const [isLoadingAdvanced, setIsLoadingAdvanced] = useState(false);
  
  // Filter and sort states
  const [playerFilter, setPlayerFilter] = useState<string>("all"); // all, starters, bench, development
  const [rosterSortBy, setRosterSortBy] = useState<string>("salary"); // salary, impact, age, position
  const [insightFilter, setInsightFilter] = useState<string>("all"); // all, critical, high, medium, low
  const [selectedSeason, setSelectedSeason] = useState<string>("2023-24");

  // Fetch initial teams
  useEffect(() => {
    const loadTeams = async () => {
      setIsLoadingTeams(true);
      try {
        const teams = await mockAllTeamsAPI();
        setAllTeams(teams);
        
        // Auto-select team from URL param or default to first team
        if (teamIdParam) {
          const team = teams.find(t => t.id === teamIdParam);
          if (team) {
            setSelectedTeam(team);
          }
        } else if (teams.length > 0) {
          setSelectedTeam(teams[0]);
        }
      } catch (error) {
        console.error("Error loading teams:", error);
      }
      setIsLoadingTeams(false);
    };

    loadTeams();
  }, [teamIdParam]);

  // Load team data when team is selected
  useEffect(() => {
    if (!selectedTeam) return;

    const loadTeamData = async () => {
      setIsLoadingTeamData(true);
      try {
        const [roster, stats] = await Promise.all([
          mockTeamRosterAPI(selectedTeam.id),
          mockTeamStatsAPI(selectedTeam.id, selectedSeason)
        ]);
        
        setTeamRoster(roster);
        setTeamStats(stats);
      } catch (error) {
        console.error("Error loading team data:", error);
      }
      setIsLoadingTeamData(false);
    };

    loadTeamData();
  }, [selectedTeam, selectedSeason]);

  // Load advanced analytics when team is selected
  useEffect(() => {
    if (!selectedTeam) return;

    const loadAdvancedData = async () => {
      setIsLoadingAdvanced(true);
      try {
        const [lineups, trades, insights] = await Promise.all([
          mockGetLineupAnalysisAPI(selectedTeam.id),
          mockGetTradeScenarioAPI(selectedTeam.id),
          mockGetTeamInsightsAPI(selectedTeam.id)
        ]);
        
        setLineupAnalysis(lineups);
        setTradeScenarios(trades);
        setTeamInsights(insights);
      } catch (error) {
        console.error("Error loading advanced data:", error);
      }
      setIsLoadingAdvanced(false);
    };

    loadAdvancedData();
  }, [selectedTeam]);

  const handleTeamChange = (teamId: string) => {
    const team = allTeams.find(t => t.id === teamId);
    setSelectedTeam(team || null);
    
    // Update URL
    const params = new URLSearchParams(searchParams);
    if (team) {
      params.set('team', teamId);
    } else {
      params.delete('team');
    }
    router.push(`/team-command?${params.toString()}`);
  };

  // Helper functions
  const formatSalary = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const getInjuryRiskColor = (risk: string) => {
    switch (risk) {
      case 'Low': return 'text-green-600';
      case 'Medium': return 'text-yellow-600';
      case 'High': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const getGradeColor = (grade: string) => {
    if (grade.startsWith('A')) return 'text-green-600';
    if (grade.startsWith('B')) return 'text-blue-600';
    if (grade.startsWith('C')) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getInsightPriorityIcon = (priority: TeamInsight["priority"]) => {
    switch (priority) {
      case 'critical': return <AlertTriangle className="w-4 h-4 text-red-500" />;
      case 'high': return <Brain className="w-4 h-4 text-orange-500" />;
      case 'medium': return <Eye className="w-4 h-4 text-blue-500" />;
      case 'low': return <Activity className="w-4 h-4 text-gray-500" />;
      default: return <Activity className="w-4 h-4" />;
    }
  };

  const getEffectivenessColor = (effectiveness: string) => {
    switch (effectiveness) {
      case 'Elite': return 'text-purple-600';
      case 'Good': return 'text-green-600';
      case 'Average': return 'text-yellow-600';
      case 'Poor': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const getRecommendationColor = (rec: string) => {
    switch (rec) {
      case 'Strongly Recommend': return 'text-green-700 bg-green-50';
      case 'Recommend': return 'text-green-600 bg-green-50';
      case 'Neutral': return 'text-gray-600 bg-gray-50';
      case 'Not Recommended': return 'text-red-600 bg-red-50';
      case 'Strongly Against': return 'text-red-700 bg-red-50';
      default: return 'text-gray-600';
    }
  };

  // Filter and sort logic
  const filteredRoster = teamRoster.filter(player => {
    switch (playerFilter) {
      case 'starters': return ['Superstar', 'All-Star', 'Starter'].includes(player.primaryRole);
      case 'bench': return ['Sixth Man', 'Role Player', 'Bench'].includes(player.primaryRole);
      case 'development': return player.developmentPotential > 50;
      default: return true;
    }
  });

  const sortedRoster = [...filteredRoster].sort((a, b) => {
    switch (rosterSortBy) {
      case 'salary': return b.salary - a.salary;
      case 'impact': return b.impactRating - a.impactRating;
      case 'age': return a.age - b.age;
      case 'position': return a.position.localeCompare(b.position);
      default: return 0;
    }
  });

  const filteredInsights = teamInsights.filter(insight => 
    insightFilter === "all" || insight.priority === insightFilter
  );

  return (
    <div className="flex-1 space-y-6 p-4 md:p-6 lg:p-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Team Command</h1>
          <p className="text-muted-foreground">Advanced team management and roster analytics powered by Dime AI</p>
        </div>
        
        <div className="flex items-center space-x-2">
          <Select value={selectedSeason} onValueChange={setSelectedSeason}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="2023-24">2023-24</SelectItem>
              <SelectItem value="2022-23">2022-23</SelectItem>
              <SelectItem value="2021-22">2021-22</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Team Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building className="w-5 h-5" />
            Select Team
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoadingTeams ? (
            <Skeleton className="h-12 w-64" />
          ) : (
            <Select value={selectedTeam?.id || ""} onValueChange={handleTeamChange}>
              <SelectTrigger className="w-full md:w-64">
                <SelectValue placeholder="Choose a team" />
              </SelectTrigger>
              <SelectContent>
                {allTeams.map((team) => (
                  <SelectItem key={team.id} value={team.id}>
                    <div className="flex items-center gap-2">
                      <span>{team.fullName}</span>
                      <Badge variant="outline" className="text-xs">
                        {team.currentRecord}
                      </Badge>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </CardContent>
      </Card>

      {/* Team Overview Cards */}
      {selectedTeam && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Team Chemistry */}
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-100 rounded-lg">
                    <Users className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Team Chemistry</p>
                    <div className="flex items-center gap-2">
                      <Progress value={selectedTeam.teamChemistry} className="w-16 h-2" />
                      <span className="font-semibold">{selectedTeam.teamChemistry}/100</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Salary Cap */}
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-green-100 rounded-lg">
                    <DollarSign className="w-5 h-5 text-green-600" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Salary Cap Usage</p>
                    <div className="flex items-center gap-2">
                      <Progress 
                        value={(selectedTeam.payroll / selectedTeam.salaryCap) * 100} 
                        className="w-16 h-2" 
                      />
                      <span className="font-semibold">
                        {((selectedTeam.payroll / selectedTeam.salaryCap) * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Average Age */}
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-100 rounded-lg">
                    <Clock className="w-5 h-5 text-purple-600" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Average Age</p>
                    <p className="font-semibold text-lg">{selectedTeam.averageAge} yrs</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Injury Risk */}
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-red-100 rounded-lg">
                    <ShieldCheck className="w-5 h-5 text-red-600" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Injury Risk</p>
                    <p className={`font-semibold ${getInjuryRiskColor(selectedTeam.injuryRisk)}`}>
                      {selectedTeam.injuryRisk}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Main Analytics Tabs */}
          <Tabs defaultValue="roster_analytics" className="w-full">
            <TabsList className="grid w-full grid-cols-6">
              <TabsTrigger value="roster_analytics" className="flex items-center gap-2">
                <Users className="w-4 h-4" />
                Roster
              </TabsTrigger>
              <TabsTrigger value="salary_cap" className="flex items-center gap-2">
                <DollarSign className="w-4 h-4" />
                Salary Cap
              </TabsTrigger>
              <TabsTrigger value="lineups" className="flex items-center gap-2">
                <Target className="w-4 h-4" />
                Lineups
              </TabsTrigger>
              <TabsTrigger value="trade_scenarios" className="flex items-center gap-2">
                <ArrowUpDown className="w-4 h-4" />
                Trades
              </TabsTrigger>
              <TabsTrigger value="ai_insights" className="flex items-center gap-2">
                <Brain className="w-4 h-4" />
                AI Insights
              </TabsTrigger>
              <TabsTrigger value="team_analytics" className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4" />
                Analytics
              </TabsTrigger>
            </TabsList>

            <TabsContent value="roster_analytics" className="mt-6">
              <Card>
                <CardHeader><CardTitle>Team Roster ({selectedSeason})</CardTitle></CardHeader>
                <CardContent>
                {isLoadingTeamData || !selectedTeam ? (
                    <Skeleton className="h-96 w-full" />
                ) : teamRoster.length > 0 ? (
                    <div className="overflow-x-auto">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Player</TableHead>
                                <TableHead>#</TableHead>
                                <TableHead>Pos</TableHead>
                                <TableHead>Height</TableHead>
                                <TableHead>Weight</TableHead>
                                <TableHead>Age</TableHead>
                                <TableHead>Exp</TableHead>
                                <TableHead>College</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {sortedRoster.map((player) => (
                                <TableRow key={player.id}>
                                    <TableCell className="font-medium">{player.fullName}</TableCell>
                                    <TableCell>{player.jerseyNumber || "N/A"}</TableCell>
                                    <TableCell>{player.position}</TableCell>
                                    <TableCell>{player.height}</TableCell>
                                    <TableCell>{player.weight}</TableCell>
                                    <TableCell>{player.age}</TableCell>
                                    <TableCell>{player.experience}</TableCell>
                                    <TableCell>{player.college || "N/A"}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                    </div>
                ) : (
                    <p className="text-muted-foreground text-center py-10">No roster data available for this team.</p>
                )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="salary_cap" className="mt-6">
              <Card>
                <CardHeader><CardTitle>Detailed Team Statistics</CardTitle></CardHeader>
                <CardContent><p className="text-muted-foreground">Full team stats tables (traditional, advanced, shooting, etc.) will go here.</p></CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="lineups" className="mt-6">
              <Card>
                <CardHeader><CardTitle>Team Lineups</CardTitle></CardHeader>
                <CardContent><p className="text-muted-foreground">Team lineup analysis and performance data will go here.</p></CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="trade_scenarios" className="mt-6">
              <Card>
                <CardHeader><CardTitle>Trade Scenarios</CardTitle></CardHeader>
                <CardContent><p className="text-muted-foreground">Trade scenarios and analysis will go here.</p></CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="ai_insights" className="mt-6">
              <Card>
                <CardHeader><CardTitle>AI Insights</CardTitle></CardHeader>
                <CardContent><p className="text-muted-foreground">AI-generated insights and recommendations will go here.</p></CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="team_analytics" className="mt-6">
              <Card>
                <CardHeader><CardTitle>Team Analytics</CardTitle></CardHeader>
                <CardContent><p className="text-muted-foreground">Advanced team analytics and statistics will go here.</p></CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
} 