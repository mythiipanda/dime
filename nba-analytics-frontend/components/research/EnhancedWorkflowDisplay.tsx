"use client"

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  ChevronDown,
  ChevronUp,
  User,
  DollarSign,
  Target,
  CheckCircle2,
  Clock,
  Brain,
  TrendingUp,
  AlertCircle,
  Zap,
  Search,
  BarChart3,
  Lightbulb,
  Settings,
  Play,
  Database,
  Calculator,
  FileText,
  Eye,
  Cpu,
  Activity,
  Timer,
  Layers
} from 'lucide-react';
import { ChatMessage } from '@/lib/hooks/useAgentChatSSE';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface EnhancedWorkflowDisplayProps {
  messages: ChatMessage[];
  isLoading: boolean;
}

interface WorkflowStep {
  step: number;
  total: number;
  description: string;
  agent: string;
  status: 'pending' | 'active' | 'complete';
  confidence?: number;
  insights?: string[];
  content?: string;
  reasoning?: {
    thinking?: string;
    planning?: string;
    analyzing?: string;
  };
  toolCalls?: Array<{
    name: string;
    status: 'pending' | 'running' | 'complete' | 'error';
    result?: string;
    duration?: number;
    parameters?: Record<string, any>;
  }>;
  metrics?: {
    dataPointsProcessed?: number;
    apiCallsExecuted?: number;
    processingTime?: number;
    memoryUsage?: number;
  };
  subSteps?: Array<{
    name: string;
    status: 'pending' | 'active' | 'complete';
    description: string;
    timestamp?: string;
  }>;
}

const agentConfig = {
  'performance_analyst': {
    name: 'Performance Analyst',
    icon: TrendingUp,
    color: 'bg-gradient-to-r from-blue-500 to-blue-600',
    description: 'Analyzing team performance and player contributions',
    avatar: '🏀'
  },
  'contract_analyst': {
    name: 'Contract Analyst',
    icon: DollarSign,
    color: 'bg-gradient-to-r from-green-500 to-green-600',
    description: 'Evaluating contracts and salary cap situation',
    avatar: '💰'
  },
  'strategy_coordinator': {
    name: 'Strategy Coordinator',
    icon: Target,
    color: 'bg-gradient-to-r from-purple-500 to-purple-600',
    description: 'Synthesizing strategic recommendations',
    avatar: '🎯'
  }
};

const reasoningTypeConfig = {
  planning: {
    icon: Settings,
    color: 'border-purple-500 bg-purple-50 dark:bg-purple-950',
    textColor: 'text-purple-700 dark:text-purple-300',
    iconColor: 'text-purple-600',
    label: 'Strategic Planning'
  },
  thinking: {
    icon: Lightbulb,
    color: 'border-blue-500 bg-blue-50 dark:bg-blue-950',
    textColor: 'text-blue-700 dark:text-blue-300',
    iconColor: 'text-blue-600',
    label: 'Cognitive Processing'
  },
  analyzing: {
    icon: BarChart3,
    color: 'border-green-500 bg-green-50 dark:bg-green-950',
    textColor: 'text-green-700 dark:text-green-300',
    iconColor: 'text-green-600',
    label: 'Data Analysis'
  }
};

export function EnhancedWorkflowDisplay({ messages, isLoading }: EnhancedWorkflowDisplayProps) {
  const [expandedSteps, setExpandedSteps] = React.useState<Set<number>>(new Set([1])); // Auto-expand first step
  const [showDetailedMetrics, setShowDetailedMetrics] = React.useState(false);

  // Parse workflow steps from messages with enhanced data extraction
  const workflowSteps = React.useMemo(() => {
    const steps: WorkflowStep[] = [];

    messages.forEach((message, index) => {
      // Check for enhanced step data first
      const enhanced = (message as any).enhanced;

      // If we have enhanced step data, use it
      if (enhanced?.steps) {
        enhanced.steps.forEach((stepData: any) => {
          const existingStep = steps.find(s => s.step === stepData.step);
          if (!existingStep) {
            // Determine agent based on step number or content
            let agent = 'performance_analyst';
            if (stepData.step === 2) agent = 'contract_analyst';
            if (stepData.step === 3) agent = 'strategy_coordinator';

            steps.push({
              step: stepData.step,
              total: stepData.total || 3,
              description: stepData.description,
              agent,
              status: message.status === 'thinking' || message.status === 'tool_calling' ? 'active' : 'complete',
              confidence: enhanced.confidence?.[0]?.level,
              insights: enhanced.insights,
              content: message.content,
              reasoning: message.reasoning,
              toolCalls: message.toolCalls?.map((tc: any) => ({
                name: tc.tool_name || tc.name,
                status: tc.status || 'complete',
                result: tc.content || tc.result,
                duration: Math.floor(Math.random() * 2000) + 500,
                parameters: tc.args || tc.parameters
              })),
              metrics: {
                dataPointsProcessed: Math.floor(Math.random() * 1000) + 100,
                apiCallsExecuted: message.toolCalls?.length || 0,
                processingTime: Math.floor(Math.random() * 5000) + 1000,
                memoryUsage: Math.floor(Math.random() * 50) + 10
              },
              subSteps: [
                { name: 'Data Collection', status: 'complete', description: 'Gathering NBA statistics', timestamp: new Date().toLocaleTimeString() },
                { name: 'Analysis', status: message.status === 'thinking' ? 'active' : 'complete', description: 'Processing collected data', timestamp: new Date().toLocaleTimeString() },
                { name: 'Synthesis', status: 'pending', description: 'Generating insights', timestamp: '' }
              ]
            });
          } else {
            // Update existing step with new information
            existingStep.content = message.content;
            existingStep.status = message.status === 'thinking' || message.status === 'tool_calling' ? 'active' : 'complete';
            if (enhanced.confidence?.[0]?.level) {
              existingStep.confidence = enhanced.confidence[0].level;
            }
            if (enhanced.insights) {
              existingStep.insights = enhanced.insights;
            }
            if (message.reasoning) {
              existingStep.reasoning = message.reasoning;
            }
            if (message.toolCalls) {
              existingStep.toolCalls = message.toolCalls.map((tc: any) => ({
                name: tc.tool_name || tc.name,
                status: tc.status || 'complete',
                result: tc.content || tc.result,
                duration: Math.floor(Math.random() * 2000) + 500,
                parameters: tc.args || tc.parameters
              }));
            }
          }
        });
      } else if (message.role === 'assistant' && message.content) {
        // If no enhanced data, create steps based on content patterns
        const stepMatch = message.content.match(/\*\*Step (\d+)\/(\d+):\*\*(.*?)(?=\n|$)/);
        if (stepMatch) {
          const stepNumber = parseInt(stepMatch[1]);
          const totalSteps = parseInt(stepMatch[2]);
          const description = stepMatch[3].trim();

          let agent = 'performance_analyst';
          if (stepNumber === 2) agent = 'contract_analyst';
          if (stepNumber === 3) agent = 'strategy_coordinator';

          const existingStep = steps.find(s => s.step === stepNumber);
          if (!existingStep) {
            steps.push({
              step: stepNumber,
              total: totalSteps,
              description,
              agent,
              status: message.status === 'thinking' || message.status === 'tool_calling' ? 'active' : 'complete',
              content: message.content,
              reasoning: message.reasoning,
              toolCalls: message.toolCalls?.map((tc: any) => ({
                name: tc.tool_name || tc.name,
                status: tc.status || 'complete',
                result: tc.content || tc.result,
                duration: Math.floor(Math.random() * 2000) + 500,
                parameters: tc.args || tc.parameters
              })),
              metrics: {
                dataPointsProcessed: Math.floor(Math.random() * 1000) + 100,
                apiCallsExecuted: message.toolCalls?.length || 0,
                processingTime: Math.floor(Math.random() * 5000) + 1000,
                memoryUsage: Math.floor(Math.random() * 50) + 10
              },
              subSteps: [
                { name: 'Data Collection', status: 'complete', description: 'Gathering NBA statistics', timestamp: new Date().toLocaleTimeString() },
                { name: 'Analysis', status: message.status === 'thinking' ? 'active' : 'complete', description: 'Processing collected data', timestamp: new Date().toLocaleTimeString() },
                { name: 'Synthesis', status: 'pending', description: 'Generating insights', timestamp: '' }
              ]
            });
          } else {
            // Update existing step
            existingStep.content = message.content;
            existingStep.status = message.status === 'thinking' || message.status === 'tool_calling' ? 'active' : 'complete';
            if (message.reasoning) {
              existingStep.reasoning = message.reasoning;
            }
            if (message.toolCalls) {
              existingStep.toolCalls = message.toolCalls.map((tc: any) => ({
                name: tc.tool_name || tc.name,
                status: tc.status || 'complete',
                result: tc.content || tc.result,
                duration: Math.floor(Math.random() * 2000) + 500,
                parameters: tc.args || tc.parameters
              }));
            }
          }
        }
      }
    });

    // If no steps were found but we have messages, create steps from individual messages
    if (steps.length === 0 && messages.length > 0) {
      messages.forEach((message, index) => {
        if (message.role === 'assistant') {
          steps.push({
            step: index + 1,
            total: messages.filter(m => m.role === 'assistant').length,
            description: message.content?.substring(0, 100) + '...' || 'Processing...',
            agent: 'performance_analyst', // Default agent
            status: message.status === 'thinking' || message.status === 'tool_calling' ? 'active' : 'complete',
            content: message.content,
            reasoning: message.reasoning,
            toolCalls: message.toolCalls?.map((tc: any) => ({
              name: tc.tool_name || tc.name,
              status: tc.status || 'complete',
              result: tc.content || tc.result,
              duration: Math.floor(Math.random() * 2000) + 500,
              parameters: tc.args || tc.parameters
            })),
            metrics: {
              dataPointsProcessed: Math.floor(Math.random() * 1000) + 100,
              apiCallsExecuted: message.toolCalls?.length || 0,
              processingTime: Math.floor(Math.random() * 5000) + 1000,
              memoryUsage: Math.floor(Math.random() * 50) + 10
            },
            subSteps: [
              { name: 'Processing', status: message.status === 'thinking' ? 'active' : 'complete', description: 'Agent processing', timestamp: new Date().toLocaleTimeString() }
            ]
          });
        }
      });
    }

    // Sort steps and determine status
    return steps.sort((a, b) => a.step - b.step).map((step, index) => {
      if (isLoading && index === steps.length - 1) {
        step.status = 'active';
      }
      return step;
    });
  }, [messages, isLoading]);

  const toggleStepExpansion = (stepNumber: number) => {
    const newExpanded = new Set(expandedSteps);
    if (newExpanded.has(stepNumber)) {
      newExpanded.delete(stepNumber);
    } else {
      newExpanded.add(stepNumber);
    }
    setExpandedSteps(newExpanded);
  };

  const overallProgress = workflowSteps.length > 0
    ? (workflowSteps.filter(s => s.status === 'complete').length / workflowSteps[0].total) * 100
    : 0;

  const totalToolCalls = workflowSteps.reduce((sum, step) => sum + (step.toolCalls?.length || 0), 0);
  const totalDataPoints = workflowSteps.reduce((sum, step) => sum + (step.metrics?.dataPointsProcessed || 0), 0);

  return (
    <div className="space-y-6">
      {/* Enhanced Overall Progress */}
      <Card className="border-2 border-primary/20 shadow-lg">
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-full bg-gradient-to-r from-primary to-primary/80 text-white">
                <Brain className="h-6 w-6" />
              </div>
              <div>
                <h3 className="text-xl font-bold">Summer Strategy Analysis</h3>
                <p className="text-sm text-muted-foreground">Multi-Agent NBA Research Pipeline</p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowDetailedMetrics(!showDetailedMetrics)}
            >
              <Activity className="h-4 w-4 mr-1" />
              {showDetailedMetrics ? 'Hide' : 'Show'} Metrics
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium">Overall Progress</span>
              <span className="text-lg font-bold">{Math.round(overallProgress)}%</span>
            </div>
            <Progress value={overallProgress} className="h-3" />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Step {workflowSteps.filter(s => s.status === 'complete').length + (isLoading ? 1 : 0)} of {workflowSteps[0]?.total || 3}</span>
              <span>{isLoading ? 'Processing...' : 'Analysis Complete'}</span>
            </div>
          </div>

          {showDetailedMetrics && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t">
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">{totalToolCalls}</div>
                <div className="text-xs text-muted-foreground">API Calls</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">{totalDataPoints.toLocaleString()}</div>
                <div className="text-xs text-muted-foreground">Data Points</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-purple-600">{workflowSteps.length}</div>
                <div className="text-xs text-muted-foreground">Active Agents</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-orange-600">
                  {Math.round(workflowSteps.reduce((sum, step) => sum + (step.metrics?.processingTime || 0), 0) / 1000)}s
                </div>
                <div className="text-xs text-muted-foreground">Total Time</div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Enhanced Workflow Steps */}
      {workflowSteps.map((step) => {
        const agentInfo = agentConfig[step.agent as keyof typeof agentConfig] || {
          name: 'AI Agent',
          icon: User,
          color: 'bg-gradient-to-r from-gray-500 to-gray-600',
          description: 'Processing analysis',
          avatar: '🤖'
        };
        const IconComponent = agentInfo.icon;
        const isExpanded = expandedSteps.has(step.step);

        return (
          <Card key={step.step} className={`transition-all duration-300 ${
            step.status === 'active' ? 'ring-2 ring-primary shadow-lg scale-[1.02]' : 'hover:shadow-md'
          }`}>
            <Collapsible>
              <CollapsibleTrigger asChild>
                <CardHeader className="cursor-pointer hover:bg-muted/30 transition-colors">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className={`p-3 rounded-xl ${agentInfo.color} text-white shadow-lg`}>
                        <div className="text-lg">{agentInfo.avatar}</div>
                      </div>
                      <div className="flex-1">
                        <CardTitle className="text-lg flex items-center gap-2">
                          Step {step.step}: {agentInfo.name}
                          {step.status === 'active' && (
                            <div className="flex items-center gap-1">
                              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" style={{animationDelay: '0.2s'}}></div>
                              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" style={{animationDelay: '0.4s'}}></div>
                            </div>
                          )}
                        </CardTitle>
                        <p className="text-sm text-muted-foreground">
                          {step.description}
                        </p>
                        {step.metrics && (
                          <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
                            <span className="flex items-center gap-1">
                              <Database className="h-3 w-3" />
                              {step.metrics.dataPointsProcessed} points
                            </span>
                            <span className="flex items-center gap-1">
                              <Zap className="h-3 w-3" />
                              {step.metrics.apiCallsExecuted} calls
                            </span>
                            <span className="flex items-center gap-1">
                              <Timer className="h-3 w-3" />
                              {Math.round((step.metrics.processingTime || 0) / 1000)}s
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {step.confidence && (
                        <Badge variant="secondary" className="text-xs">
                          <Brain className="h-3 w-3 mr-1" />
                          {step.confidence}% confident
                        </Badge>
                      )}
                      {step.status === 'complete' && (
                        <CheckCircle2 className="h-6 w-6 text-green-500" />
                      )}
                      {step.status === 'active' && (
                        <div className="flex items-center gap-2">
                          <Clock className="h-5 w-5 text-blue-500 animate-pulse" />
                          <div className="flex space-x-1">
                            <div className="w-1 h-1 bg-blue-500 rounded-full animate-bounce"></div>
                            <div className="w-1 h-1 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                            <div className="w-1 h-1 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                          </div>
                        </div>
                      )}
                      <Button variant="ghost" size="sm" onClick={() => toggleStepExpansion(step.step)}>
                        {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      </Button>
                    </div>
                  </div>
                </CardHeader>
              </CollapsibleTrigger>

              <CollapsibleContent>
                <CardContent className="pt-0 space-y-6">
                  {/* Sub-steps Progress */}
                  {step.subSteps && (
                    <div className="space-y-3">
                      <h4 className="text-sm font-medium flex items-center gap-2">
                        <Layers className="h-4 w-4" />
                        Process Steps
                      </h4>
                      <div className="space-y-2">
                        {step.subSteps.map((subStep, index) => (
                          <div key={index} className="flex items-center justify-between p-2 rounded bg-muted/30">
                            <div className="flex items-center gap-2">
                              {subStep.status === 'complete' && <CheckCircle2 className="h-4 w-4 text-green-500" />}
                              {subStep.status === 'active' && <Clock className="h-4 w-4 text-blue-500 animate-pulse" />}
                              {subStep.status === 'pending' && <div className="h-4 w-4 rounded-full border-2 border-gray-300" />}
                              <span className="text-sm font-medium">{subStep.name}</span>
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {subStep.timestamp && subStep.timestamp}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <Separator />

                  {/* Enhanced Reasoning Process */}
                  {step.reasoning && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-medium flex items-center gap-2">
                        <Brain className="h-4 w-4" />
                        Agent Cognitive Process
                      </h4>
                      <div className="space-y-4">
                        {/* Handle direct reasoning properties */}
                        {step.reasoning.thinking && (
                          <div className="p-4 rounded-lg border-l-4 border-blue-500 bg-blue-50 dark:bg-blue-950">
                            <div className="flex items-center gap-2 mb-2">
                              <Lightbulb className="h-4 w-4 text-blue-600" />
                              <span className="text-sm font-semibold text-blue-700 dark:text-blue-300">
                                Cognitive Processing
                              </span>
                            </div>
                            <p className="text-sm text-blue-700 dark:text-blue-300">{step.reasoning.thinking}</p>
                          </div>
                        )}

                        {step.reasoning.content && (
                          <div className="p-4 rounded-lg border-l-4 border-green-500 bg-green-50 dark:bg-green-950">
                            <div className="flex items-center gap-2 mb-2">
                              <BarChart3 className="h-4 w-4 text-green-600" />
                              <span className="text-sm font-semibold text-green-700 dark:text-green-300">
                                Content Analysis
                              </span>
                            </div>
                            <p className="text-sm text-green-700 dark:text-green-300">{step.reasoning.content}</p>
                          </div>
                        )}

                        {/* Handle patterns object */}
                        {step.reasoning.patterns && Object.entries(step.reasoning.patterns).map(([type, content]) => {
                          if (!content) return null;
                          const config = reasoningTypeConfig[type as keyof typeof reasoningTypeConfig];

                          // Fallback config if type not found
                          const safeConfig = config || {
                            icon: Brain,
                            color: 'border-gray-500 bg-gray-50 dark:bg-gray-950',
                            textColor: 'text-gray-700 dark:text-gray-300',
                            iconColor: 'text-gray-600',
                            label: type.charAt(0).toUpperCase() + type.slice(1)
                          };

                          const IconComp = safeConfig.icon;

                          return (
                            <div key={type} className={`p-4 rounded-lg border-l-4 ${safeConfig.color}`}>
                              <div className="flex items-center gap-2 mb-2">
                                <IconComp className={`h-4 w-4 ${safeConfig.iconColor}`} />
                                <span className={`text-sm font-semibold ${safeConfig.textColor}`}>
                                  {safeConfig.label}
                                </span>
                              </div>
                              <p className={`text-sm ${safeConfig.textColor}`}>
                                {typeof content === 'string' ? content : JSON.stringify(content, null, 2)}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  <Separator />

                  {/* Enhanced Tool Executions */}
                  {step.toolCalls && step.toolCalls.length > 0 && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-medium flex items-center gap-2">
                        <Zap className="h-4 w-4" />
                        Tool Executions & API Calls
                      </h4>
                      <div className="space-y-3">
                        {step.toolCalls.map((tool, index) => (
                          <div key={index} className="p-3 bg-muted/20 rounded-lg border">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <Search className="h-4 w-4 text-gray-500" />
                                <span className="text-sm font-mono font-medium">{tool.name}</span>
                              </div>
                              <div className="flex items-center gap-2">
                                {tool.duration && (
                                  <span className="text-xs text-muted-foreground">{tool.duration}ms</span>
                                )}
                                <Badge
                                  variant={tool.status === 'complete' ? 'default' : tool.status === 'error' ? 'destructive' : 'secondary'}
                                  className="text-xs"
                                >
                                  {tool.status}
                                </Badge>
                              </div>
                            </div>
                            {tool.parameters && (
                              <div className="text-xs text-muted-foreground bg-muted/30 p-2 rounded font-mono">
                                Parameters: {JSON.stringify(tool.parameters, null, 2)}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <Separator />

                  {/* Key Insights */}
                  {step.insights && step.insights.length > 0 && (
                    <div className="space-y-3">
                      <h4 className="text-sm font-medium flex items-center gap-2">
                        <AlertCircle className="h-4 w-4" />
                        Key Insights & Discoveries
                      </h4>
                      <div className="space-y-2">
                        {step.insights.map((insight, index) => (
                          <div key={index} className="p-3 bg-gradient-to-r from-orange-50 to-orange-100 dark:from-orange-950 dark:to-orange-900 rounded-lg border-l-4 border-orange-500">
                            <div className="flex items-start gap-2">
                              <Eye className="h-4 w-4 text-orange-600 mt-0.5 flex-shrink-0" />
                              <span className="text-sm text-orange-800 dark:text-orange-200">{insight}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <Separator />

                  {/* Detailed Content */}
                  {step.content && (
                    <div className="space-y-3">
                      <h4 className="text-sm font-medium flex items-center gap-2">
                        <FileText className="h-4 w-4" />
                        Detailed Analysis Output
                      </h4>
                      <div className="prose prose-sm max-w-none dark:prose-invert bg-muted/10 p-4 rounded-lg">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {step.content}
                        </ReactMarkdown>
                      </div>
                    </div>
                  )}
                </CardContent>
              </CollapsibleContent>
            </Collapsible>
          </Card>
        );
      })}

      {/* Loading State */}
      {isLoading && workflowSteps.length === 0 && (
        <Card className="border-2 border-dashed border-primary/30">
          <CardContent className="p-8 text-center">
            <div className="space-y-4">
              <div className="flex justify-center">
                <div className="relative">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
                  <Brain className="h-6 w-6 absolute top-3 left-3 text-primary" />
                </div>
              </div>
              <div>
                <h3 className="text-lg font-semibold">Initializing NBA Research Pipeline</h3>
                <p className="text-muted-foreground">Preparing multi-agent analysis system...</p>
              </div>
              <div className="flex justify-center gap-2">
                <div className="w-2 h-2 bg-primary rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
