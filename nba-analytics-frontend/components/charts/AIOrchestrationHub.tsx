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
import { Textarea } from '@/components/ui/textarea';
import { 
  Brain, 
  Cpu, 
  Network,
  Zap,
  Eye,
  Target,
  TrendingUp,
  Activity,
  Users,
  BarChart3,
  LineChart,
  PieChart,
  Bot,
  Cog,
  Layers,
  GitBranch,
  Workflow,
  MessageSquare,
  AlertTriangle,
  CheckCircle,
  Clock,
  Play,
  Pause,
  RotateCcw,
  Settings,
  Monitor,
  Database,
  Cloud,
  Wifi,
  WifiOff,
  Lightbulb,
  Rocket,
  Shield,
  Lock,
  Unlock,
  ArrowRight,
  ArrowDown,
  ArrowUp,
  Plus,
  Minus,
  X,
    Check,  Info,  AlertTriangle as Warning,  XCircle as Error,  CheckCircle as Success
} from 'lucide-react';

interface AIAgent {
  id: string;
  name: string;
  type: 'analytics' | 'prediction' | 'strategy' | 'monitoring' | 'optimization' | 'research';
  status: 'active' | 'idle' | 'processing' | 'error' | 'offline';
  priority: 'low' | 'medium' | 'high' | 'critical';
  capabilities: string[];
  currentTask: string;
  performance: number; // 0-100
  confidence: number; // 0-100
  processingPower: number; // 0-100
  memoryUsage: number; // 0-100
  lastUpdate: Date;
  totalTasks: number;
  successRate: number; // 0-100
  averageResponseTime: number; // milliseconds
  specialization: string;
  learningRate: number; // 0-100
}

interface AgentTask {
  id: string;
  agentId: string;
  title: string;
  description: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: number; // 0-100
  startTime: Date;
  estimatedCompletion: Date;
  actualCompletion?: Date;
  dependencies: string[];
  output?: any;
  confidence: number;
  requiredResources: string[];
}

interface AgentCommunication {
  id: string;
  fromAgent: string;
  toAgent: string;
  messageType: 'data' | 'request' | 'result' | 'alert' | 'coordination';
  content: string;
  timestamp: Date;
  priority: 'low' | 'medium' | 'high' | 'critical';
  requiresResponse: boolean;
  processed: boolean;
}

interface SystemMetrics {
  totalAgents: number;
  activeAgents: number;
  totalTasks: number;
  completedTasks: number;
  failedTasks: number;
  averagePerformance: number;
  systemLoad: number;
  memoryUsage: number;
  networkLatency: number;
  uptime: number;
  throughput: number; // tasks per minute
  errorRate: number; // percentage
  coordinationEfficiency: number; // 0-100
}

interface OrchestrationProps {
  agents?: AIAgent[];
  tasks?: AgentTask[];
  communications?: AgentCommunication[];
  systemMetrics?: SystemMetrics;
  autoMode?: boolean;
}

// Mock AI Agents
const mockAgents: AIAgent[] = [
  {
    id: 'analytics-core',
    name: 'Analytics Core',
    type: 'analytics',
    status: 'active',
    priority: 'critical',
    capabilities: ['Statistical Analysis', 'Performance Metrics', 'Trend Analysis', 'Pattern Recognition'],
    currentTask: 'Processing Lakers vs Celtics advanced metrics',
    performance: 94,
    confidence: 88,
    processingPower: 87,
    memoryUsage: 65,
    lastUpdate: new Date(),
    totalTasks: 2847,
    successRate: 96.2,
    averageResponseTime: 245,
    specialization: 'Real-time game analysis and advanced statistics',
    learningRate: 85
  },
  {
    id: 'prediction-engine',
    name: 'Prediction Engine',
    type: 'prediction',
    status: 'processing',
    priority: 'high',
    capabilities: ['Game Outcomes', 'Player Performance', 'Injury Risk', 'Market Predictions'],
    currentTask: 'Generating playoff bracket predictions',
    performance: 91,
    confidence: 92,
    processingPower: 95,
    memoryUsage: 78,
    lastUpdate: new Date(Date.now() - 30000),
    totalTasks: 1823,
    successRate: 89.7,
    averageResponseTime: 1850,
    specialization: 'Machine learning predictions and forecasting',
    learningRate: 92
  },
  {
    id: 'strategy-advisor',
    name: 'Strategy Advisor',
    type: 'strategy',
    status: 'active',
    priority: 'high',
    capabilities: ['Game Strategy', 'Lineup Optimization', 'Coaching Insights', 'Tactical Analysis'],
    currentTask: 'Optimizing rotation patterns for 4th quarter',
    performance: 89,
    confidence: 86,
    processingPower: 82,
    memoryUsage: 58,
    lastUpdate: new Date(Date.now() - 15000),
    totalTasks: 1456,
    successRate: 91.3,
    averageResponseTime: 680,
    specialization: 'Strategic decision making and tactical optimization',
    learningRate: 78
  },
  {
    id: 'player-monitor',
    name: 'Player Monitor',
    type: 'monitoring',
    status: 'active',
    priority: 'medium',
    capabilities: ['Health Tracking', 'Fatigue Analysis', 'Performance Monitoring', 'Biometric Analysis'],
    currentTask: 'Monitoring LeBron James fatigue levels',
    performance: 87,
    confidence: 94,
    processingPower: 72,
    memoryUsage: 45,
    lastUpdate: new Date(Date.now() - 5000),
    totalTasks: 3621,
    successRate: 97.8,
    averageResponseTime: 125,
    specialization: 'Real-time player health and performance monitoring',
    learningRate: 88
  },
  {
    id: 'market-intelligence',
    name: 'Market Intelligence',
    type: 'research',
    status: 'idle',
    priority: 'medium',
    capabilities: ['Trade Analysis', 'Contract Valuations', 'Market Trends', 'Salary Cap Planning'],
    currentTask: 'Analyzing potential trade scenarios',
    performance: 85,
    confidence: 81,
    processingPower: 68,
    memoryUsage: 52,
    lastUpdate: new Date(Date.now() - 120000),
    totalTasks: 892,
    successRate: 88.4,
    averageResponseTime: 2140,
    specialization: 'NBA market analysis and financial modeling',
    learningRate: 74
  },
  {
    id: 'optimization-engine',
    name: 'Optimization Engine',
    type: 'optimization',
    status: 'processing',
    priority: 'high',
    capabilities: ['Resource Allocation', 'Performance Optimization', 'Efficiency Analysis', 'System Tuning'],
    currentTask: 'Optimizing agent coordination protocols',
    performance: 93,
    confidence: 89,
    processingPower: 91,
    memoryUsage: 71,
    lastUpdate: new Date(Date.now() - 8000),
    totalTasks: 1247,
    successRate: 94.1,
    averageResponseTime: 890,
    specialization: 'System optimization and efficiency enhancement',
    learningRate: 91
  }
];

const mockTasks: AgentTask[] = [
  {
    id: 'task-001',
    agentId: 'analytics-core',
    title: 'Real-time Game Analysis',
    description: 'Analyze live Lakers vs Celtics game data and provide insights',
    priority: 'critical',
    status: 'processing',
    progress: 75,
    startTime: new Date(Date.now() - 300000),
    estimatedCompletion: new Date(Date.now() + 60000),
    dependencies: [],
    confidence: 94,
    requiredResources: ['Game Feed', 'Player Tracking', 'Historical Data']
  },
  {
    id: 'task-002',
    agentId: 'prediction-engine',
    title: 'Playoff Bracket Prediction',
    description: 'Generate comprehensive playoff bracket predictions with probability analysis',
    priority: 'high',
    status: 'processing',
    progress: 45,
    startTime: new Date(Date.now() - 900000),
    estimatedCompletion: new Date(Date.now() + 600000),
    dependencies: ['task-001'],
    confidence: 87,
    requiredResources: ['Season Data', 'Team Analytics', 'Injury Reports']
  },
  {
    id: 'task-003',
    agentId: 'strategy-advisor',
    title: 'Lineup Optimization',
    description: 'Optimize 4th quarter lineup based on current game state',
    priority: 'high',
    status: 'queued',
    progress: 0,
    startTime: new Date(Date.now() + 120000),
    estimatedCompletion: new Date(Date.now() + 480000),
    dependencies: ['task-001'],
    confidence: 85,
    requiredResources: ['Player Metrics', 'Matchup Data', 'Fatigue Analysis']
  },
  {
    id: 'task-004',
    agentId: 'player-monitor',
    title: 'Fatigue Assessment',
    description: 'Monitor all active players for fatigue and injury risk',
    priority: 'medium',
    status: 'processing',
    progress: 88,
    startTime: new Date(Date.now() - 180000),
    estimatedCompletion: new Date(Date.now() + 30000),
    dependencies: [],
    confidence: 96,
    requiredResources: ['Biometric Data', 'Movement Tracking', 'Historical Load']
  },
  {
    id: 'task-005',
    agentId: 'optimization-engine',
    title: 'System Coordination',
    description: 'Optimize agent communication and task distribution',
    priority: 'high',
    status: 'processing',
    progress: 62,
    startTime: new Date(Date.now() - 240000),
    estimatedCompletion: new Date(Date.now() + 180000),
    dependencies: [],
    confidence: 91,
    requiredResources: ['System Metrics', 'Agent Performance', 'Network Status']
  }
];

const mockCommunications: AgentCommunication[] = [
  {
    id: 'comm-001',
    fromAgent: 'analytics-core',
    toAgent: 'strategy-advisor',
    messageType: 'data',
    content: 'Current momentum favors Celtics (+18 over last 5 minutes). Lakers struggling with paint defense.',
    timestamp: new Date(Date.now() - 30000),
    priority: 'high',
    requiresResponse: true,
    processed: false
  },
  {
    id: 'comm-002',
    fromAgent: 'player-monitor',
    toAgent: 'strategy-advisor',
    messageType: 'alert',
    content: 'LeBron James showing elevated fatigue (72%). Consider rest period.',
    timestamp: new Date(Date.now() - 45000),
    priority: 'critical',
    requiresResponse: true,
    processed: true
  },
  {
    id: 'comm-003',
    fromAgent: 'prediction-engine',
    toAgent: 'analytics-core',
    messageType: 'request',
    content: 'Need latest efficiency ratings for Eastern Conference teams.',
    timestamp: new Date(Date.now() - 120000),
    priority: 'medium',
    requiresResponse: false,
    processed: true
  },
  {
    id: 'comm-004',
    fromAgent: 'optimization-engine',
    toAgent: 'all',
    messageType: 'coordination',
    content: 'Initiating load balancing protocol. Redistributing tasks for optimal performance.',
    timestamp: new Date(Date.now() - 60000),
    priority: 'low',
    requiresResponse: false,
    processed: true
  }
];

const mockSystemMetrics: SystemMetrics = {
  totalAgents: 6,
  activeAgents: 5,
  totalTasks: 247,
  completedTasks: 231,
  failedTasks: 3,
  averagePerformance: 89.7,
  systemLoad: 73.2,
  memoryUsage: 61.5,
  networkLatency: 12,
  uptime: 99.7,
  throughput: 45.8,
  errorRate: 1.2,
  coordinationEfficiency: 94.3
};

export default function AIOrchestrationHub({
  agents = mockAgents,
  tasks = mockTasks,
  communications = mockCommunications,
  systemMetrics = mockSystemMetrics,
  autoMode = true
}: OrchestrationProps) {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const [orchestrationMode, setOrchestrationMode] = useState<'auto' | 'manual' | 'hybrid'>('auto');
  const [systemStatus, setSystemStatus] = useState<'optimal' | 'warning' | 'critical'>('optimal');
  const [showCommunications, setShowCommunications] = useState(true);
  const [filterAgentType, setFilterAgentType] = useState<string>('all');
  const [autoOptimize, setAutoOptimize] = useState(true);
  const [realTimeMode, setRealTimeMode] = useState(true);
  const [debugMode, setDebugMode] = useState(false);
  const [alertThreshold, setAlertThreshold] = useState([80]);
  const [maxConcurrentTasks, setMaxConcurrentTasks] = useState([10]);
  const [newTaskInput, setNewTaskInput] = useState('');
  const [commandInput, setCommandInput] = useState('');

  // Get agent status color
  const getAgentStatusColor = (status: string) => {
    switch (status) {
      case 'active': return '#10b981';
      case 'processing': return '#3b82f6';
      case 'idle': return '#6b7280';
      case 'error': return '#ef4444';
      case 'offline': return '#374151';
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

  // Get agent type icon
  const getAgentTypeIcon = (type: string) => {
    switch (type) {
      case 'analytics': return BarChart3;
      case 'prediction': return TrendingUp;
      case 'strategy': return Target;
      case 'monitoring': return Eye;
      case 'optimization': return Cog;
      case 'research': return Lightbulb;
      default: return Bot;
    }
  };

  // Filter agents by type
  const filteredAgents = useMemo(() => {
    if (filterAgentType === 'all') return agents;
    return agents.filter(agent => agent.type === filterAgentType);
  }, [agents, filterAgentType]);

  // Calculate system health
  const systemHealth = useMemo(() => {
    const performance = systemMetrics.averagePerformance;
    const uptime = systemMetrics.uptime;
    const errorRate = 100 - systemMetrics.errorRate;
    const efficiency = systemMetrics.coordinationEfficiency;
    
    return (performance + uptime + errorRate + efficiency) / 4;
  }, [systemMetrics]);

  // Get recent communications
  const recentCommunications = useMemo(() => {
    return communications
      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
      .slice(0, 10);
  }, [communications]);

  // Active tasks count
  const activeTasks = tasks.filter(task => task.status === 'processing').length;
  const queuedTasks = tasks.filter(task => task.status === 'queued').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card className="border-2 border-blue-500">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-xl font-bold flex items-center gap-3">
                <Network className="w-6 h-6 text-blue-500" />
                Multi-Agent AI Orchestration Hub
                <Badge variant="outline" className="flex items-center gap-1">
                  <Rocket className="w-3 h-3" />
                  Advanced AI
                </Badge>
              </h3>
              <div className="flex items-center gap-6 mt-2 text-sm text-muted-foreground">
                <span className="text-lg font-bold text-foreground">
                  {systemMetrics.activeAgents}/{systemMetrics.totalAgents} Agents Active
                </span>
                <span>Mode: {orchestrationMode.toUpperCase()}</span>
                <span>System Health: {systemHealth.toFixed(1)}%</span>
                <span>Throughput: {systemMetrics.throughput} tasks/min</span>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <Badge 
                variant={systemHealth > 90 ? 'default' : systemHealth > 70 ? 'secondary' : 'destructive'}
                className="flex items-center gap-1"
              >
                {systemHealth > 90 ? <CheckCircle className="w-3 h-3" /> : 
                 systemHealth > 70 ? <AlertTriangle className="w-3 h-3" /> : 
                 <X className="w-3 h-3" />}
                {systemHealth > 90 ? 'Optimal' : systemHealth > 70 ? 'Warning' : 'Critical'}
              </Badge>
              
              <Button
                size="sm"
                variant={realTimeMode ? 'default' : 'outline'}
                onClick={() => setRealTimeMode(!realTimeMode)}
              >
                {realTimeMode ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
                {realTimeMode ? 'Live' : 'Paused'}
              </Button>
              
              <Button size="sm" variant="outline">
                <Settings className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* System Overview Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-6 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">{systemMetrics.totalAgents}</div>
            <div className="text-sm text-muted-foreground">Total Agents</div>
            <div className="text-xs text-green-600 mt-1">{systemMetrics.activeAgents} active</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-green-600">{activeTasks}</div>
            <div className="text-sm text-muted-foreground">Active Tasks</div>
            <div className="text-xs text-yellow-600 mt-1">{queuedTasks} queued</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-purple-600">{systemMetrics.averagePerformance.toFixed(1)}%</div>
            <div className="text-sm text-muted-foreground">Performance</div>
            <div className="text-xs text-blue-600 mt-1">{systemMetrics.coordinationEfficiency.toFixed(1)}% efficiency</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-orange-600">{systemMetrics.systemLoad.toFixed(1)}%</div>
            <div className="text-sm text-muted-foreground">System Load</div>
            <div className="text-xs text-gray-600 mt-1">{systemMetrics.memoryUsage.toFixed(1)}% memory</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-red-600">{systemMetrics.errorRate.toFixed(1)}%</div>
            <div className="text-sm text-muted-foreground">Error Rate</div>
            <div className="text-xs text-green-600 mt-1">{systemMetrics.uptime.toFixed(1)}% uptime</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-indigo-600">{systemMetrics.networkLatency}ms</div>
            <div className="text-sm text-muted-foreground">Network Latency</div>
            <div className="text-xs text-blue-600 mt-1">{systemMetrics.throughput.toFixed(1)} tasks/min</div>
          </CardContent>
        </Card>
      </div>

      {/* Main Orchestration Interface */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Agent Management Panel */}
        <Card className="xl:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <h4 className="font-semibold flex items-center gap-2">
                <Bot className="w-4 h-4" />
                AI Agent Network ({filteredAgents.length})
              </h4>
              <div className="flex items-center gap-2">
                <Select value={filterAgentType} onValueChange={setFilterAgentType}>
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="analytics">Analytics</SelectItem>
                    <SelectItem value="prediction">Prediction</SelectItem>
                    <SelectItem value="strategy">Strategy</SelectItem>
                    <SelectItem value="monitoring">Monitoring</SelectItem>
                    <SelectItem value="optimization">Optimization</SelectItem>
                    <SelectItem value="research">Research</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {filteredAgents.map(agent => {
                const AgentIcon = getAgentTypeIcon(agent.type);
                return (
                  <div 
                    key={agent.id} 
                    className={`p-4 border rounded-lg cursor-pointer transition-all ${
                      selectedAgent === agent.id ? 'border-blue-500 bg-blue-50' : 'hover:bg-gray-50'
                    }`}
                    onClick={() => setSelectedAgent(selectedAgent === agent.id ? null : agent.id)}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="relative">
                          <AgentIcon className="w-8 h-8 text-gray-600" />
                          <div 
                            className="absolute -bottom-1 -right-1 w-3 h-3 rounded-full border-2 border-white"
                            style={{ backgroundColor: getAgentStatusColor(agent.status) }}
                          />
                        </div>
                        <div>
                          <div className="font-medium">{agent.name}</div>
                          <div className="text-xs text-muted-foreground capitalize">
                            {agent.type} • {agent.status}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge 
                          style={{ backgroundColor: getPriorityColor(agent.priority) }}
                          className="text-white text-xs"
                        >
                          {agent.priority}
                        </Badge>
                        <Badge variant="outline" className="text-xs">
                          {agent.performance}% perf
                        </Badge>
                      </div>
                    </div>
                    
                    <div className="text-sm text-muted-foreground mb-3">
                      Current: {agent.currentTask}
                    </div>
                    
                    <div className="grid grid-cols-3 gap-3 mb-3">
                      <div>
                        <div className="text-xs text-muted-foreground">Processing</div>
                        <Progress value={agent.processingPower} className="h-1 mt-1" />
                        <div className="text-xs font-medium mt-1">{agent.processingPower}%</div>
                      </div>
                      <div>
                        <div className="text-xs text-muted-foreground">Memory</div>
                        <Progress value={agent.memoryUsage} className="h-1 mt-1" />
                        <div className="text-xs font-medium mt-1">{agent.memoryUsage}%</div>
                      </div>
                      <div>
                        <div className="text-xs text-muted-foreground">Confidence</div>
                        <Progress value={agent.confidence} className="h-1 mt-1" />
                        <div className="text-xs font-medium mt-1">{agent.confidence}%</div>
                      </div>
                    </div>
                    
                    {selectedAgent === agent.id && (
                      <div className="mt-4 pt-4 border-t">
                        <div className="grid grid-cols-2 gap-4 text-xs">
                          <div>
                            <div className="text-muted-foreground">Specialization:</div>
                            <div className="font-medium">{agent.specialization}</div>
                          </div>
                          <div>
                            <div className="text-muted-foreground">Learning Rate:</div>
                            <div className="font-medium">{agent.learningRate}%</div>
                          </div>
                          <div>
                            <div className="text-muted-foreground">Total Tasks:</div>
                            <div className="font-medium">{agent.totalTasks}</div>
                          </div>
                          <div>
                            <div className="text-muted-foreground">Success Rate:</div>
                            <div className="font-medium">{agent.successRate}%</div>
                          </div>
                          <div>
                            <div className="text-muted-foreground">Avg Response:</div>
                            <div className="font-medium">{agent.averageResponseTime}ms</div>
                          </div>
                          <div>
                            <div className="text-muted-foreground">Last Update:</div>
                            <div className="font-medium">{agent.lastUpdate.toLocaleTimeString()}</div>
                          </div>
                        </div>
                        
                        <div className="mt-3">
                          <div className="text-xs text-muted-foreground mb-2">Capabilities:</div>
                          <div className="flex flex-wrap gap-1">
                            {agent.capabilities.map(capability => (
                              <Badge key={capability} variant="secondary" className="text-xs">
                                {capability}
                              </Badge>
                            ))}
                          </div>
                        </div>
                        
                        <div className="flex gap-2 mt-4">
                          <Button size="sm" variant="outline" className="text-xs">
                            <Pause className="w-3 h-3 mr-1" />
                            Pause
                          </Button>
                          <Button size="sm" variant="outline" className="text-xs">
                            <Settings className="w-3 h-3 mr-1" />
                            Configure
                          </Button>
                          <Button size="sm" variant="outline" className="text-xs">
                            <BarChart3 className="w-3 h-3 mr-1" />
                            Analytics
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Task Queue & Communications */}
        <div className="space-y-6">
          {/* Active Tasks */}
          <Card>
            <CardHeader>
              <h4 className="font-semibold flex items-center gap-2">
                <Activity className="w-4 h-4" />
                Task Queue ({tasks.length})
              </h4>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 max-h-64 overflow-y-auto">
                {tasks.slice(0, 5).map(task => (
                  <div 
                    key={task.id} 
                    className={`p-3 border rounded-lg cursor-pointer transition-all ${
                      selectedTask === task.id ? 'border-blue-500 bg-blue-50' : 'hover:bg-gray-50'
                    }`}
                    onClick={() => setSelectedTask(selectedTask === task.id ? null : task.id)}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-sm">{task.title}</span>
                      <Badge 
                        variant={task.status === 'processing' ? 'default' : 
                               task.status === 'completed' ? 'secondary' : 'outline'}
                        className="text-xs"
                      >
                        {task.status}
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground mb-2">
                      Agent: {agents.find(a => a.id === task.agentId)?.name}
                    </div>
                    <div className="flex items-center justify-between">
                      <Progress value={task.progress} className="h-2 flex-1 mr-2" />
                      <span className="text-xs font-medium">{task.progress}%</span>
                    </div>
                    {selectedTask === task.id && (
                      <div className="mt-3 pt-3 border-t text-xs">
                        <div className="text-muted-foreground mb-1">Description:</div>
                        <div className="mb-2">{task.description}</div>
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <span className="text-muted-foreground">Priority:</span>
                            <span className="font-medium ml-1">{task.priority}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Confidence:</span>
                            <span className="font-medium ml-1">{task.confidence}%</span>
                          </div>
                        </div>
                        <div className="mt-2">
                          <span className="text-muted-foreground">ETA:</span>
                          <span className="font-medium ml-1">
                            {task.estimatedCompletion.toLocaleTimeString()}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Inter-Agent Communications */}
          {showCommunications && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold flex items-center gap-2">
                    <MessageSquare className="w-4 h-4" />
                    Agent Communications
                  </h4>
                  <Badge variant="outline">{recentCommunications.length} recent</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {recentCommunications.map(comm => (
                    <div key={comm.id} className="p-2 border rounded text-xs">
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-1">
                          <ArrowRight className="w-3 h-3 text-blue-500" />
                          <span className="font-medium">
                            {agents.find(a => a.id === comm.fromAgent)?.name || comm.fromAgent}
                          </span>
                          <ArrowRight className="w-3 h-3 text-gray-400" />
                          <span className="text-muted-foreground">
                            {agents.find(a => a.id === comm.toAgent)?.name || comm.toAgent}
                          </span>
                        </div>
                        <Badge 
                          style={{ backgroundColor: getPriorityColor(comm.priority) }}
                          className="text-white text-xs"
                        >
                          {comm.messageType}
                        </Badge>
                      </div>
                      <div className="text-muted-foreground mb-1">{comm.content}</div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500">{comm.timestamp.toLocaleTimeString()}</span>
                        <div className="flex items-center gap-1">
                          {comm.requiresResponse && <Clock className="w-3 h-3 text-orange-500" />}
                          {comm.processed && <CheckCircle className="w-3 h-3 text-green-500" />}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Control Panel */}
      <Card>
        <CardHeader>
          <h4 className="font-semibold flex items-center gap-2">
            <Workflow className="w-4 h-4" />
            Orchestration Control Panel
          </h4>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="space-y-4">
              <div>
                <Label className="text-sm font-medium">Orchestration Mode</Label>
                <Select value={orchestrationMode} onValueChange={(value: any) => setOrchestrationMode(value)}>
                  <SelectTrigger className="mt-2">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">Automatic</SelectItem>
                    <SelectItem value="manual">Manual</SelectItem>
                    <SelectItem value="hybrid">Hybrid</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Auto Optimization</Label>
                  <Switch checked={autoOptimize} onCheckedChange={setAutoOptimize} />
                </div>
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Real-time Mode</Label>
                  <Switch checked={realTimeMode} onCheckedChange={setRealTimeMode} />
                </div>
                <div className="flex items-center justify-between">
                  <Label className="text-sm">Debug Mode</Label>
                  <Switch checked={debugMode} onCheckedChange={setDebugMode} />
                </div>
              </div>
            </div>
            
            <div className="space-y-4">
              <div>
                <Label className="text-sm">Alert Threshold: {alertThreshold[0]}%</Label>
                <Slider
                  value={alertThreshold}
                  onValueChange={setAlertThreshold}
                  min={50}
                  max={100}
                  step={5}
                  className="mt-2"
                />
              </div>
              <div>
                <Label className="text-sm">Max Concurrent Tasks: {maxConcurrentTasks[0]}</Label>
                <Slider
                  value={maxConcurrentTasks}
                  onValueChange={setMaxConcurrentTasks}
                  min={5}
                  max={25}
                  step={1}
                  className="mt-2"
                />
              </div>
            </div>
            
            <div className="space-y-4">
              <div>
                <Label className="text-sm font-medium">Quick Actions</Label>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  <Button size="sm" variant="outline">
                    <Play className="w-3 h-3 mr-1" />
                    Start All
                  </Button>
                  <Button size="sm" variant="outline">
                    <Pause className="w-3 h-3 mr-1" />
                    Pause All
                  </Button>
                  <Button size="sm" variant="outline">
                    <RotateCcw className="w-3 h-3 mr-1" />
                    Restart
                  </Button>
                  <Button size="sm" variant="outline">
                    <Cog className="w-3 h-3 mr-1" />
                    Optimize
                  </Button>
                </div>
              </div>
            </div>
            
            <div className="space-y-4">
              <div>
                <Label className="text-sm font-medium">System Commands</Label>
                <Textarea
                  value={commandInput}
                  onChange={(e) => setCommandInput(e.target.value)}
                  placeholder="Enter system command..."
                  className="mt-2 h-20 text-xs"
                />
                <Button size="sm" className="mt-2 w-full">
                  <Play className="w-3 h-3 mr-1" />
                  Execute
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Network Visualization */}
      <Card>
        <CardHeader>
          <h4 className="font-semibold flex items-center gap-2">
            <GitBranch className="w-4 h-4" />
            Agent Network Visualization
          </h4>
        </CardHeader>
        <CardContent>
          <div className="relative h-64 bg-gradient-to-br from-blue-50 to-purple-50 rounded-lg p-4">
            <svg width="100%" height="100%" viewBox="0 0 600 200">
              {/* Network connections */}
              <defs>
                <linearGradient id="networkGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" style={{stopColor: '#3b82f6', stopOpacity: 0.6}} />
                  <stop offset="100%" style={{stopColor: '#8b5cf6', stopOpacity: 0.6}} />
                </linearGradient>
              </defs>
              
              {/* Draw connections between agents */}
              {agents.map((agent, index) => {
                const x = 100 + (index % 3) * 200;
                const y = 50 + Math.floor(index / 3) * 100;
                
                return (
                  <g key={agent.id}>
                    {/* Agent node */}
                    <circle
                      cx={x}
                      cy={y}
                      r="20"
                      fill={getAgentStatusColor(agent.status)}
                      stroke="#ffffff"
                      strokeWidth="3"
                      className="cursor-pointer"
                    />
                    
                    {/* Agent label */}
                    <text
                      x={x}
                      y={y + 35}
                      textAnchor="middle"
                      className="text-xs font-medium fill-gray-700"
                    >
                      {agent.name.split(' ')[0]}
                    </text>
                    
                    {/* Performance indicator */}
                    <text
                      x={x}
                      y={y + 5}
                      textAnchor="middle"
                      className="text-xs font-bold fill-white"
                    >
                      {agent.performance}%
                    </text>
                    
                    {/* Connect to other agents */}
                    {index < agents.length - 1 && (
                      <line
                        x1={x}
                        y1={y}
                        x2={100 + ((index + 1) % 3) * 200}
                        y2={50 + Math.floor((index + 1) / 3) * 100}
                        stroke="url(#networkGradient)"
                        strokeWidth="2"
                        strokeDasharray="5,5"
                        opacity="0.7"
                      />
                    )}
                  </g>
                );
              })}
              
              {/* Central orchestrator */}
              <circle
                cx="300"
                cy="100"
                r="15"
                fill="#8b5cf6"
                stroke="#ffffff"
                strokeWidth="2"
              />
              <text
                x="300"
                y="105"
                textAnchor="middle"
                className="text-xs font-bold fill-white"
              >
                HUB
              </text>
            </svg>
            
            {/* Network status overlay */}
            <div className="absolute top-4 right-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 space-y-1 text-xs">
              <div className="font-medium">Network Status</div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span>Latency: {systemMetrics.networkLatency}ms</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                <span>Throughput: {systemMetrics.throughput}/min</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                <span>Efficiency: {systemMetrics.coordinationEfficiency.toFixed(1)}%</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
} 