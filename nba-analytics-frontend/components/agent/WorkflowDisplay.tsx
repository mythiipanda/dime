"use client"

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
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
  Play
} from 'lucide-react';
import { ChatMessage } from '@/lib/hooks/useAgentChatSSE';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface WorkflowDisplayProps {
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
  }>;
}

const agentConfig = {
  'performance_analyst': {
    name: 'Performance Analyst',
    icon: TrendingUp,
    color: 'bg-blue-500',
    description: 'Analyzing team performance and player contributions'
  },
  'contract_analyst': {
    name: 'Contract Analyst',
    icon: DollarSign,
    color: 'bg-green-500',
    description: 'Evaluating contracts and salary cap situation'
  },
  'strategy_coordinator': {
    name: 'Strategy Coordinator',
    icon: Target,
    color: 'bg-purple-500',
    description: 'Synthesizing strategic recommendations'
  }
};

export function WorkflowDisplay({ messages, isLoading }: WorkflowDisplayProps) {
  const [expandedSteps, setExpandedSteps] = React.useState<Set<number>>(new Set());

  // Parse workflow steps from messages
  const workflowSteps = React.useMemo(() => {
    const steps: WorkflowStep[] = [];

    messages.forEach((message, index) => {
      const enhanced = (message as any).enhanced;
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
              reasoning: (message as any).reasoning,
              toolCalls: message.toolCalls?.map(tc => ({
                name: tc.name,
                status: tc.status || 'complete',
                result: tc.result
              }))
            });
          } else {
            // Update existing step
            existingStep.content = message.content;
            existingStep.status = message.status === 'thinking' || message.status === 'tool_calling' ? 'active' : 'complete';
            if (enhanced.confidence?.[0]?.level) {
              existingStep.confidence = enhanced.confidence[0].level;
            }
            if (enhanced.insights) {
              existingStep.insights = enhanced.insights;
            }
            if ((message as any).reasoning) {
              existingStep.reasoning = (message as any).reasoning;
            }
            if (message.toolCalls) {
              existingStep.toolCalls = message.toolCalls.map(tc => ({
                name: tc.name,
                status: tc.status || 'complete',
                result: tc.result
              }));
            }
          }
        });
      }
    });

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

  return (
    <div className="space-y-4">
      {/* Overall Progress */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5" />
            Summer Strategy Analysis Progress
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Overall Progress</span>
              <span>{Math.round(overallProgress)}%</span>
            </div>
            <Progress value={overallProgress} className="h-2" />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Step {workflowSteps.filter(s => s.status === 'complete').length + (isLoading ? 1 : 0)} of {workflowSteps[0]?.total || 3}</span>
              <span>{isLoading ? 'In Progress' : 'Complete'}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Workflow Steps */}
      {workflowSteps.map((step) => {
        const agentInfo = agentConfig[step.agent as keyof typeof agentConfig];
        const IconComponent = agentInfo?.icon || User;
        const isExpanded = expandedSteps.has(step.step);

        return (
          <Card key={step.step} className={`transition-all duration-200 ${
            step.status === 'active' ? 'ring-2 ring-primary' : ''
          }`}>
            <Collapsible>
              <CollapsibleTrigger asChild>
                <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-full ${agentInfo?.color || 'bg-gray-500'} text-white`}>
                        <IconComponent className="h-4 w-4" />
                      </div>
                      <div>
                        <CardTitle className="text-base">
                          Step {step.step}: {agentInfo?.name || 'Agent'}
                        </CardTitle>
                        <p className="text-sm text-muted-foreground">
                          {step.description}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {step.confidence && (
                        <Badge variant="secondary" className="text-xs">
                          {step.confidence}% confident
                        </Badge>
                      )}
                      {step.status === 'complete' && (
                        <CheckCircle2 className="h-5 w-5 text-green-500" />
                      )}
                      {step.status === 'active' && (
                        <div className="flex items-center gap-1">
                          <Clock className="h-4 w-4 text-blue-500 animate-pulse" />
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
                <CardContent className="pt-0">
                  {/* Reasoning Process */}
                  {step.reasoning && (
                    <div className="mb-4">
                      <h4 className="text-sm font-medium mb-3 flex items-center gap-1">
                        <Brain className="h-4 w-4" />
                        Agent Reasoning
                      </h4>
                      <div className="space-y-3">
                        {step.reasoning.planning && (
                          <div className="bg-purple-50 dark:bg-purple-950 p-3 rounded border-l-2 border-purple-500">
                            <div className="flex items-center gap-2 mb-1">
                              <Settings className="h-3 w-3 text-purple-600" />
                              <span className="text-xs font-medium text-purple-600">Planning</span>
                            </div>
                            <p className="text-sm">{step.reasoning.planning}</p>
                          </div>
                        )}
                        {step.reasoning.thinking && (
                          <div className="bg-blue-50 dark:bg-blue-950 p-3 rounded border-l-2 border-blue-500">
                            <div className="flex items-center gap-2 mb-1">
                              <Lightbulb className="h-3 w-3 text-blue-600" />
                              <span className="text-xs font-medium text-blue-600">Thinking</span>
                            </div>
                            <p className="text-sm">{step.reasoning.thinking}</p>
                          </div>
                        )}
                        {step.reasoning.analyzing && (
                          <div className="bg-green-50 dark:bg-green-950 p-3 rounded border-l-2 border-green-500">
                            <div className="flex items-center gap-2 mb-1">
                              <BarChart3 className="h-3 w-3 text-green-600" />
                              <span className="text-xs font-medium text-green-600">Analyzing</span>
                            </div>
                            <p className="text-sm">{step.reasoning.analyzing}</p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Tool Calls */}
                  {step.toolCalls && step.toolCalls.length > 0 && (
                    <div className="mb-4">
                      <h4 className="text-sm font-medium mb-3 flex items-center gap-1">
                        <Zap className="h-4 w-4" />
                        Tool Executions
                      </h4>
                      <div className="space-y-2">
                        {step.toolCalls.map((tool, index) => (
                          <div key={index} className="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-900 rounded">
                            <div className="flex items-center gap-2">
                              <Search className="h-3 w-3 text-gray-500" />
                              <span className="text-sm font-mono">{tool.name}</span>
                            </div>
                            <Badge
                              variant={tool.status === 'complete' ? 'default' : tool.status === 'error' ? 'destructive' : 'secondary'}
                              className="text-xs"
                            >
                              {tool.status}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Key Insights */}
                  {step.insights && step.insights.length > 0 && (
                    <div className="mb-4">
                      <h4 className="text-sm font-medium mb-2 flex items-center gap-1">
                        <AlertCircle className="h-4 w-4" />
                        Key Insights
                      </h4>
                      <div className="space-y-1">
                        {step.insights.map((insight, index) => (
                          <div key={index} className="text-sm bg-orange-50 dark:bg-orange-950 p-2 rounded border-l-2 border-orange-500">
                            {insight}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Detailed Content */}
                  {step.content && (
                    <div className="prose prose-sm max-w-none dark:prose-invert">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {step.content}
                      </ReactMarkdown>
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
        <Card>
          <CardContent className="p-6 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
            <p className="text-muted-foreground">Initializing summer strategy analysis...</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
