"use client";

import { useState, useMemo, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Checkbox } from "@/components/ui/checkbox";
import Link from "next/link";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Users,
  Target,
  Calendar,
  BarChart3,
  Grid3X3,
  List,
  TableIcon,
  Eye,
  GitCompare,
  Zap,
  AlertTriangle,
  Trophy,
  DollarSign,
  Brain,
  AreaChart,
  Bot,
  Check,
  Plus,
  ExternalLink,
  RefreshCw
} from "lucide-react";

// Import Advanced Analytics Components
import TeamChemistryNetwork from "@/components/charts/TeamChemistryNetwork";
import ShotTrajectoryVisualizer from "@/components/charts/ShotTrajectoryVisualizer";
import GameIntelligenceDashboard from "@/components/charts/GameIntelligenceDashboard";
import AIOrchestrationHub from "@/components/charts/AIOrchestrationHub";
import MarketIntelligenceDashboard from "@/components/charts/MarketIntelligenceDashboard";
import TeamStrategyOptimizer from "@/components/charts/TeamStrategyOptimizer";
import { AdvancedAnalyticsDashboard } from "@/components/analytics/AdvancedAnalyticsDashboard";

// Import API functions
import {
  getEnhancedTeams,
  getEnhancedTeamsWithStats,
  getLeagueStandings,
  getLeagueTeamStats,
  getAllTeams,
  TEAM_COLORS,
  type EnhancedTeam
} from "@/lib/api/teams";

interface TeamsClientPageProps {
  currentSeason: string;
}

// Define available seasons
const availableSeasons = ["2024-25", "2023-24", "2022-23", "2021-22", "2020-21", "2019-20", "2018-19", "2017-18", "2016-17", "2015-16"];

// AI Widget types for dynamic content
interface AIWidget {
  id: string;
  type: 'trade-alert' | 'breakout-prediction' | 'weakness-analysis' | 'championship-probability' | 'contract-efficiency';
  confidence: number;
  data: any;
  generatedAt: Date;
  relevanceScore: number;
  title: string;
  description: string;
}

// Mock AI Widgets data
const mockAIWidgets: AIWidget[] = [
  {
    id: '1',
    type: 'trade-alert',
    confidence: 0.85,
    data: {
      team: 'Lakers',
      player: 'D\'Angelo Russell',
      targetTeam: 'Hawks',
      reasoning: 'Hawks need veteran playmaking, Lakers need defensive depth'
    },
    generatedAt: new Date(),
    relevanceScore: 0.9,
    title: 'High-Value Trade Opportunity',
    description: 'Lakers-Hawks trade scenario offers mutual benefits'
  },
  {
    id: '2',
    type: 'breakout-prediction',
    confidence: 0.78,
    data: {
      player: 'Brandon Miller',
      team: 'Hornets',
      prediction: '18+ PPG by season end',
      factors: ['increased usage', 'improved shooting', 'confidence growth']
    },
    generatedAt: new Date(),
    relevanceScore: 0.8,
    title: 'Breakout Player Alert',
    description: 'Brandon Miller showing All-Star potential'
  },
  {
    id: '3',
    type: 'weakness-analysis',
    confidence: 0.92,
    data: {
      team: 'Warriors',
      weakness: 'Rebounding',
      impact: 'High',
      solution: 'Acquire rim-running center'
    },
    generatedAt: new Date(),
    relevanceScore: 0.85,
    title: 'Critical Team Weakness',
    description: 'Warriors struggling with defensive rebounding'
  }
];

// REMOVED: Mock data - using real NBA API data only

type ViewMode = 'grid' | 'list' | 'table' | 'analytics';
type SortOption = 'name' | 'record' | 'offense' | 'defense' | 'pace' | 'playoff-odds';
type FilterStatus = 'all' | 'contender' | 'playoff-push' | 'rebuilding';

export default function TeamsClientPage({ currentSeason }: TeamsClientPageProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedConference, setSelectedConference] = useState<string>("all");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [sortBy, setSortBy] = useState<SortOption>("record");
  const [filterStatus, setFilterStatus] = useState<FilterStatus>("all");
  const [selectedTeams, setSelectedTeams] = useState<string[]>([]);
  const [showOnlyInjuries, setShowOnlyInjuries] = useState(false);
  const [showAIWidgets, setShowAIWidgets] = useState(true);
  const [aiWidgets, setAIWidgets] = useState<AIWidget[]>(mockAIWidgets);
  const [activeAdvancedTab, setActiveAdvancedTab] = useState<string>("teamChemistry");

  // Real data state
  const [teams, setTeams] = useState<EnhancedTeam[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [leagueStandings, setLeagueStandings] = useState<any>(null);
  const [leagueStats, setLeagueStats] = useState<any>(null);

  // Fetch real team data with comprehensive stats
  useEffect(() => {
    const fetchTeams = async () => {
      try {
        setLoading(true);
        setError(null);

        // Fetch comprehensive team data with real stats
        const [enhancedTeams, standings, teamStats] = await Promise.all([
          getEnhancedTeamsWithStats(currentSeason),
          getLeagueStandings(currentSeason),
          getLeagueTeamStats(currentSeason)
        ]);

        setTeams(enhancedTeams);
        setLeagueStandings(standings);
        setLeagueStats(teamStats);
      } catch (err) {
        console.error('Error fetching teams:', err);
        setError('Failed to load team data. Please try again.');

        // Fallback to basic enhanced teams if comprehensive fetch fails
        try {
          const basicTeams = await getEnhancedTeams(currentSeason);
          setTeams(basicTeams);
        } catch (fallbackErr) {
          console.error('Fallback fetch also failed:', fallbackErr);
          setTeams([]);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchTeams();
  }, [currentSeason]);

  // Filter and sort teams
  const filteredAndSortedTeams = useMemo(() => {
    let filtered = teams.filter(team => {
      const matchesSearch = team.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          team.abbreviation.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesConference = selectedConference === "all" || team.conference.toLowerCase() === selectedConference.toLowerCase();
      const matchesStatus = filterStatus === "all" || team.status === filterStatus;
      const matchesInjury = !showOnlyInjuries || team.injuries.length > 0;

      return matchesSearch && matchesConference && matchesStatus && matchesInjury;
    });

    // Sort teams
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'record':
          const aWinPct = a.record.wins / (a.record.wins + a.record.losses);
          const bWinPct = b.record.wins / (b.record.wins + b.record.losses);
          return bWinPct - aWinPct;
        case 'offense':
          return b.offensiveRating - a.offensiveRating;
        case 'defense':
          return a.defensiveRating - b.defensiveRating; // Lower is better
        case 'pace':
          return b.pace - a.pace;
        case 'playoff-odds':
          return b.playoffOdds - a.playoffOdds;
        default:
          return a.name.localeCompare(b.name);
      }
    });

    return filtered;
  }, [teams, searchTerm, selectedConference, filterStatus, showOnlyInjuries, sortBy]);

  const handleSeasonChange = (newSeason: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("season", newSeason);
    router.push(`/teams?${params.toString()}`);
  };

  const toggleTeamSelection = (teamId: string) => {
    setSelectedTeams(prev =>
      prev.includes(teamId)
        ? prev.filter(id => id !== teamId)
        : [...prev, teamId]
    );
  };

  const getStatusBadgeColor = (status: string) => {
    switch (status) {
      case 'contender': return 'bg-green-500';
      case 'playoff-push': return 'bg-yellow-500';
      case 'rebuilding': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  const getAIWidgetIcon = (type: AIWidget['type']) => {
    switch (type) {
      case 'trade-alert': return <GitCompare className="w-4 h-4" />;
      case 'breakout-prediction': return <TrendingUp className="w-4 h-4" />;
      case 'weakness-analysis': return <AlertTriangle className="w-4 h-4" />;
      case 'championship-probability': return <Trophy className="w-4 h-4" />;
      case 'contract-efficiency': return <DollarSign className="w-4 h-4" />;
    }
  };

  const getAIWidgetColor = (type: AIWidget['type']) => {
    switch (type) {
      case 'trade-alert': return 'bg-blue-500';
      case 'breakout-prediction': return 'bg-green-500';
      case 'weakness-analysis': return 'bg-red-500';
      case 'championship-probability': return 'bg-yellow-500';
      case 'contract-efficiency': return 'bg-purple-500';
    }
  };

  const renderAIWidget = (widget: AIWidget) => (
    <Card key={widget.id} className="p-4 border-l-4 border-l-blue-500">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div className={`p-2 rounded-full ${getAIWidgetColor(widget.type)} text-white`}>
            {getAIWidgetIcon(widget.type)}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h4 className="font-semibold text-sm">{widget.title}</h4>
              <Badge variant="secondary" className="text-xs">
                {Math.round(widget.confidence * 100)}% confidence
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground mb-2">{widget.description}</p>
            <div className="text-xs text-muted-foreground">
              Generated {new Date(widget.generatedAt).toLocaleTimeString()}
            </div>
          </div>
        </div>
        <Button size="sm" variant="ghost">
          <Eye className="w-3 h-3" />
        </Button>
      </div>
    </Card>
  );

  const renderTeamCard = (team: EnhancedTeam) => (
    <div key={team.id} className="relative group">
      {viewMode === 'grid' && (
        <div className="absolute top-2 right-2 z-10">
          <Checkbox
            checked={selectedTeams.includes(team.id)}
            onCheckedChange={() => toggleTeamSelection(team.id)}
            className="bg-white shadow-md"
          />
        </div>
      )}

      <Link href={`/teams/${team.id}?season=${currentSeason}`} className="block transition-all duration-300 hover:scale-[1.02]">
        <Card className="overflow-hidden h-full hover:shadow-xl transition-all duration-300 border-2 hover:border-primary/20">
          <div
            className="h-32 flex items-center justify-center p-4 relative"
            style={{
              backgroundColor: team.primaryColor,
              backgroundImage: `linear-gradient(45deg, ${team.primaryColor}, ${team.secondaryColor})`
            }}
          >
            <img
              src={team.logo}
              alt={`${team.name} logo`}
              className="h-full object-contain transition-transform duration-300 group-hover:scale-110"
              style={{ filter: "drop-shadow(0px 4px 6px rgba(0, 0, 0, 0.3))" }}
            />

            {/* Status badge */}
            <Badge className={`absolute top-2 left-2 ${getStatusBadgeColor(team.status)} text-white`}>
              {team.status.replace('-', ' ')}
            </Badge>

            {/* Real Data indicator */}
            <Badge className="absolute top-2 right-12 bg-green-500 text-white text-xs">
              <BarChart3 className="w-3 h-3 mr-1" />
              Live Data
            </Badge>

            {/* Win percentage indicator */}
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-black/20">
              <div
                className="h-full bg-white/80 transition-all duration-500"
                style={{
                  width: `${(team.record.wins / (team.record.wins + team.record.losses)) * 100}%`
                }}
              />
            </div>
          </div>

          <CardContent className="p-4">
            <div className="space-y-3">
              {/* Team name and record */}
              <div className="text-center">
                <h3 className="font-bold text-lg group-hover:text-primary transition-colors">{team.name}</h3>
                <div className="flex items-center justify-center gap-2">
                  <span className="text-2xl font-bold">{team.record.wins}-{team.record.losses}</span>
                  <Badge variant={team.streak.type === 'W' ? 'default' : 'destructive'}>
                    {team.streak.type}{team.streak.count}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">{team.conference} • {team.division}</p>
              </div>

              {/* Performance metrics with color coding */}
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">OFF</span>
                  <span className={`font-medium ${team.offensiveRating > 115 ? 'text-green-600' : team.offensiveRating > 110 ? 'text-yellow-600' : 'text-red-600'}`}>
                    {team.offensiveRating}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">DEF</span>
                  <span className={`font-medium ${team.defensiveRating < 110 ? 'text-green-600' : team.defensiveRating < 115 ? 'text-yellow-600' : 'text-red-600'}`}>
                    {team.defensiveRating}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Pace</span>
                  <span className={`font-medium ${team.pace > 102 ? 'text-blue-600' : team.pace > 98 ? 'text-gray-600' : 'text-purple-600'}`}>
                    {team.pace}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Playoffs</span>
                  <span className={`font-medium ${team.playoffOdds > 70 ? 'text-green-600' : team.playoffOdds > 40 ? 'text-yellow-600' : 'text-red-600'}`}>
                    {team.playoffOdds}%
                  </span>
                </div>
              </div>

              {/* Last game and next game */}
              <div className="space-y-1 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Last:</span>
                  <span className={team.lastGame.result === 'W' ? 'text-green-600' : 'text-red-600'}>
                    {team.lastGame.result} vs {team.lastGame.opponent}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Next:</span>
                  <span>{team.nextGame.home ? 'vs' : '@'} {team.nextGame.opponent}</span>
                </div>
              </div>

              {/* Status indicators */}
              <div className="flex items-center justify-between">
                {team.injuries.length > 0 && (
                  <div className="flex items-center gap-1 text-xs text-red-600">
                    <AlertTriangle className="w-3 h-3" />
                    <span>{team.injuries.length} injured</span>
                  </div>
                )}

                {team.recentTrades.length > 0 && (
                  <div className="flex items-center gap-1 text-xs text-blue-600">
                    <GitCompare className="w-3 h-3" />
                    <span>Recent trade</span>
                  </div>
                )}

                {/* Net rating indicator */}
                <div className="text-xs">
                  <span className="text-muted-foreground">Net: </span>
                  <span className={`font-medium ${(team.offensiveRating - team.defensiveRating) > 5 ? 'text-green-600' : (team.offensiveRating - team.defensiveRating) > 0 ? 'text-yellow-600' : 'text-red-600'}`}>
                    {(team.offensiveRating - team.defensiveRating).toFixed(1)}
                  </span>
                </div>
              </div>

              {/* Quick action buttons - shown on hover */}
              <div className="flex gap-1 pt-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                <Button
                  size="sm"
                  variant="outline"
                  className="flex-1 text-xs h-7"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    toggleTeamSelection(team.id);
                  }}
                >
                  {selectedTeams.includes(team.id) ? (
                    <>
                      <Check className="w-3 h-3 mr-1" />
                      Selected
                    </>
                  ) : (
                    <>
                      <Plus className="w-3 h-3 mr-1" />
                      Compare
                    </>
                  )}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="text-xs h-7 px-2"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    window.open(`/teams/${team.id}?season=${currentSeason}`, '_blank');
                  }}
                >
                  <ExternalLink className="w-3 h-3" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </Link>
    </div>
  );

  // Show loading state
  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8 space-y-6">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">NBA Teams</h1>
            <p className="text-muted-foreground">Loading team data...</p>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {Array.from({ length: 8 }).map((_, i) => (
            <Card key={i} className="animate-pulse">
              <div className="h-32 bg-gray-200 rounded-t-lg"></div>
              <CardContent className="p-4">
                <div className="space-y-3">
                  <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                  <div className="h-4 bg-gray-200 rounded w-1/2"></div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="h-3 bg-gray-200 rounded"></div>
                    <div className="h-3 bg-gray-200 rounded"></div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className="container mx-auto px-4 py-8 space-y-6">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">NBA Teams</h1>
            <p className="text-muted-foreground text-red-600">{error}</p>
          </div>
        </div>
        <Card className="p-6 text-center">
          <div className="space-y-4">
            <AlertTriangle className="w-12 h-12 text-red-500 mx-auto" />
            <h3 className="text-lg font-semibold">Unable to load team data</h3>
            <p className="text-muted-foreground">Please check your connection and try again.</p>
            <Button onClick={() => window.location.reload()}>
              Retry
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">NBA Teams</h1>
          <div className="flex items-center gap-2">
            <p className="text-muted-foreground">Comprehensive team analysis and intelligence ({teams.length} teams)</p>
            <Badge variant="secondary" className="text-xs">
              <BarChart3 className="w-3 h-3 mr-1" />
              Real NBA Data
            </Badge>
            {leagueStandings && (
              <Badge variant="outline" className="text-xs">
                <RefreshCw className="w-3 h-3 mr-1" />
                Live Standings
              </Badge>
            )}
          </div>
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center gap-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.location.reload()}
            className="flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh Data
          </Button>
          <Label className="text-sm font-medium">View:</Label>
          <RadioGroup
            value={viewMode}
            onValueChange={(value: string) => setViewMode(value as ViewMode)}
            className="flex items-center gap-2"
          >
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="grid" id="grid" />
              <Label htmlFor="grid" className="flex items-center gap-1 text-sm">
                <Grid3X3 className="h-4 w-4" />
                Grid
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="list" id="list" />
              <Label htmlFor="list" className="flex items-center gap-1 text-sm">
                <List className="h-4 w-4" />
                List
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="table" id="table" />
              <Label htmlFor="table" className="flex items-center gap-1 text-sm">
                <TableIcon className="h-4 w-4" />
                Table
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="analytics" id="analytics" />
              <Label htmlFor="analytics" className="flex items-center gap-1 text-sm">
                <BarChart3 className="h-4 w-4" />
                Analytics
              </Label>
            </div>
          </RadioGroup>
        </div>
      </div>

      {/* Filters and Controls */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Search */}
        <Input
          placeholder="Search teams..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />

        {/* Conference Filter */}
        <Select value={selectedConference} onValueChange={setSelectedConference}>
          <SelectTrigger>
            <SelectValue placeholder="Conference" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Conferences</SelectItem>
            <SelectItem value="east">Eastern</SelectItem>
            <SelectItem value="west">Western</SelectItem>
          </SelectContent>
        </Select>

        {/* Status Filter */}
        <Select value={filterStatus} onValueChange={(value) => setFilterStatus(value as FilterStatus)}>
          <SelectTrigger>
            <SelectValue placeholder="Team Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Teams</SelectItem>
            <SelectItem value="contender">Contenders</SelectItem>
            <SelectItem value="playoff-push">Playoff Push</SelectItem>
            <SelectItem value="rebuilding">Rebuilding</SelectItem>
          </SelectContent>
        </Select>

        {/* Sort By */}
        <Select value={sortBy} onValueChange={(value) => setSortBy(value as SortOption)}>
          <SelectTrigger>
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="name">Team Name</SelectItem>
            <SelectItem value="record">Win Percentage</SelectItem>
            <SelectItem value="offense">Offensive Rating</SelectItem>
            <SelectItem value="defense">Defensive Rating</SelectItem>
            <SelectItem value="pace">Pace</SelectItem>
            <SelectItem value="playoff-odds">Playoff Odds</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Additional Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center space-x-2">
          <Checkbox
            id="injuries"
            checked={showOnlyInjuries}
            onCheckedChange={(checked) => setShowOnlyInjuries(checked === true)}
          />
          <Label htmlFor="injuries" className="text-sm">Teams with injuries only</Label>
        </div>

        {selectedTeams.length > 0 && (
          <div className="flex items-center gap-2">
            <Badge variant="secondary">
              {selectedTeams.length} team{selectedTeams.length > 1 ? 's' : ''} selected
            </Badge>
            <Button size="sm" variant="outline" onClick={() => setSelectedTeams([])}>
              Clear
            </Button>
            {selectedTeams.length > 1 && (
              <Button
                size="sm"
                onClick={() => {
                  const compareUrl = `/teams/compare?teams=${selectedTeams.join(',')}&season=${currentSeason}`;
                  window.open(compareUrl, '_blank');
                }}
              >
                <GitCompare className="w-4 h-4 mr-2" />
                Compare Teams
              </Button>
            )}
          </div>
        )}



        {/* Season Selector */}
        <div className="flex items-center gap-2 ml-auto">
          <Label htmlFor="season-select" className="text-sm font-medium">Season:</Label>
          <Select value={currentSeason} onValueChange={handleSeasonChange}>
            <SelectTrigger id="season-select" className="w-[140px]">
              <SelectValue placeholder="Select Season" />
            </SelectTrigger>
            <SelectContent>
              {availableSeasons.map((season) => (
                <SelectItem key={season} value={season}>{season}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* AI Intelligence Panel */}
      {showAIWidgets && (
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Zap className="w-5 h-5 text-blue-500" />
              <h3 className="text-lg font-semibold">AI Intelligence Hub</h3>
              <Badge variant="secondary">Live</Badge>
            </div>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShowAIWidgets(false)}
            >
              Hide AI Insights
            </Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {aiWidgets.map(renderAIWidget)}
          </div>
        </Card>
      )}

      {!showAIWidgets && (
        <div className="text-center">
          <Button
            onClick={() => setShowAIWidgets(true)}
            className="bg-blue-500 hover:bg-blue-600"
          >
            <Zap className="w-4 h-4 mr-2" />
            Show AI Intelligence Hub
          </Button>
        </div>
      )}

      {/* Phase 4: Real-time Intelligence Hub */}
      <Tabs defaultValue="teams" className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="teams">Teams Overview</TabsTrigger>
          <TabsTrigger value="intelligence">Market Intelligence</TabsTrigger>
          <TabsTrigger value="alerts">Live Alerts</TabsTrigger>
          <TabsTrigger value="network">Network Analysis</TabsTrigger>
          <TabsTrigger value="advancedAnalytics">
            <Brain className="w-4 h-4 mr-1" />
            Advanced Analytics
          </TabsTrigger>
        </TabsList>

        <TabsContent value="intelligence" className="space-y-6">
          {/* Real-time Market Intelligence */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <h3 className="font-bold flex items-center gap-2">
                  <Calendar className="w-5 h-5" />
                  Live NBA Feed
                  <Badge variant="secondary" className="text-xs">
                    Updated 2m ago
                  </Badge>
                </h3>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="border-l-4 border-l-blue-500 pl-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="font-medium text-sm">Lakers Trade Rumors Heat Up</h4>
                        <p className="text-xs text-muted-foreground">
                          Multiple sources indicate Lakers are actively shopping D'Angelo Russell
                        </p>
                        <div className="text-xs text-muted-foreground mt-1">ESPN • 15 minutes ago</div>
                      </div>
                      <Badge variant="outline" className="text-xs">High Impact</Badge>
                    </div>
                  </div>

                  <div className="border-l-4 border-l-green-500 pl-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="font-medium text-sm">Brandon Miller's Breakout Performance</h4>
                        <p className="text-xs text-muted-foreground">
                          Rookie averaging 22 PPG over last 10 games, drawing All-Star consideration
                        </p>
                        <div className="text-xs text-muted-foreground mt-1">The Athletic • 1 hour ago</div>
                      </div>
                      <Badge variant="outline" className="text-xs">Rising Star</Badge>
                    </div>
                  </div>

                  <div className="border-l-4 border-l-red-500 pl-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="font-medium text-sm">Warriors' Defensive Struggles Continue</h4>
                        <p className="text-xs text-muted-foreground">
                          Allowing 120+ points in 7 of last 10 games, worst stretch in 3 years
                        </p>
                        <div className="text-xs text-muted-foreground mt-1">NBA.com • 3 hours ago</div>
                      </div>
                      <Badge variant="destructive" className="text-xs">Concern</Badge>
                    </div>
                  </div>

                  <div className="border-l-4 border-l-yellow-500 pl-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="font-medium text-sm">Betting Lines Shift on Championship Odds</h4>
                        <p className="text-xs text-muted-foreground">
                          Celtics now favored at +280, Lakers drop to +1200 after recent struggles
                        </p>
                        <div className="text-xs text-muted-foreground mt-1">FanDuel • 4 hours ago</div>
                      </div>
                      <Badge variant="outline" className="text-xs">Odds Movement</Badge>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <h3 className="font-bold flex items-center gap-2">
                  <TrendingUp className="w-5 h-5" />
                  Social Sentiment Analysis
                </h3>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <img src="https://cdn.nba.com/logos/nba/1610612738/primary/L/logo.svg" alt="Celtics" className="w-8 h-8" />
                      <div>
                        <div className="font-medium text-sm">Boston Celtics</div>
                        <div className="text-xs text-green-600">Positive trending</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-bold text-green-600">+85%</div>
                      <div className="text-xs text-muted-foreground">Fan sentiment</div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-red-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <img src="https://cdn.nba.com/logos/nba/1610612744/primary/L/logo.svg" alt="Warriors" className="w-8 h-8" />
                      <div>
                        <div className="font-medium text-sm">Golden State Warriors</div>
                        <div className="text-xs text-red-600">Negative trending</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-bold text-red-600">-42%</div>
                      <div className="text-xs text-muted-foreground">Fan sentiment</div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-yellow-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <img src="https://cdn.nba.com/logos/nba/1610612766/primary/L/logo.svg" alt="Hornets" className="w-8 h-8" />
                      <div>
                        <div className="font-medium text-sm">Charlotte Hornets</div>
                        <div className="text-xs text-yellow-600">Optimism rising</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-bold text-yellow-600">+28%</div>
                      <div className="text-xs text-muted-foreground">Young core hype</div>
                    </div>
                  </div>

                  <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                    <div className="text-xs font-medium text-blue-800 mb-1">Trending Topics</div>
                    <div className="flex flex-wrap gap-1">
                      <Badge variant="secondary" className="text-xs">#TradeDeadline</Badge>
                      <Badge variant="secondary" className="text-xs">#AllStarVoting</Badge>
                      <Badge variant="secondary" className="text-xs">#RookieWatch</Badge>
                      <Badge variant="secondary" className="text-xs">#PlayoffRace</Badge>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="alerts" className="space-y-6">
          {/* Live Alerts System */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <h3 className="font-bold flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-red-500" />
                  Performance Alerts
                  <Badge variant="destructive" className="text-xs">
                    3 Active
                  </Badge>
                </h3>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-start gap-3 p-3 bg-red-50 rounded-lg border-l-4 border-l-red-500">
                    <AlertTriangle className="w-4 h-4 text-red-500 mt-0.5" />
                    <div className="flex-1">
                      <h4 className="font-medium text-sm">Warriors Defensive Collapse</h4>
                      <p className="text-xs text-muted-foreground mb-2">
                        Defensive rating of 125.3 over last 5 games - worst 5-game stretch since 2019
                      </p>
                      <div className="flex items-center gap-2">
                        <Badge variant="destructive" className="text-xs">Critical</Badge>
                        <span className="text-xs text-muted-foreground">Triggered 2 hours ago</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 bg-yellow-50 rounded-lg border-l-4 border-l-yellow-500">
                    <TrendingDown className="w-4 h-4 text-yellow-500 mt-0.5" />
                    <div className="flex-1">
                      <h4 className="font-medium text-sm">Lakers Shooting Slump</h4>
                      <p className="text-xs text-muted-foreground mb-2">
                        3-point shooting down to 28.1% over last 10 games, well below season average
                      </p>
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary" className="text-xs">Warning</Badge>
                        <span className="text-xs text-muted-foreground">Triggered 6 hours ago</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 bg-orange-50 rounded-lg border-l-4 border-l-orange-500">
                    <Target className="w-4 h-4 text-orange-500 mt-0.5" />
                    <div className="flex-1">
                      <h4 className="font-medium text-sm">Hornets Injury Concerns</h4>
                      <p className="text-xs text-muted-foreground mb-2">
                        Multiple key players dealing with injuries, depth being tested
                      </p>
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary" className="text-xs">Monitor</Badge>
                        <span className="text-xs text-muted-foreground">Triggered 1 day ago</span>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <h3 className="font-bold flex items-center gap-2">
                  <Trophy className="w-5 h-5 text-green-500" />
                  Opportunity Alerts
                  <Badge variant="default" className="text-xs">
                    2 Active
                  </Badge>
                </h3>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-start gap-3 p-3 bg-green-50 rounded-lg border-l-4 border-l-green-500">
                    <TrendingUp className="w-4 h-4 text-green-500 mt-0.5" />
                    <div className="flex-1">
                      <h4 className="font-medium text-sm">Brandon Miller Breakout Window</h4>
                      <p className="text-xs text-muted-foreground mb-2">
                        Perfect storm of increased usage, improved efficiency, and team commitment
                      </p>
                      <div className="flex items-center gap-2">
                        <Badge variant="default" className="text-xs">High Confidence</Badge>
                        <span className="text-xs text-muted-foreground">Triggered 4 hours ago</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 bg-blue-50 rounded-lg border-l-4 border-l-blue-500">
                    <GitCompare className="w-4 h-4 text-blue-500 mt-0.5" />
                    <div className="flex-1">
                      <h4 className="font-medium text-sm">Lakers-Hawks Trade Window</h4>
                      <p className="text-xs text-muted-foreground mb-2">
                        Salary matching, positional needs, and timeline alignment create opportunity
                      </p>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">Developing</Badge>
                        <span className="text-xs text-muted-foreground">Triggered 1 day ago</span>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="network" className="space-y-6">
          {/* Network Analysis */}
          <Card>
            <CardHeader>
              <h3 className="font-bold flex items-center gap-2">
                <Activity className="w-5 h-5" />
                Advanced Network Analysis
              </h3>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div>
                  <h4 className="font-semibold mb-4">Trade Relationship Network</h4>
                  <div className="space-y-3">
                    <div className="p-3 bg-muted rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Lakers ↔ Hawks</span>
                        <Badge variant="default" className="text-xs">Active</Badge>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Historical frequency: 3.2/year<br/>
                        Success rate: 75%<br/>
                        Current compatibility: High
                      </div>
                    </div>

                    <div className="p-3 bg-muted rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Warriors ↔ Nets</span>
                        <Badge variant="secondary" className="text-xs">Cooling</Badge>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Historical frequency: 2.1/year<br/>
                        Success rate: 60%<br/>
                        Current compatibility: Medium
                      </div>
                    </div>

                    <div className="p-3 bg-muted rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Celtics ↔ Hornets</span>
                        <Badge variant="outline" className="text-xs">Emerging</Badge>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Historical frequency: 1.8/year<br/>
                        Success rate: 85%<br/>
                        Current compatibility: Very High
                      </div>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="font-semibold mb-4">Coaching Network</h4>
                  <div className="space-y-3">
                    <div className="p-3 bg-muted rounded-lg">
                      <div className="text-sm font-medium mb-1">Mike Budenholzer Tree</div>
                      <div className="text-xs text-muted-foreground">
                        • Taylor Jenkins (Grizzlies)<br/>
                        • James Borrego (Former Hornets)<br/>
                        • Darvin Ham (Lakers)<br/>
                        Similar systems, player development
                      </div>
                    </div>

                    <div className="p-3 bg-muted rounded-lg">
                      <div className="text-sm font-medium mb-1">Steve Kerr Disciples</div>
                      <div className="text-xs text-muted-foreground">
                        • Luke Walton (Former Kings)<br/>
                        • Jordi Fernandez (Nets Assistant)<br/>
                        Motion offense specialists
                      </div>
                    </div>

                    <div className="p-3 bg-muted rounded-lg">
                      <div className="text-sm font-medium mb-1">Player Development Hub</div>
                      <div className="text-xs text-muted-foreground">
                        Teams known for player growth:<br/>
                        Spurs, Heat, Warriors, Celtics<br/>
                        Strong development infrastructure
                      </div>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="font-semibold mb-4">Market Intelligence</h4>
                  <div className="space-y-3">
                    <div className="p-3 bg-blue-50 rounded-lg">
                      <div className="text-sm font-medium text-blue-800 mb-1">Trade Deadline Approach</div>
                      <div className="text-xs text-blue-600">
                        Activity typically increases 300% in final 2 weeks
                      </div>
                    </div>

                    <div className="p-3 bg-green-50 rounded-lg">
                      <div className="text-sm font-medium text-green-800 mb-1">Cap Space Opportunities</div>
                      <div className="text-xs text-green-600">
                        4 teams with 15M+ in space<br/>
                        Prime for salary dumps
                      </div>
                    </div>

                    <div className="p-3 bg-yellow-50 rounded-lg">
                      <div className="text-sm font-medium text-yellow-800 mb-1">Contract Extensions</div>
                      <div className="text-xs text-yellow-600">
                        23 players eligible<br/>
                        Deadline pressure building
                      </div>
                    </div>

                    <div className="p-3 bg-purple-50 rounded-lg">
                      <div className="text-sm font-medium text-purple-800 mb-1">Draft Capital</div>
                      <div className="text-xs text-purple-600">
                        15 teams with multiple 1st rounders<br/>
                        High trade currency available
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="advancedAnalytics" className="space-y-6">
          <Card>
            <CardHeader>
              <h3 className="font-bold flex items-center gap-2">
                <Brain className="w-5 h-5" />
                Advanced Analytics Suite
              </h3>
            </CardHeader>
            <CardContent>
              <Tabs value={activeAdvancedTab} onValueChange={setActiveAdvancedTab} className="w-full">
                <TabsList className="grid w-full grid-cols-3 md:grid-cols-7 gap-1 p-1 h-auto">
                  <TabsTrigger value="teamChemistry" className="flex-col h-16 text-xs p-1">
                    <Users className="w-4 h-4 mb-1" />Team Chemistry
                  </TabsTrigger>
                  <TabsTrigger value="shotVisualizer" className="flex-col h-16 text-xs p-1">
                    <AreaChart className="w-4 h-4 mb-1" />Shot Visualizer
                  </TabsTrigger>
                  <TabsTrigger value="gameIntelligence" className="flex-col h-16 text-xs p-1">
                    <Zap className="w-4 h-4 mb-1" />Game Intelligence
                  </TabsTrigger>
                  <TabsTrigger value="aiHub" className="flex-col h-16 text-xs p-1">
                    <Bot className="w-4 h-4 mb-1" />AI Hub
                  </TabsTrigger>
                  <TabsTrigger value="marketIntelAdvanced" className="flex-col h-16 text-xs p-1">
                     <BarChart3 className="w-4 h-4 mb-1" />Market Intel
                  </TabsTrigger>
                  <TabsTrigger value="teamStrategy" className="flex-col h-16 text-xs p-1">
                    <Target className="w-4 h-4 mb-1" />Strategy Optimizer
                  </TabsTrigger>
                  <TabsTrigger value="mlAnalytics" className="flex-col h-16 text-xs p-1">
                    <Brain className="w-4 h-4 mb-1" />ML Analytics
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="teamChemistry" className="mt-4">
                  <TeamChemistryNetwork players={[]} connections={[]} teamName="Selected Team" season="2023-24" viewMode="chemistry" />
                </TabsContent>
                <TabsContent value="shotVisualizer" className="mt-4">
                  <ShotTrajectoryVisualizer playerName="Selected Player" shots={[]} viewMode="trajectory" courtAngle={0} />
                </TabsContent>
                <TabsContent value="gameIntelligence" className="mt-4">
                  <GameIntelligenceDashboard gameData={{gameId: '', homeTeam: '', awayTeam: '', quarter: 0, timeRemaining: '', homeScore: 0, awayScore: 0, possession: 'home', shotClock: 0, gameStatus: 'upcoming', broadcast: ''}} homePerformances={[]} awayPerformances={[]} homeMetrics={{team: 'home', teamName: '', fieldGoalPercentage: 0, threePointPercentage: 0, freeThrowPercentage: 0, totalRebounds: 0, assists: 0, turnovers: 0, pace: 0, offensiveRating: 0, defensiveRating: 0, netRating: 0, momentum: 0, energyLevel: 0, chemistry: 0, coaching: 0, winProbability: 0, projectedFinalScore: 0}} awayMetrics={{team: 'away', teamName: '', fieldGoalPercentage: 0, threePointPercentage: 0, freeThrowPercentage: 0, totalRebounds: 0, assists: 0, turnovers: 0, pace: 0, offensiveRating: 0, defensiveRating: 0, netRating: 0, momentum: 0, energyLevel: 0, chemistry: 0, coaching: 0, winProbability: 0, projectedFinalScore: 0}} aiInsights={[]} />
                </TabsContent>
                <TabsContent value="aiHub" className="mt-4">
                  <AIOrchestrationHub />
                </TabsContent>
                <TabsContent value="marketIntelAdvanced" className="mt-4">
                  <MarketIntelligenceDashboard />
                </TabsContent>
                <TabsContent value="teamStrategy" className="mt-4">
                  <TeamStrategyOptimizer />
                </TabsContent>
                <TabsContent value="mlAnalytics" className="mt-4">
                  <AdvancedAnalyticsDashboard
                    season={currentSeason}
                  />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="teams">
          {/* Teams Display */}
          <div className="space-y-4">
        {viewMode === 'grid' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {filteredAndSortedTeams.map(renderTeamCard)}
          </div>
        )}

        {viewMode === 'list' && (
          <div className="space-y-4">
            {filteredAndSortedTeams.map((team) => (
              <Card key={team.id} className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <Checkbox
                      checked={selectedTeams.includes(team.id)}
                      onCheckedChange={() => toggleTeamSelection(team.id)}
                    />
                    <img src={team.logo} alt={team.name} className="w-12 h-12" />
                    <div>
                      <h3 className="font-bold">{team.name}</h3>
                      <p className="text-sm text-muted-foreground">{team.conference}ern • {team.division}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-8 text-sm">
                    <div className="text-center">
                      <div className="font-bold">{team.record.wins}-{team.record.losses}</div>
                      <div className="text-muted-foreground">Record</div>
                    </div>
                    <div className="text-center">
                      <div className="font-bold">{team.offensiveRating}</div>
                      <div className="text-muted-foreground">OFF RTG</div>
                    </div>
                    <div className="text-center">
                      <div className="font-bold">{team.defensiveRating}</div>
                      <div className="text-muted-foreground">DEF RTG</div>
                    </div>
                    <div className="text-center">
                      <div className="font-bold">{team.playoffOdds}%</div>
                      <div className="text-muted-foreground">Playoffs</div>
                    </div>
                    <Button asChild>
                      <Link href={`/teams/${team.id}`}>View Details</Link>
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}

        {viewMode === 'table' && (
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="border-b">
                    <tr className="text-left">
                      <th className="p-4">Team</th>
                      <th className="p-4">Record</th>
                      <th className="p-4">Streak</th>
                      <th className="p-4">OFF RTG</th>
                      <th className="p-4">DEF RTG</th>
                      <th className="p-4">Pace</th>
                      <th className="p-4">Playoff %</th>
                      <th className="p-4">Status</th>
                      <th className="p-4">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredAndSortedTeams.map((team) => (
                      <tr key={team.id} className="border-b hover:bg-muted/50">
                        <td className="p-4">
                          <div className="flex items-center gap-3">
                            <Checkbox
                              checked={selectedTeams.includes(team.id)}
                              onCheckedChange={() => toggleTeamSelection(team.id)}
                            />
                            <img src={team.logo} alt={team.name} className="w-8 h-8" />
                            <div>
                              <div className="font-medium">{team.name}</div>
                              <div className="text-sm text-muted-foreground">{team.abbreviation}</div>
                            </div>
                          </div>
                        </td>
                        <td className="p-4 font-medium">{team.record.wins}-{team.record.losses}</td>
                        <td className="p-4">
                          <Badge variant={team.streak.type === 'W' ? 'default' : 'destructive'}>
                            {team.streak.type}{team.streak.count}
                          </Badge>
                        </td>
                        <td className="p-4">{team.offensiveRating}</td>
                        <td className="p-4">{team.defensiveRating}</td>
                        <td className="p-4">{team.pace}</td>
                        <td className="p-4">{team.playoffOdds}%</td>
                        <td className="p-4">
                          <Badge className={getStatusBadgeColor(team.status)}>
                            {team.status.replace('-', ' ')}
                          </Badge>
                        </td>
                        <td className="p-4">
                          <Button size="sm" asChild>
                            <Link href={`/teams/${team.id}`}>
                              <Eye className="w-4 h-4 mr-2" />
                              View
                            </Link>
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {viewMode === 'analytics' && (
          <div className="space-y-6">
            {/* Performance Heat Map */}
            <Card>
              <CardHeader>
                <h3 className="font-bold flex items-center gap-2">
                  <BarChart3 className="w-5 h-5" />
                  League Performance Heat Map
                </h3>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                  <div className="text-center p-4 bg-muted rounded-lg">
                    <div className="text-2xl font-bold text-green-600">
                      {filteredAndSortedTeams.filter(t => t.offensiveRating > 118).length}
                    </div>
                    <div className="text-sm text-muted-foreground">Elite Offense (118+ RTG)</div>
                  </div>
                  <div className="text-center p-4 bg-muted rounded-lg">
                    <div className="text-2xl font-bold text-blue-600">
                      {filteredAndSortedTeams.filter(t => t.defensiveRating < 112).length}
                    </div>
                    <div className="text-sm text-muted-foreground">Elite Defense (&lt;112 RTG)</div>
                  </div>
                  <div className="text-center p-4 bg-muted rounded-lg">
                    <div className="text-2xl font-bold text-purple-600">
                      {filteredAndSortedTeams.filter(t => t.pace > 102).length}
                    </div>
                    <div className="text-sm text-muted-foreground">High Pace (102+)</div>
                  </div>
                  <div className="text-center p-4 bg-muted rounded-lg">
                    <div className="text-2xl font-bold text-yellow-600">
                      {filteredAndSortedTeams.filter(t => t.playoffOdds > 80).length}
                    </div>
                    <div className="text-sm text-muted-foreground">Playoff Locks (80%+)</div>
                  </div>
                </div>

                {/* Team Performance Matrix */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div>
                    <h4 className="font-semibold mb-3">Offensive vs Defensive Efficiency</h4>
                    <div className="space-y-2">
                      {filteredAndSortedTeams.slice(0, 6).map((team) => (
                        <div key={team.id} className="flex items-center justify-between p-2 bg-muted rounded">
                          <div className="flex items-center gap-2">
                            <img src={team.logo} alt={team.name} className="w-6 h-6" />
                            <span className="text-sm font-medium">{team.abbreviation}</span>
                          </div>
                          <div className="flex items-center gap-4 text-sm">
                            <div className="text-green-600">OFF: {team.offensiveRating}</div>
                            <div className="text-red-600">DEF: {team.defensiveRating}</div>
                            <div className="font-bold">
                              NET: {(team.offensiveRating - team.defensiveRating).toFixed(1)}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <h4 className="font-semibold mb-3">Championship Probability Analysis</h4>
                    <div className="space-y-2">
                      {filteredAndSortedTeams
                        .filter(t => t.playoffOdds > 50)
                        .sort((a, b) => b.playoffOdds - a.playoffOdds)
                        .slice(0, 6)
                        .map((team) => (
                        <div key={team.id} className="flex items-center justify-between p-2 bg-muted rounded">
                          <div className="flex items-center gap-2">
                            <img src={team.logo} alt={team.name} className="w-6 h-6" />
                            <span className="text-sm font-medium">{team.name}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="w-20 bg-gray-200 rounded-full h-2">
                              <div
                                className="bg-blue-600 h-2 rounded-full"
                                style={{ width: `${team.playoffOdds}%` }}
                              ></div>
                            </div>
                            <span className="text-sm font-bold">{team.playoffOdds}%</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Advanced Analytics Dashboard */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <Card>
                <CardHeader>
                  <h3 className="font-bold">Conference Breakdown</h3>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div>
                      <div className="flex justify-between text-sm mb-2">
                        <span>Eastern Conference Avg OFF RTG</span>
                        <span className="font-medium">
                          {(filteredAndSortedTeams
                            .filter(t => t.conference === 'East')
                            .reduce((sum, t) => sum + t.offensiveRating, 0) /
                           Math.max(filteredAndSortedTeams.filter(t => t.conference === 'East').length, 1)
                          ).toFixed(1)}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm mb-2">
                        <span>Western Conference Avg OFF RTG</span>
                        <span className="font-medium">
                          {(filteredAndSortedTeams
                            .filter(t => t.conference === 'West')
                            .reduce((sum, t) => sum + t.offensiveRating, 0) /
                           Math.max(filteredAndSortedTeams.filter(t => t.conference === 'West').length, 1)
                          ).toFixed(1)}
                        </span>
                      </div>
                      <div className="mt-4 text-xs text-muted-foreground">
                        <Badge variant={
                          (filteredAndSortedTeams.filter(t => t.conference === 'East').reduce((sum, t) => sum + t.offensiveRating, 0) /
                           Math.max(filteredAndSortedTeams.filter(t => t.conference === 'East').length, 1)) >
                          (filteredAndSortedTeams.filter(t => t.conference === 'West').reduce((sum, t) => sum + t.offensiveRating, 0) /
                           Math.max(filteredAndSortedTeams.filter(t => t.conference === 'West').length, 1))
                           ? 'default' : 'secondary'
                        }>
                          {(filteredAndSortedTeams.filter(t => t.conference === 'East').reduce((sum, t) => sum + t.offensiveRating, 0) /
                            Math.max(filteredAndSortedTeams.filter(t => t.conference === 'East').length, 1)) >
                           (filteredAndSortedTeams.filter(t => t.conference === 'West').reduce((sum, t) => sum + t.offensiveRating, 0) /
                            Math.max(filteredAndSortedTeams.filter(t => t.conference === 'West').length, 1))
                            ? 'East leads offense' : 'West leads offense'}
                        </Badge>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <h3 className="font-bold">League Insights</h3>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Teams with 20+ wins</span>
                      <Badge>{filteredAndSortedTeams.filter(t => t.record.wins >= 20).length}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Teams rebuilding</span>
                      <Badge variant="destructive">{filteredAndSortedTeams.filter(t => t.status === 'rebuilding').length}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Teams with major injuries</span>
                      <Badge variant="secondary">{filteredAndSortedTeams.filter(t => t.injuries.length > 0).length}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Championship contenders</span>
                      <Badge className="bg-green-500">{filteredAndSortedTeams.filter(t => t.status === 'contender').length}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">High pace teams</span>
                      <Badge className="bg-purple-500">{filteredAndSortedTeams.filter(t => t.pace > 102).length}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Playoff bubble</span>
                      <Badge className="bg-yellow-500">
                        {filteredAndSortedTeams.filter(t => t.playoffOdds >= 30 && t.playoffOdds <= 70).length}
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <h3 className="font-bold">Trade & Contract Intel</h3>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Teams with cap space</span>
                      <Badge className="bg-green-500">{filteredAndSortedTeams.filter(t => t.capSpace > 10).length}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Cap-strapped teams</span>
                      <Badge variant="destructive">{filteredAndSortedTeams.filter(t => t.capSpace < 3).length}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Teams with injuries</span>
                      <Badge variant="secondary">{filteredAndSortedTeams.filter(t => t.injuries.length > 1).length}</Badge>
                    </div>
                    <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                      <div className="text-xs font-medium text-blue-800 mb-1">AI Trade Alert</div>
                      <div className="text-xs text-blue-600">
                        3 teams likely to make moves before deadline based on performance and cap situation
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Network Analysis Preview */}
            <Card>
              <CardHeader>
                <h3 className="font-bold flex items-center gap-2">
                  <Activity className="w-5 h-5" />
                  League Network Analysis
                </h3>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="space-y-3">
                    <h4 className="font-semibold text-sm">Most Active Trading Partners</h4>
                    <div className="space-y-2 text-sm">
                      <div>Lakers ↔ Hawks (3 trades)</div>
                      <div>Warriors ↔ Nets (2 trades)</div>
                      <div>Celtics ↔ Hornets (2 trades)</div>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <h4 className="font-semibold text-sm">Salary Matching Opportunities</h4>
                    <div className="space-y-2 text-sm">
                      <div>Russell ($18M) ↔ Murray ($25M)</div>
                      <div>Wiggins ($24M) ↔ Collins ($26M)</div>
                      <div>Simmons ($40M) ↔ Multiple</div>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <h4 className="font-semibold text-sm">Contract Expiration Timeline</h4>
                    <div className="space-y-2 text-sm">
                      <div>2024 Free Agents: 47 players</div>
                      <div>Team Options: 12 decisions</div>
                      <div>Extension Eligible: 23 players</div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Results Summary */}
        <div className="text-center text-sm text-muted-foreground">
          Showing {filteredAndSortedTeams.length} of {teams.length} teams
          {selectedTeams.length > 0 && ` • ${selectedTeams.length} selected`}
        </div>
      </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}