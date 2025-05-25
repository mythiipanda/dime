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
import { Progress } from '@/components/ui/progress';
import { Input } from '@/components/ui/input';
import { TradeAnalysis } from '@/components/teams/TradeAnalysis';
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Target,
  Zap,
  BarChart3,
  LineChart,
  PieChart,
  Users,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  Eye,
  Brain,
  Calculator,
  Wallet,
  CreditCard,
  Banknote,
  Coins,
  PiggyBank,
  Building,
  Briefcase,
  FileText,
  Receipt,
  TrendingUpIcon,
  ArrowUp,
  ArrowDown,
  ArrowRight,
  ArrowLeft,
  Plus,
  Minus,
  X,
  Check,
  Info,
  Star,
  Shield,
  Lock,
  Unlock,
    Settings,  RefreshCw as Refresh,  Download,
  Upload,
  Filter,
  Search,
  Calendar,
  Globe,
  Radio,
  Wifi,
  WifiOff
} from 'lucide-react';

interface BettingOdds {
  bookmaker: string;
  gameId: string;
  homeTeam: string;
  awayTeam: string;
  homeOdds: number;
  awayOdds: number;
  overUnder: number;
  spread: number;
  homeSpreadOdds: number;
  awaySpreadOdds: number;
  lastUpdated: Date;
  volume: number;
  sharpMoney: 'home' | 'away' | 'neutral';
  publicMoney: 'home' | 'away' | 'neutral';
}

interface ContractData {
  playerId: string;
  playerName: string;
  team: string;
  currentSalary: number;
  contractYears: number;
  yearsRemaining: number;
  marketValue: number;
  predicted2025Value: number;
  contractType: 'rookie' | 'extension' | 'max' | 'mid-level' | 'minimum' | 'supermax';
  playerOption: boolean;
  teamOption: boolean;
  tradeKicker: boolean;
  noTradeClause: boolean;
  tradeProbability: number; // 0-100
  extensionLikelihood: number; // 0-100
  freeAgentStatus: 'RFA' | 'UFA' | 'N/A';
}

interface TradePrediction {
  id: string;
  probability: number; // 0-100
  confidence: number; // 0-100
  timeframe: '1 week' | '1 month' | '3 months' | 'trade deadline' | 'offseason';
  tradeType: 'blockbuster' | 'role player' | 'salary dump' | 'contender move' | 'rebuild';
  teams: string[];
  players: string[];
  assets: string[];
  description: string;
  reasoning: string;
  marketImpact: number; // -100 to 100
  salary_impact: number;
  luxury_tax_impact: number;
  competitive_impact: number;
  fanSentiment: number; // -100 to 100
  sources: string[];
  lastUpdated: Date;
}

interface MarketTrend {
  category: 'player_values' | 'team_values' | 'revenue' | 'salary_cap' | 'luxury_tax' | 'tickets' | 'merchandise';
  metric: string;
  currentValue: number;
  previousValue: number;
  changePercent: number;
  trend: 'up' | 'down' | 'stable';
  timeframe: string;
  confidence: number;
  factors: string[];
  impact: 'positive' | 'negative' | 'neutral';
}

interface FinancialAlert {
  id: string;
  type: 'trade_rumor' | 'contract_news' | 'odds_movement' | 'market_shift' | 'injury_impact' | 'insider_report';
  priority: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description: string;
  impact: string;
  confidence: number;
  timestamp: Date;
  source: string;
  relatedAssets: string[];
  actionable: boolean;
  moneyLine: number; // Expected financial impact
}

interface MarketIntelligenceProps {
  bettingOdds?: BettingOdds[];
  contracts?: ContractData[];
  tradePredictions?: TradePrediction[];
  marketTrends?: MarketTrend[];
  alerts?: FinancialAlert[];
  isLive?: boolean;
}

// Mock Data
const mockBettingOdds: BettingOdds[] = [
  {
    bookmaker: 'DraftKings',
    gameId: 'LAL-BOS-20241025',
    homeTeam: 'Lakers',
    awayTeam: 'Celtics',
    homeOdds: -110,
    awayOdds: -110,
    overUnder: 225.5,
    spread: -2.5,
    homeSpreadOdds: -105,
    awaySpreadOdds: -115,
    lastUpdated: new Date(),
    volume: 2500000,
    sharpMoney: 'away',
    publicMoney: 'home'
  },
  {
    bookmaker: 'FanDuel',
    gameId: 'LAL-BOS-20241025',
    homeTeam: 'Lakers',
    awayTeam: 'Celtics',
    homeOdds: -108,
    awayOdds: -112,
    overUnder: 226.0,
    spread: -2.0,
    homeSpreadOdds: -110,
    awaySpreadOdds: -110,
    lastUpdated: new Date(Date.now() - 30000),
    volume: 1800000,
    sharpMoney: 'away',
    publicMoney: 'home'
  }
];

const mockContracts: ContractData[] = [
  {
    playerId: 'lebron-james',
    playerName: 'LeBron James',
    team: 'Lakers',
    currentSalary: 47607360,
    contractYears: 2,
    yearsRemaining: 1,
    marketValue: 45000000,
    predicted2025Value: 40000000,
    contractType: 'max',
    playerOption: true,
    teamOption: false,
    tradeKicker: false,
    noTradeClause: true,
    tradeProbability: 15,
    extensionLikelihood: 75,
    freeAgentStatus: 'UFA'
  },
  {
    playerId: 'jayson-tatum',
    playerName: 'Jayson Tatum',
    team: 'Celtics',
    currentSalary: 34848340,
    contractYears: 5,
    yearsRemaining: 4,
    marketValue: 50000000,
    predicted2025Value: 55000000,
    contractType: 'supermax',
    playerOption: false,
    teamOption: false,
    tradeKicker: true,
    noTradeClause: false,
    tradeProbability: 8,
    extensionLikelihood: 95,
    freeAgentStatus: 'N/A'
  },
  {
    playerId: 'austin-reaves',
    playerName: 'Austin Reaves',
    team: 'Lakers',
    currentSalary: 12000000,
    contractYears: 4,
    yearsRemaining: 3,
    marketValue: 18000000,
    predicted2025Value: 22000000,
    contractType: 'extension',
    playerOption: false,
    teamOption: false,
    tradeKicker: false,
    noTradeClause: false,
    tradeProbability: 25,
    extensionLikelihood: 60,
    freeAgentStatus: 'N/A'
  }
];

const mockTradePredictions: TradePrediction[] = [
  {
    id: 'trade-001',
    probability: 78,
    confidence: 85,
    timeframe: 'trade deadline',
    tradeType: 'contender move',
    teams: ['Lakers', 'Bulls'],
    players: ['Zach LaVine', 'Austin Reaves', 'Rui Hachimura'],
    assets: ['2025 1st Round Pick', '2027 2nd Round Pick'],
    description: 'Lakers acquire Zach LaVine in exchange for young assets and picks',
    reasoning: 'Lakers need additional scoring, Bulls looking to rebuild around younger core',
    marketImpact: 35,
    salary_impact: 8500000,
    luxury_tax_impact: 12000000,
    competitive_impact: 25,
    fanSentiment: 42,
    sources: ['ESPN', 'The Athletic', 'Shams Charania'],
    lastUpdated: new Date(Date.now() - 3600000)
  },
  {
    id: 'trade-002',
    probability: 62,
    confidence: 72,
    timeframe: '1 month',
    tradeType: 'salary dump',
    teams: ['Celtics', 'Trail Blazers'],
    players: ['Malcolm Brogdon', 'Robert Williams III'],
    assets: ['2026 2nd Round Pick'],
    description: 'Celtics shed salary before luxury tax penalties increase',
    reasoning: 'Boston over luxury tax threshold, need to reduce payroll for repeater tax',
    marketImpact: -15,
    salary_impact: -22000000,
    luxury_tax_impact: -35000000,
    competitive_impact: -8,
    fanSentiment: -18,
    sources: ['Adrian Wojnarowski', 'Boston Globe'],
    lastUpdated: new Date(Date.now() - 7200000)
  }
];

const mockMarketTrends: MarketTrend[] = [
  {
    category: 'player_values',
    metric: 'Average Max Contract',
    currentValue: 48500000,
    previousValue: 46200000,
    changePercent: 4.98,
    trend: 'up',
    timeframe: 'YoY',
    confidence: 92,
    factors: ['New TV Deal', 'Rising Salary Cap', 'Player Empowerment'],
    impact: 'positive'
  },
  {
    category: 'team_values',
    metric: 'Average Franchise Value',
    currentValue: 3200000000,
    previousValue: 2980000000,
    changePercent: 7.38,
    trend: 'up',
    timeframe: 'YoY',
    confidence: 95,
    factors: ['New TV Deal', 'Global Expansion', 'Digital Revenue'],
    impact: 'positive'
  },
  {
    category: 'luxury_tax',
    metric: 'Luxury Tax Payments',
    currentValue: 483000000,
    previousValue: 352000000,
    changePercent: 37.22,
    trend: 'up',
    timeframe: 'Season',
    confidence: 88,
    factors: ['Higher Salary Cap', 'More Teams Over Tax', 'Repeater Penalties'],
    impact: 'negative'
  }
];

const mockAlerts: FinancialAlert[] = [
  {
    id: 'alert-001',
    type: 'odds_movement',
    priority: 'high',
    title: 'Significant Line Movement: Lakers vs Celtics',
    description: 'Lakers spread moved from -2.5 to -1.5 in last hour with heavy sharp action on Celtics',
    impact: '$2.3M in sharp money on Celtics',
    confidence: 91,
    timestamp: new Date(Date.now() - 1800000),
    source: 'Multiple Sportsbooks',
    relatedAssets: ['LAL', 'BOS'],
    actionable: true,
    moneyLine: 2300000
  },
  {
    id: 'alert-002',
    type: 'trade_rumor',
    priority: 'critical',
    title: 'Zach LaVine Trade Talks Intensifying',
    description: 'Multiple sources report Lakers and Bulls in advanced discussions for LaVine trade',
    impact: 'Potential $45M salary commitment',
    confidence: 78,
    timestamp: new Date(Date.now() - 3600000),
    source: 'Shams Charania',
    relatedAssets: ['LAL', 'CHI', 'Zach LaVine'],
    actionable: true,
    moneyLine: 45000000
  },
  {
    id: 'alert-003',
    type: 'contract_news',
    priority: 'medium',
    title: 'Jayson Tatum Extension Negotiations',
    description: 'Celtics and Tatum discussing supermax extension worth $315M over 5 years',
    impact: 'Luxury tax implications significant',
    confidence: 84,
    timestamp: new Date(Date.now() - 7200000),
    source: 'Adrian Wojnarowski',
    relatedAssets: ['BOS', 'Jayson Tatum'],
    actionable: false,
    moneyLine: 315000000
  }
];

export default function MarketIntelligenceDashboard({
  bettingOdds = mockBettingOdds,
  contracts = mockContracts,
  tradePredictions = mockTradePredictions,
  marketTrends = mockMarketTrends,
  alerts = mockAlerts,
  isLive = true
}: MarketIntelligenceProps) {
  const [selectedCategory, setSelectedCategory] = useState<'odds' | 'contracts' | 'trades' | 'trends' | 'alerts'>('odds');
  const [timeframe, setTimeframe] = useState<'1h' | '24h' | '7d' | '30d' | 'season'>('24h');
  const [filterTeam, setFilterTeam] = useState<string>('all');
  const [monitoringMode, setMonitoringMode] = useState(true);
  const [alertsEnabled, setAlertsEnabled] = useState(true);
  const [confidenceThreshold, setConfidenceThreshold] = useState([70]);
  const [impactThreshold, setImpactThreshold] = useState([1000000]);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showPredictions, setShowPredictions] = useState(true);

  // Get trend color
  const getTrendColor = (trend: string) => {
    switch (trend) {
      case 'up': return '#10b981';
      case 'down': return '#ef4444';
      case 'stable': return '#6b7280';
      default: return '#6b7280';
    }
  };

  // Get priority color
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return '#ef4444';
      case 'high': return '#f97316';
      case 'medium': return '#f59e0b';
      case 'low': return '#6b7280';
      default: return '#6b7280';
    }
  };

  // Format currency
  const formatCurrency = (amount: number) => {
    if (amount >= 1000000) {
      return `$${(amount / 1000000).toFixed(1)}M`;
    } else if (amount >= 1000) {
      return `$${(amount / 1000).toFixed(0)}K`;
    } else {
      return `$${amount.toFixed(0)}`;
    }
  };

  // Calculate total market exposure
  const totalMarketExposure = useMemo(() => {
    const contractExposure = contracts.reduce((sum, contract) => sum + contract.currentSalary, 0);
    const tradeExposure = tradePredictions.reduce((sum, trade) => sum + Math.abs(trade.salary_impact), 0);
    return contractExposure + tradeExposure;
  }, [contracts, tradePredictions]);

  // High confidence trades
  const highConfidenceTrades = tradePredictions.filter(trade => trade.confidence >= confidenceThreshold[0]);

  // Recent high-impact alerts
  const highImpactAlerts = alerts.filter(alert =>
    Math.abs(alert.moneyLine) >= impactThreshold[0] &&
    alert.timestamp > new Date(Date.now() - 24 * 60 * 60 * 1000)
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card className="border-2 border-green-500">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-xl font-bold flex items-center gap-3">
                <DollarSign className="w-6 h-6 text-green-500" />
                Predictive Market Intelligence Dashboard
                <Badge variant="outline" className="flex items-center gap-1">
                  <TrendingUp className="w-3 h-3" />
                  Live Markets
                </Badge>
              </h3>
              <div className="flex items-center gap-6 mt-2 text-sm text-muted-foreground">
                <span className="text-lg font-bold text-foreground">
                  {formatCurrency(totalMarketExposure)} Total Exposure
                </span>
                <span>{highConfidenceTrades.length} High-Confidence Trades</span>
                <span>{highImpactAlerts.length} Critical Alerts</span>
                <span>Monitoring: {monitoringMode ? 'Active' : 'Paused'}</span>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Badge
                variant={isLive ? 'default' : 'secondary'}
                className="flex items-center gap-1"
              >
                {isLive ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                {isLive ? 'Live Data' : 'Offline'}
              </Badge>

              <Button
                size="sm"
                variant={monitoringMode ? 'default' : 'outline'}
                onClick={() => setMonitoringMode(!monitoringMode)}
              >
                {monitoringMode ? <Eye className="w-4 h-4" /> : <Settings className="w-4 h-4" />}
                {monitoringMode ? 'Monitoring' : 'Configure'}
              </Button>

              <Button size="sm" variant="outline">
                <Download className="w-4 h-4" />
                Export
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-green-600">
              {formatCurrency(totalMarketExposure)}
            </div>
            <div className="text-sm text-muted-foreground">Market Exposure</div>
            <div className="text-xs text-blue-600 mt-1">{contracts.length} contracts tracked</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">{tradePredictions.length}</div>
            <div className="text-sm text-muted-foreground">Trade Predictions</div>
            <div className="text-xs text-green-600 mt-1">{highConfidenceTrades.length} high confidence</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-purple-600">{bettingOdds.length}</div>
            <div className="text-sm text-muted-foreground">Live Odds</div>
            <div className="text-xs text-orange-600 mt-1">
              {formatCurrency(bettingOdds.reduce((sum, odds) => sum + odds.volume, 0))} volume
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-orange-600">{marketTrends.length}</div>
            <div className="text-sm text-muted-foreground">Market Trends</div>
            <div className="text-xs text-green-600 mt-1">
              {marketTrends.filter(t => t.trend === 'up').length} trending up
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-red-600">{alerts.length}</div>
            <div className="text-sm text-muted-foreground">Active Alerts</div>
            <div className="text-xs text-red-600 mt-1">{highImpactAlerts.length} high impact</div>
          </CardContent>
        </Card>
      </div>

      {/* Main Tabs */}
      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-4 gap-1 p-1 h-auto">
          <TabsTrigger value="overview" className="flex-col h-16 text-xs p-1">
            <DollarSign className="w-4 h-4 mb-1" />
            Market Overview
          </TabsTrigger>
          <TabsTrigger value="trades" className="flex-col h-16 text-xs p-1">
            <Brain className="w-4 h-4 mb-1" />
            Trade Analysis
          </TabsTrigger>
          <TabsTrigger value="contracts" className="flex-col h-16 text-xs p-1">
            <FileText className="w-4 h-4 mb-1" />
            Contract Intel
          </TabsTrigger>
          <TabsTrigger value="odds" className="flex-col h-16 text-xs p-1">
            <Target className="w-4 h-4 mb-1" />
            Betting Markets
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          {/* Control Panel */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <h4 className="font-semibold flex items-center gap-2">
                  <Settings className="w-4 h-4" />
                  Market Intelligence Controls
                </h4>
              </div>
            </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="space-y-3">
              <div>
                <Label className="text-sm">Timeframe</Label>
                <Select value={timeframe} onValueChange={(value: any) => setTimeframe(value)}>
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1h">1 Hour</SelectItem>
                    <SelectItem value="24h">24 Hours</SelectItem>
                    <SelectItem value="7d">7 Days</SelectItem>
                    <SelectItem value="30d">30 Days</SelectItem>
                    <SelectItem value="season">Season</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <Label className="text-sm">Confidence Threshold: {confidenceThreshold[0]}%</Label>
                <Slider
                  value={confidenceThreshold}
                  onValueChange={setConfidenceThreshold}
                  min={50}
                  max={100}
                  step={5}
                  className="mt-2"
                />
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <Label className="text-sm">Impact Threshold: {formatCurrency(impactThreshold[0])}</Label>
                <Slider
                  value={impactThreshold}
                  onValueChange={setImpactThreshold}
                  min={100000}
                  max={50000000}
                  step={1000000}
                  className="mt-2"
                />
              </div>
            </div>

            <div className="space-y-3">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Auto Refresh</Label>
                  <Switch checked={autoRefresh} onCheckedChange={setAutoRefresh} />
                </div>
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Alerts</Label>
                  <Switch checked={alertsEnabled} onCheckedChange={setAlertsEnabled} />
                </div>
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Predictions</Label>
                  <Switch checked={showPredictions} onCheckedChange={setShowPredictions} />
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <Label className="text-sm">Search</Label>
                <div className="relative mt-1">
                  <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search markets..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-8"
                  />
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Critical Alerts */}
      {highImpactAlerts.length > 0 && alertsEnabled && (
        <Card className="border-2 border-red-500 bg-red-50">
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-3">
              <AlertTriangle className="w-5 h-5 text-red-500" />
              <h4 className="font-semibold text-red-800">Critical Market Alerts ({highImpactAlerts.length})</h4>
            </div>
            <div className="space-y-2">
              {highImpactAlerts.slice(0, 3).map(alert => (
                <div key={alert.id} className="bg-white p-3 rounded-lg border border-red-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-red-800">{alert.title}</span>
                    <div className="flex items-center gap-2">
                      <Badge
                        style={{ backgroundColor: getPriorityColor(alert.priority) }}
                        className="text-white text-xs"
                      >
                        {alert.priority}
                      </Badge>
                      <Badge variant="outline" className="text-xs">
                        {alert.confidence}% confidence
                      </Badge>
                    </div>
                  </div>
                  <p className="text-sm text-red-700 mb-2">{alert.description}</p>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-red-600">Impact: {alert.impact}</span>
                    <span className="text-gray-500">{alert.timestamp.toLocaleTimeString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Content Based on Selected Category */}
      {selectedCategory === 'odds' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <h4 className="font-semibold flex items-center gap-2">
                <Target className="w-4 h-4" />
                Live Betting Odds
              </h4>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {bettingOdds.map((odds, index) => (
                  <div key={index} className="p-4 border rounded-lg">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <div className="font-medium">{odds.awayTeam} @ {odds.homeTeam}</div>
                        <div className="text-sm text-muted-foreground">{odds.bookmaker}</div>
                      </div>
                      <Badge variant="outline">
                        {formatCurrency(odds.volume)} volume
                      </Badge>
                    </div>

                    <div className="grid grid-cols-3 gap-4 text-sm">
                      <div>
                        <div className="text-muted-foreground">Moneyline</div>
                        <div className="font-medium">
                          {odds.awayTeam}: {odds.awayOdds > 0 ? '+' : ''}{odds.awayOdds}
                        </div>
                        <div className="font-medium">
                          {odds.homeTeam}: {odds.homeOdds > 0 ? '+' : ''}{odds.homeOdds}
                        </div>
                      </div>
                      <div>
                        <div className="text-muted-foreground">Spread</div>
                        <div className="font-medium">
                          {odds.homeTeam} {odds.spread > 0 ? '+' : ''}{odds.spread}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          ({odds.homeSpreadOdds > 0 ? '+' : ''}{odds.homeSpreadOdds})
                        </div>
                      </div>
                      <div>
                        <div className="text-muted-foreground">O/U</div>
                        <div className="font-medium">{odds.overUnder}</div>
                        <div className="text-xs text-muted-foreground">
                          Last: {odds.lastUpdated.toLocaleTimeString()}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center justify-between mt-3 pt-3 border-t">
                      <div className="flex items-center gap-4 text-xs">
                        <div>
                          <span className="text-muted-foreground">Sharp Money:</span>
                          <span className="font-medium ml-1 capitalize">{odds.sharpMoney}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Public Money:</span>
                          <span className="font-medium ml-1 capitalize">{odds.publicMoney}</span>
                        </div>
                      </div>
                      <Badge variant={odds.sharpMoney !== odds.publicMoney ? 'destructive' : 'secondary'}>
                        {odds.sharpMoney !== odds.publicMoney ? 'Conflict' : 'Aligned'}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <h4 className="font-semibold flex items-center gap-2">
                <LineChart className="w-4 h-4" />
                Odds Movement Analysis
              </h4>
            </CardHeader>
            <CardContent>
              <div className="relative h-64 bg-gradient-to-br from-green-50 to-blue-50 rounded-lg p-4">
                <svg width="100%" height="100%" viewBox="0 0 400 200">
                  <defs>
                    <linearGradient id="oddsGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                      <stop offset="0%" style={{stopColor: '#10b981', stopOpacity: 0.8}} />
                      <stop offset="100%" style={{stopColor: '#3b82f6', stopOpacity: 0.8}} />
                    </linearGradient>
                  </defs>

                  {/* Grid lines */}
                  {[0, 1, 2, 3, 4].map(i => (
                    <line
                      key={i}
                      x1={50 + i * 75}
                      y1="20"
                      x2={50 + i * 75}
                      y2="180"
                      stroke="#e5e7eb"
                      strokeWidth="1"
                    />
                  ))}

                  {[-150, -110, -100, +100, +150].map((odds, index) => (
                    <line
                      key={odds}
                      x1="50"
                      y1={20 + index * 40}
                      x2="350"
                      y2={20 + index * 40}
                      stroke="#e5e7eb"
                      strokeWidth="1"
                    />
                  ))}

                  {/* Odds line */}
                  <path
                    d="M 50,100 L 125,95 L 200,105 L 275,90 L 350,95"
                    stroke="url(#oddsGradient)"
                    strokeWidth="3"
                    fill="none"
                    strokeLinecap="round"
                  />

                  {/* Data points */}
                  {[{x: 50, y: 100}, {x: 125, y: 95}, {x: 200, y: 105}, {x: 275, y: 90}, {x: 350, y: 95}].map((point, index) => (
                    <circle
                      key={index}
                      cx={point.x}
                      cy={point.y}
                      r="4"
                      fill="#10b981"
                      stroke="#ffffff"
                      strokeWidth="2"
                    />
                  ))}

                  {/* Labels */}
                  <text x="50" y="195" textAnchor="middle" className="text-xs fill-gray-600">12h ago</text>
                  <text x="125" y="195" textAnchor="middle" className="text-xs fill-gray-600">9h ago</text>
                  <text x="200" y="195" textAnchor="middle" className="text-xs fill-gray-600">6h ago</text>
                  <text x="275" y="195" textAnchor="middle" className="text-xs fill-gray-600">3h ago</text>
                  <text x="350" y="195" textAnchor="middle" className="text-xs fill-gray-600">Now</text>
                </svg>

                <div className="absolute top-4 right-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 text-xs">
                  <div className="font-medium mb-2">Lakers Spread Movement</div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                      <span>Opening: -2.5</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                      <span>Current: -2.0</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                      <span>Sharp: Celtics +2</span>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {selectedCategory === 'contracts' && (
        <Card>
          <CardHeader>
            <h4 className="font-semibold flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Contract Intelligence ({contracts.length})
            </h4>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {contracts.map(contract => (
                <div key={contract.playerId} className="p-4 border rounded-lg">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="font-medium">{contract.playerName}</div>
                      <div className="text-sm text-muted-foreground">{contract.team} • {contract.contractType}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-bold">{formatCurrency(contract.currentSalary)}</div>
                      <div className="text-sm text-muted-foreground">{contract.yearsRemaining} years left</div>
                    </div>
                  </div>

                  <div className="grid grid-cols-4 gap-4 text-sm mb-4">
                    <div>
                      <div className="text-muted-foreground">Market Value</div>
                      <div className="font-medium">{formatCurrency(contract.marketValue)}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">2025 Projection</div>
                      <div className="font-medium">{formatCurrency(contract.predicted2025Value)}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Trade Probability</div>
                      <div className="font-medium">{contract.tradeProbability}%</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Extension Likelihood</div>
                      <div className="font-medium">{contract.extensionLikelihood}%</div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex flex-wrap gap-2">
                      {contract.playerOption && <Badge variant="secondary">Player Option</Badge>}
                      {contract.teamOption && <Badge variant="secondary">Team Option</Badge>}
                      {contract.tradeKicker && <Badge variant="secondary">Trade Kicker</Badge>}
                      {contract.noTradeClause && <Badge variant="destructive">No Trade Clause</Badge>}
                      {contract.freeAgentStatus !== 'N/A' && (
                        <Badge variant="outline">{contract.freeAgentStatus}</Badge>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Progress value={contract.tradeProbability} className="w-16 h-2" />
                      <span className="text-xs text-muted-foreground">Trade Risk</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {selectedCategory === 'trades' && showPredictions && (
        <Card>
          <CardHeader>
            <h4 className="font-semibold flex items-center gap-2">
              <Brain className="w-4 h-4" />
              AI Trade Predictions ({tradePredictions.length})
            </h4>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {tradePredictions.map(trade => (
                <div key={trade.id} className="p-4 border rounded-lg">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="font-medium">{trade.description}</div>
                      <div className="text-sm text-muted-foreground capitalize">
                        {trade.tradeType} • {trade.timeframe}
                      </div>
                    </div>
                    <div className="text-right">
                      <Badge variant="outline" className="mb-1">{trade.probability}% probability</Badge>
                      <div className="text-sm text-muted-foreground">{trade.confidence}% confidence</div>
                    </div>
                  </div>

                  <div className="mb-3">
                    <div className="text-sm font-medium mb-2">Teams & Players:</div>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {trade.teams.map(team => (
                        <Badge key={team} variant="secondary">{team}</Badge>
                      ))}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {trade.players.map(player => (
                        <Badge key={player} variant="outline">{player}</Badge>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-4 gap-4 text-sm mb-3">
                    <div>
                      <div className="text-muted-foreground">Salary Impact</div>
                      <div className={`font-medium ${trade.salary_impact >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {trade.salary_impact >= 0 ? '+' : ''}{formatCurrency(trade.salary_impact)}
                      </div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Luxury Tax</div>
                      <div className={`font-medium ${trade.luxury_tax_impact >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {trade.luxury_tax_impact >= 0 ? '+' : ''}{formatCurrency(trade.luxury_tax_impact)}
                      </div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Market Impact</div>
                      <div className={`font-medium ${trade.marketImpact >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {trade.marketImpact >= 0 ? '+' : ''}{trade.marketImpact}%
                      </div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Fan Sentiment</div>
                      <div className={`font-medium ${trade.fanSentiment >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {trade.fanSentiment >= 0 ? '+' : ''}{trade.fanSentiment}%
                      </div>
                    </div>
                  </div>

                  <div className="text-sm text-muted-foreground mb-3">
                    <span className="font-medium">Reasoning:</span> {trade.reasoning}
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex flex-wrap gap-1 text-xs">
                      <span className="text-muted-foreground">Sources:</span>
                      {trade.sources.map(source => (
                        <Badge key={source} variant="outline" className="text-xs">{source}</Badge>
                      ))}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Updated: {trade.lastUpdated.toLocaleString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {selectedCategory === 'trends' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <h4 className="font-semibold flex items-center gap-2">
                <TrendingUp className="w-4 h-4" />
                Market Trends ({marketTrends.length})
              </h4>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {marketTrends.map((trend, index) => (
                  <div key={index} className="p-4 border rounded-lg">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <div className="font-medium">{trend.metric}</div>
                        <div className="text-sm text-muted-foreground capitalize">
                          {trend.category.replace('_', ' ')} • {trend.timeframe}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="flex items-center gap-2">
                          {trend.trend === 'up' ? (
                            <ArrowUp className="w-4 h-4 text-green-500" />
                          ) : trend.trend === 'down' ? (
                            <ArrowDown className="w-4 h-4 text-red-500" />
                          ) : (
                            <ArrowRight className="w-4 h-4 text-gray-500" />
                          )}
                          <span className={`font-bold ${
                            trend.changePercent > 0 ? 'text-green-600' :
                            trend.changePercent < 0 ? 'text-red-600' : 'text-gray-600'
                          }`}>
                            {trend.changePercent > 0 ? '+' : ''}{trend.changePercent.toFixed(2)}%
                          </span>
                        </div>
                        <div className="text-sm text-muted-foreground">{trend.confidence}% confidence</div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 text-sm mb-3">
                      <div>
                        <div className="text-muted-foreground">Current</div>
                        <div className="font-medium">{formatCurrency(trend.currentValue)}</div>
                      </div>
                      <div>
                        <div className="text-muted-foreground">Previous</div>
                        <div className="font-medium">{formatCurrency(trend.previousValue)}</div>
                      </div>
                    </div>

                    <div className="mb-3">
                      <div className="text-sm font-medium mb-2">Key Factors:</div>
                      <div className="flex flex-wrap gap-1">
                        {trend.factors.map(factor => (
                          <Badge key={factor} variant="secondary" className="text-xs">{factor}</Badge>
                        ))}
                      </div>
                    </div>

                    <div className="flex items-center justify-between">
                      <Badge variant={trend.impact === 'positive' ? 'default' : trend.impact === 'negative' ? 'destructive' : 'secondary'}>
                        {trend.impact} impact
                      </Badge>
                      <Progress value={trend.confidence} className="w-20 h-2" />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <h4 className="font-semibold flex items-center gap-2">
                <PieChart className="w-4 h-4" />
                Market Distribution
              </h4>
            </CardHeader>
            <CardContent>
              <div className="relative h-64 bg-gradient-to-br from-green-50 to-blue-50 rounded-lg p-4">
                <svg width="100%" height="100%" viewBox="0 0 300 200">
                  {/* Pie chart segments */}
                  <g transform="translate(150,100)">
                    {/* Player Values - 45% */}
                    <path
                      d="M 0,-60 A 60,60 0 0,1 42.4,42.4 L 0,0 Z"
                      fill="#10b981"
                      stroke="#ffffff"
                      strokeWidth="2"
                    />
                    {/* Team Values - 30% */}
                    <path
                      d="M 42.4,42.4 A 60,60 0 0,1 -18.5,56.4 L 0,0 Z"
                      fill="#3b82f6"
                      stroke="#ffffff"
                      strokeWidth="2"
                    />
                    {/* Contracts - 15% */}
                    <path
                      d="M -18.5,56.4 A 60,60 0 0,1 -58.8,-7.8 L 0,0 Z"
                      fill="#8b5cf6"
                      stroke="#ffffff"
                      strokeWidth="2"
                    />
                    {/* Other - 10% */}
                    <path
                      d="M -58.8,-7.8 A 60,60 0 0,1 0,-60 L 0,0 Z"
                      fill="#f59e0b"
                      stroke="#ffffff"
                      strokeWidth="2"
                    />
                  </g>
                </svg>

                <div className="absolute top-4 right-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 text-xs">
                  <div className="font-medium mb-2">Market Allocation</div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                      <span>Player Values (45%)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                      <span>Team Values (30%)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                      <span>Contracts (15%)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                      <span>Other (10%)</span>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
        </TabsContent>

        <TabsContent value="trades" className="space-y-6">
          <TradeAnalysis />
        </TabsContent>

        <TabsContent value="contracts" className="space-y-6">
          <Card>
            <CardHeader>
              <h4 className="font-semibold flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Contract Intelligence ({contracts.length})
              </h4>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {contracts.map(contract => (
                  <div key={contract.playerId} className="p-4 border rounded-lg">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <div className="font-medium">{contract.playerName}</div>
                        <div className="text-sm text-muted-foreground">{contract.team} • {contract.contractType}</div>
                      </div>
                      <div className="text-right">
                        <div className="font-bold">{formatCurrency(contract.currentSalary)}</div>
                        <div className="text-sm text-muted-foreground">{contract.yearsRemaining} years left</div>
                      </div>
                    </div>

                    <div className="grid grid-cols-4 gap-4 text-sm mb-4">
                      <div>
                        <div className="text-muted-foreground">Market Value</div>
                        <div className="font-medium">{formatCurrency(contract.marketValue)}</div>
                      </div>
                      <div>
                        <div className="text-muted-foreground">2025 Projection</div>
                        <div className="font-medium">{formatCurrency(contract.predicted2025Value)}</div>
                      </div>
                      <div>
                        <div className="text-muted-foreground">Trade Probability</div>
                        <div className="font-medium">{contract.tradeProbability}%</div>
                      </div>
                      <div>
                        <div className="text-muted-foreground">Extension Likelihood</div>
                        <div className="font-medium">{contract.extensionLikelihood}%</div>
                      </div>
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="flex flex-wrap gap-2">
                        {contract.playerOption && <Badge variant="secondary">Player Option</Badge>}
                        {contract.teamOption && <Badge variant="secondary">Team Option</Badge>}
                        {contract.tradeKicker && <Badge variant="secondary">Trade Kicker</Badge>}
                        {contract.noTradeClause && <Badge variant="destructive">No Trade Clause</Badge>}
                        {contract.freeAgentStatus !== 'N/A' && (
                          <Badge variant="outline">{contract.freeAgentStatus}</Badge>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <Progress value={contract.tradeProbability} className="w-16 h-2" />
                        <span className="text-xs text-muted-foreground">Trade Risk</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="odds" className="space-y-6">
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <h4 className="font-semibold flex items-center gap-2">
                  <Target className="w-4 h-4" />
                  Live Betting Odds
                </h4>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {bettingOdds.map((odds, index) => (
                    <div key={index} className="p-4 border rounded-lg">
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <div className="font-medium">{odds.awayTeam} @ {odds.homeTeam}</div>
                          <div className="text-sm text-muted-foreground">{odds.bookmaker}</div>
                        </div>
                        <Badge variant="outline">
                          {formatCurrency(odds.volume)} volume
                        </Badge>
                      </div>

                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                          <div className="text-muted-foreground">Moneyline</div>
                          <div className="font-medium">
                            {odds.awayTeam}: {odds.awayOdds > 0 ? '+' : ''}{odds.awayOdds}
                          </div>
                          <div className="font-medium">
                            {odds.homeTeam}: {odds.homeOdds > 0 ? '+' : ''}{odds.homeOdds}
                          </div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">Spread</div>
                          <div className="font-medium">
                            {odds.homeTeam} {odds.spread > 0 ? '+' : ''}{odds.spread}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            ({odds.homeSpreadOdds > 0 ? '+' : ''}{odds.homeSpreadOdds})
                          </div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">O/U</div>
                          <div className="font-medium">{odds.overUnder}</div>
                          <div className="text-xs text-muted-foreground">
                            Last: {odds.lastUpdated.toLocaleTimeString()}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center justify-between mt-3 pt-3 border-t">
                        <div className="flex items-center gap-4 text-xs">
                          <div>
                            <span className="text-muted-foreground">Sharp Money:</span>
                            <span className="font-medium ml-1 capitalize">{odds.sharpMoney}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Public Money:</span>
                            <span className="font-medium ml-1 capitalize">{odds.publicMoney}</span>
                          </div>
                        </div>
                        <Badge variant={odds.sharpMoney !== odds.publicMoney ? 'destructive' : 'secondary'}>
                          {odds.sharpMoney !== odds.publicMoney ? 'Conflict' : 'Aligned'}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <h4 className="font-semibold flex items-center gap-2">
                  <LineChart className="w-4 h-4" />
                  Odds Movement Analysis
                </h4>
              </CardHeader>
              <CardContent>
                <div className="text-center py-8">
                  <Target className="w-12 h-12 mx-auto mb-4 text-blue-500" />
                  <h3 className="text-lg font-semibold mb-2">Odds Movement Chart</h3>
                  <p className="text-muted-foreground">
                    Real-time odds movement visualization coming soon...
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}