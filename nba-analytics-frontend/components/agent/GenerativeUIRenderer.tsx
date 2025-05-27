"use client"

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  User,
  Users,
  ArrowUpDown,
  BarChart3,
  Target,
  Trophy,
  Zap,
  Star,
  Activity,
  Award,
  Crown,
  Flame,
  Sparkles
} from 'lucide-react';

interface StatCardData {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: 'up' | 'down' | 'neutral';
  rank?: number;
  category: string;
  color: string;
}

interface PlayerCardData {
  name: string;
  position: string;
  stats: Record<string, string | number>;
  performance_rating: number;
  contract?: Record<string, any>;
  trade_value?: string;
}

interface TeamAnalysisData {
  team_name: string;
  season: string;
  record: string;
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
  urgency: string;
}

interface TradeScenarioData {
  title: string;
  players_out: string[];
  players_in: string[];
  rationale: string;
  probability: number;
  risk_level: string;
  timeline: string;
}

interface ChartData {
  type: string;
  title: string;
  data: Record<string, any>[];
  labels?: string[];
  colors?: string[];
  description?: string;
}

interface ToolCall {
  tool_name: string;
  content?: string;
  status: string;
  args?: any;
}

interface GenerativeUIRendererProps {
  content: string;
  toolCalls?: ToolCall[];
}

function StatCard({ data }: { data: StatCardData }) {
  const getTrendIcon = (trend?: string) => {
    switch (trend) {
      case 'up': return <TrendingUp className="h-5 w-5 text-emerald-500" />;
      case 'down': return <TrendingDown className="h-5 w-5 text-red-500" />;
      case 'neutral': return <Minus className="h-5 w-5 text-slate-500" />;
      default: return null;
    }
  };

  const getStatIcon = (title: string) => {
    const titleLower = title.toLowerCase();
    if (titleLower.includes('point')) return <Target className="h-5 w-5" />;
    if (titleLower.includes('assist')) return <Users className="h-5 w-5" />;
    if (titleLower.includes('rebound')) return <Activity className="h-5 w-5" />;
    if (titleLower.includes('steal')) return <Zap className="h-5 w-5" />;
    if (titleLower.includes('block')) return <Award className="h-5 w-5" />;
    if (titleLower.includes('rating') || titleLower.includes('efficiency')) return <Star className="h-5 w-5" />;
    return <BarChart3 className="h-5 w-5" />;
  };

  const getGradientClass = (color: string, trend?: string) => {
    const baseClasses = "relative overflow-hidden border-0 shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105";

    switch (color) {
      case 'success':
        return `${baseClasses} bg-gradient-to-br from-emerald-500 via-emerald-600 to-emerald-700 text-white`;
      case 'warning':
        return `${baseClasses} bg-gradient-to-br from-amber-500 via-amber-600 to-amber-700 text-white`;
      case 'destructive':
        return `${baseClasses} bg-gradient-to-br from-red-500 via-red-600 to-red-700 text-white`;
      default:
        if (trend === 'up') {
          return `${baseClasses} bg-gradient-to-br from-emerald-500 via-emerald-600 to-emerald-700 text-white`;
        } else if (trend === 'down') {
          return `${baseClasses} bg-gradient-to-br from-red-500 via-red-600 to-red-700 text-white`;
        }
        return `${baseClasses} bg-gradient-to-br from-blue-500 via-blue-600 to-blue-700 text-white`;
    }
  };

  const getTrendBadgeClass = (trend?: string) => {
    switch (trend) {
      case 'up': return 'bg-emerald-500/20 text-emerald-100 border-emerald-400/30';
      case 'down': return 'bg-red-500/20 text-red-100 border-red-400/30';
      case 'neutral': return 'bg-slate-500/20 text-slate-100 border-slate-400/30';
      default: return 'bg-white/20 text-white border-white/30';
    }
  };

  return (
    <Card className={`w-full max-w-sm min-w-[200px] ${getGradientClass(data.color, data.trend)}`}>
      {/* Decorative background pattern */}
      <div className="absolute inset-0 opacity-10">
        <div className="absolute top-0 right-0 w-32 h-32 rounded-full bg-white/20 -translate-y-16 translate-x-16"></div>
        <div className="absolute bottom-0 left-0 w-24 h-24 rounded-full bg-white/10 translate-y-12 -translate-x-12"></div>
      </div>

      <CardHeader className="pb-3 relative z-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-white/20 backdrop-blur-sm">
              {getStatIcon(data.title)}
            </div>
            <CardTitle className="text-sm font-semibold text-white/90">{data.title}</CardTitle>
          </div>
          {getTrendIcon(data.trend)}
        </div>
      </CardHeader>

      <CardContent className="relative z-10">
        <div className="space-y-3">
          <div className="flex items-baseline gap-2">
            <div className="text-3xl font-bold text-white">{data.value}</div>
            {data.trend && (
              <Badge className={`text-xs font-medium ${getTrendBadgeClass(data.trend)}`}>
                {data.trend === 'up' ? '↗' : data.trend === 'down' ? '↘' : '→'}
              </Badge>
            )}
          </div>

          <div className="flex items-center justify-between">
            {data.subtitle && (
              <p className="text-xs text-white/70 font-medium">{data.subtitle}</p>
            )}
            {data.rank && (
              <Badge className="bg-white/20 text-white border-white/30 text-xs font-semibold">
                <Crown className="h-3 w-3 mr-1" />
                #{data.rank}
              </Badge>
            )}
          </div>

          {/* Performance indicator bar */}
          <div className="w-full h-1 bg-white/20 rounded-full overflow-hidden">
            <div
              className="h-full bg-white/60 rounded-full transition-all duration-1000 ease-out"
              style={{ width: `${Math.min(100, Math.max(10, parseFloat(String(data.value)) * 3))}%` }}
            ></div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function PlayerCard({ data }: { data: PlayerCardData }) {
  const getPerformanceColor = (rating: number) => {
    if (rating >= 8) return 'from-emerald-500 to-emerald-600';
    if (rating >= 6) return 'from-blue-500 to-blue-600';
    if (rating >= 4) return 'from-amber-500 to-amber-600';
    return 'from-red-500 to-red-600';
  };

  const getTradeValueBadge = (value?: string) => {
    switch (value) {
      case 'high': return { variant: 'default' as const, icon: <Flame className="h-3 w-3" />, color: 'text-red-500' };
      case 'medium': return { variant: 'secondary' as const, icon: <Star className="h-3 w-3" />, color: 'text-amber-500' };
      case 'low': return { variant: 'outline' as const, icon: <Minus className="h-3 w-3" />, color: 'text-slate-500' };
      default: return { variant: 'outline' as const, icon: <BarChart3 className="h-3 w-3" />, color: 'text-slate-500' };
    }
  };

  const tradeValueBadge = getTradeValueBadge(data.trade_value);

  return (
    <Card className="w-full max-w-md bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 border-2 hover:shadow-lg transition-all duration-300">
      <CardHeader className="pb-4">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 text-white shadow-lg">
            <User className="h-6 w-6" />
          </div>
          <div className="flex-1">
            <CardTitle className="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              {data.name}
            </CardTitle>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant="secondary" className="text-xs font-semibold">
                {data.position}
              </Badge>
              {data.trade_value && (
                <Badge variant={tradeValueBadge.variant} className="text-xs font-medium">
                  {tradeValueBadge.icon}
                  <span className="ml-1">{data.trade_value} value</span>
                </Badge>
              )}
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-3">
          {Object.entries(data.stats).map(([key, value]) => (
            <div key={key} className="bg-white dark:bg-slate-800 rounded-lg p-3 border shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{key}</span>
                <Sparkles className="h-3 w-3 text-blue-500" />
              </div>
              <div className="text-lg font-bold text-foreground mt-1">{value}</div>
            </div>
          ))}
        </div>

        {/* Performance Rating */}
        <div className="bg-white dark:bg-slate-800 rounded-lg p-4 border shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Trophy className="h-4 w-4 text-amber-500" />
              <span className="text-sm font-semibold">Performance Rating</span>
            </div>
            <span className="text-lg font-bold">{data.performance_rating}/10</span>
          </div>

          {/* Custom Progress Bar */}
          <div className="relative w-full h-3 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
            <div
              className={`h-full bg-gradient-to-r ${getPerformanceColor(data.performance_rating)} rounded-full transition-all duration-1000 ease-out relative`}
              style={{ width: `${data.performance_rating * 10}%` }}
            >
              <div className="absolute inset-0 bg-white/20 animate-pulse"></div>
            </div>
          </div>

          {/* Rating Labels */}
          <div className="flex justify-between text-xs text-muted-foreground mt-2">
            <span>Poor</span>
            <span>Average</span>
            <span>Elite</span>
          </div>
        </div>

        {/* Contract Info */}
        {data.contract && (
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-950 dark:to-emerald-950 rounded-lg p-3 border border-green-200 dark:border-green-800">
            <div className="flex items-center gap-2 mb-2">
              <Award className="h-4 w-4 text-green-600" />
              <span className="text-sm font-semibold text-green-800 dark:text-green-200">Contract Details</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {Object.entries(data.contract).map(([key, value]) => (
                <div key={key} className="flex justify-between">
                  <span className="text-green-700 dark:text-green-300 capitalize">{key}:</span>
                  <span className="font-medium text-green-800 dark:text-green-200">{String(value)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TeamAnalysisCard({ data }: { data: TeamAnalysisData }) {
  const getUrgencyColor = (urgency: string) => {
    switch (urgency) {
      case 'high': return 'destructive';
      case 'medium': return 'default';
      case 'low': return 'secondary';
      default: return 'outline';
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            <div>
              <CardTitle>{data.team_name}</CardTitle>
              <p className="text-sm text-muted-foreground">{data.season} • {data.record}</p>
            </div>
          </div>
          <Badge variant={getUrgencyColor(data.urgency)}>
            {data.urgency} priority
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <h4 className="font-medium text-green-700 dark:text-green-400 mb-2">Strengths</h4>
          <ul className="text-sm space-y-1">
            {data.strengths.map((strength, index) => (
              <li key={index} className="flex items-start gap-2">
                <span className="text-green-500 mt-1">•</span>
                {strength}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="font-medium text-red-700 dark:text-red-400 mb-2">Weaknesses</h4>
          <ul className="text-sm space-y-1">
            {data.weaknesses.map((weakness, index) => (
              <li key={index} className="flex items-start gap-2">
                <span className="text-red-500 mt-1">•</span>
                {weakness}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="font-medium text-blue-700 dark:text-blue-400 mb-2">Recommendations</h4>
          <ul className="text-sm space-y-1">
            {data.recommendations.map((rec, index) => (
              <li key={index} className="flex items-start gap-2">
                <span className="text-blue-500 mt-1">•</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}

function TradeScenarioCard({ data }: { data: TradeScenarioData }) {
  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'high': return 'text-red-500';
      case 'medium': return 'text-yellow-500';
      case 'low': return 'text-green-500';
      default: return 'text-gray-500';
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center gap-2">
          <ArrowUpDown className="h-5 w-5" />
          <CardTitle>{data.title}</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h4 className="font-medium text-red-600 dark:text-red-400 mb-2">Trading Away</h4>
            <ul className="text-sm space-y-1">
              {data.players_out.map((player, index) => (
                <li key={index}>• {player}</li>
              ))}
            </ul>
          </div>
          <div>
            <h4 className="font-medium text-green-600 dark:text-green-400 mb-2">Acquiring</h4>
            <ul className="text-sm space-y-1">
              {data.players_in.map((player, index) => (
                <li key={index}>• {player}</li>
              ))}
            </ul>
          </div>
        </div>
        <div>
          <h4 className="font-medium mb-2">Rationale</h4>
          <p className="text-sm text-muted-foreground">{data.rationale}</p>
        </div>
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <span>Success Probability:</span>
            <span className="font-medium">{data.probability}%</span>
          </div>
          <div className="flex items-center gap-2">
            <span>Risk Level:</span>
            <span className={`font-medium ${getRiskColor(data.risk_level)}`}>
              {data.risk_level}
            </span>
          </div>
        </div>
        <div className="text-xs text-muted-foreground">
          Timeline: {data.timeline}
        </div>
      </CardContent>
    </Card>
  );
}

export function GenerativeUIRenderer({ content, toolCalls }: GenerativeUIRendererProps) {
  const renderComponents = () => {
    const components: React.ReactNode[] = [];

    // Combine content and tool call content for parsing
    let allContent = content;
    if (toolCalls) {
      toolCalls.forEach(tool => {
        if (tool.content) {
          allContent += '\n' + tool.content;
        }
      });
    }

    // Parse STAT_CARD_JSON markers
    const statCardMatches = allContent.match(/STAT_CARD_JSON::({.*?})/g);

    if (statCardMatches) {
      statCardMatches.forEach((match, index) => {
        try {
          const jsonStr = match.replace('STAT_CARD_JSON::', '');
          const data: StatCardData = JSON.parse(jsonStr);
          components.push(<StatCard key={`stat-${index}`} data={data} />);
        } catch (e) {
          console.error('Failed to parse stat card JSON:', e);
        }
      });
    }

    // Parse PLAYER_CARD_JSON markers
    const playerCardMatches = allContent.match(/PLAYER_CARD_JSON::({.*?})/g);
    if (playerCardMatches) {
      playerCardMatches.forEach((match, index) => {
        try {
          const jsonStr = match.replace('PLAYER_CARD_JSON::', '');
          const data: PlayerCardData = JSON.parse(jsonStr);
          components.push(<PlayerCard key={`player-${index}`} data={data} />);
        } catch (e) {
          console.error('Failed to parse player card JSON:', e);
        }
      });
    }

    // Parse TEAM_ANALYSIS_JSON markers
    const teamAnalysisMatches = allContent.match(/TEAM_ANALYSIS_JSON::({.*?})/g);
    if (teamAnalysisMatches) {
      teamAnalysisMatches.forEach((match, index) => {
        try {
          const jsonStr = match.replace('TEAM_ANALYSIS_JSON::', '');
          const data: TeamAnalysisData = JSON.parse(jsonStr);
          components.push(<TeamAnalysisCard key={`team-${index}`} data={data} />);
        } catch (e) {
          console.error('Failed to parse team analysis JSON:', e);
        }
      });
    }

    // Parse TRADE_SCENARIO_JSON markers
    const tradeScenarioMatches = allContent.match(/TRADE_SCENARIO_JSON::({.*?})/g);
    if (tradeScenarioMatches) {
      tradeScenarioMatches.forEach((match, index) => {
        try {
          const jsonStr = match.replace('TRADE_SCENARIO_JSON::', '');
          const data: TradeScenarioData = JSON.parse(jsonStr);
          components.push(<TradeScenarioCard key={`trade-${index}`} data={data} />);
        } catch (e) {
          console.error('Failed to parse trade scenario JSON:', e);
        }
      });
    }

    return components;
  };

  const components = renderComponents();

  if (components.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-4 my-4">
      {components}
    </div>
  );
}
