"use client";

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BotIcon, BarChart2, Briefcase, Target, Users, Zap, RefreshCw } from "lucide-react";

interface TeamAIAssistantProps {
  teamId: string;
  teamName: string;
  season: string;
}

export function TeamAIAssistant({ teamId, teamName, season }: TeamAIAssistantProps) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [activeTab, setActiveTab] = useState("chat");
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "assistant",
      content: `I'm your NBA Analytics Assistant for the ${teamName}. I can help you analyze games, identify team strengths and weaknesses, suggest lineup optimizations, and find potential trade targets.`,
      timestamp: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState("");
  const [analysisResults, setAnalysisResults] = useState<AnalysisResults | null>(null);

  // Simulate running an analysis
  const runAnalysis = async () => {
    setIsAnalyzing(true);
    
    // In a real implementation, this would call an API
    setTimeout(() => {
      setAnalysisResults({
        gameAnalysis: {
          title: "Season Performance Analysis",
          summary: "The Warriors have shown strong offensive efficiency but struggle with defensive consistency, particularly in transition defense and defending the paint.",
          keyMetrics: [
            { name: "Offensive Rating", value: "116.8", trend: "up" },
            { name: "Defensive Rating", value: "114.2", trend: "down" },
            { name: "Net Rating", value: "+2.6", trend: "up" },
            { name: "Pace", value: "101.2", trend: "neutral" },
          ],
          recommendations: [
            "Increase defensive pressure on perimeter shooters",
            "Improve transition defense to limit fast break points",
            "Utilize more small-ball lineups in fourth quarters",
          ],
        },
        weaknesses: {
          title: "Team Weaknesses",
          areas: [
            {
              name: "Interior Defense",
              description: "Allowing 48.2 points in the paint per game (24th in NBA)",
              impact: "high",
            },
            {
              name: "Defensive Rebounding",
              description: "72.4% defensive rebound rate (22nd in NBA)",
              impact: "medium",
            },
            {
              name: "Free Throw Generation",
              description: "19.8 free throw attempts per game (27th in NBA)",
              impact: "medium",
            },
            {
              name: "Bench Scoring",
              description: "28.5 bench points per game (20th in NBA)",
              impact: "medium",
            },
          ],
        },
        lineupSuggestions: {
          title: "Lineup Optimization",
          suggestions: [
            {
              name: "Closing Lineup",
              players: ["Stephen Curry", "Klay Thompson", "Andrew Wiggins", "Draymond Green", "Kevon Looney"],
              netRating: "+8.5",
              description: "Strong defensive communication with balanced scoring",
            },
            {
              name: "Small Ball Lineup",
              players: ["Stephen Curry", "Jordan Poole", "Klay Thompson", "Andrew Wiggins", "Draymond Green"],
              netRating: "+5.2",
              description: "High pace and spacing for offensive bursts",
            },
            {
              name: "Defensive Lineup",
              players: ["Stephen Curry", "Gary Payton II", "Andrew Wiggins", "Draymond Green", "Kevon Looney"],
              netRating: "+7.1",
              description: "Elite perimeter and interior defense",
            },
          ],
        },
        tradeTargets: {
          title: "Potential Trade Targets",
          targets: [
            {
              name: "Myles Turner",
              team: "Indiana Pacers",
              position: "C",
              fit: "high",
              description: "Elite rim protector who can stretch the floor",
              contract: "$18M/year through 2025-26",
            },
            {
              name: "OG Anunoby",
              team: "Toronto Raptors",
              position: "SF/PF",
              fit: "high",
              description: "Versatile defender with developing offensive game",
              contract: "$19.9M/year through 2024-25",
            },
            {
              name: "Jonas Valančiūnas",
              team: "New Orleans Pelicans",
              position: "C",
              fit: "medium",
              description: "Strong rebounder and interior presence",
              contract: "$15.4M/year through 2023-24",
            },
          ],
        },
      });
      
      // Add a message about the completed analysis
      setMessages(prev => [
        ...prev,
        {
          id: Date.now().toString(),
          role: "assistant" as const,
          content: `I've completed a comprehensive analysis of the ${teamName} for the ${season} season. Check the Analysis tab to see my findings on team performance, weaknesses, lineup suggestions, and potential trade targets.`,
          timestamp: new Date().toISOString(),
        }
      ]);
      
      setIsAnalyzing(false);
    }, 3000);
  };

  const handleSendMessage = () => {
    if (!input.trim()) return;
    
    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date().toISOString(),
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    
    // Simulate AI response
    setTimeout(() => {
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `I'll analyze that for the ${teamName}. Let me process the data and get back to you shortly.`,
        timestamp: new Date().toISOString(),
      };
      
      setMessages(prev => [...prev, assistantMessage]);
    }, 1000);
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center">
              <BotIcon className="mr-2 h-5 w-5" />
              Team AI Assistant
            </CardTitle>
            <CardDescription>
              AI-powered analysis and insights for {teamName}
            </CardDescription>
          </div>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={runAnalysis} 
            disabled={isAnalyzing}
          >
            {isAnalyzing ? (
              <>
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Zap className="mr-2 h-4 w-4" />
                Run Analysis
              </>
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="chat" value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="chat">Chat</TabsTrigger>
            <TabsTrigger value="analysis">Analysis</TabsTrigger>
          </TabsList>
          
          <TabsContent value="chat" className="space-y-4 mt-4">
            <div className="h-[400px] overflow-y-auto space-y-4 p-4 border rounded-md">
              {messages.map(message => (
                <div 
                  key={message.id}
                  className={`flex ${message.role === 'assistant' ? 'justify-start' : 'justify-end'}`}
                >
                  <div className={`flex gap-3 max-w-[80%] ${message.role === 'assistant' ? 'flex-row' : 'flex-row-reverse'}`}>
                    {message.role === 'assistant' && (
                      <Avatar className="h-8 w-8">
                        <BotIcon className="h-5 w-5" />
                      </Avatar>
                    )}
                    <div className={`rounded-lg px-4 py-2 ${
                      message.role === 'assistant' 
                        ? 'bg-secondary text-secondary-foreground' 
                        : 'bg-primary text-primary-foreground'
                    }`}>
                      <p className="text-sm">{message.content}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            
            <div className="flex gap-2">
              <Textarea
                placeholder="Ask about team performance, weaknesses, or potential improvements..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                className="resize-none"
              />
              <Button onClick={handleSendMessage}>Send</Button>
            </div>
          </TabsContent>
          
          <TabsContent value="analysis" className="space-y-6 mt-4">
            {!analysisResults ? (
              <div className="text-center py-12">
                <BotIcon className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="text-lg font-medium mb-2">No Analysis Available</h3>
                <p className="text-muted-foreground mb-4">
                  Run an analysis to see AI-powered insights about team performance, weaknesses, and recommendations.
                </p>
                <Button onClick={runAnalysis} disabled={isAnalyzing}>
                  {isAnalyzing ? "Analyzing..." : "Run Analysis"}
                </Button>
              </div>
            ) : (
              <>
                {/* Game Analysis */}
                <div className="space-y-4">
                  <h3 className="text-lg font-medium">{analysisResults.gameAnalysis.title}</h3>
                  <p className="text-sm text-muted-foreground">{analysisResults.gameAnalysis.summary}</p>
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {analysisResults.gameAnalysis.keyMetrics.map((metric, i) => (
                      <div key={i} className="border rounded-md p-3">
                        <p className="text-xs text-muted-foreground">{metric.name}</p>
                        <div className="flex items-center justify-between">
                          <p className="text-lg font-medium">{metric.value}</p>
                          <Badge variant={
                            metric.trend === 'up' ? 'default' : 
                            metric.trend === 'down' ? 'destructive' : 'outline'
                          }>
                            {metric.trend === 'up' ? '↑' : metric.trend === 'down' ? '↓' : '–'}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                  
                  <div className="border-t pt-4">
                    <h4 className="font-medium mb-2">Recommendations</h4>
                    <ul className="list-disc list-inside space-y-1">
                      {analysisResults.gameAnalysis.recommendations.map((rec, i) => (
                        <li key={i} className="text-sm">{rec}</li>
                      ))}
                    </ul>
                  </div>
                </div>
                
                {/* Team Weaknesses */}
                <div className="space-y-4 border-t pt-6">
                  <h3 className="text-lg font-medium flex items-center">
                    <Target className="mr-2 h-5 w-5" />
                    {analysisResults.weaknesses.title}
                  </h3>
                  
                  <div className="space-y-3">
                    {analysisResults.weaknesses.areas.map((weakness, i) => (
                      <div key={i} className="border rounded-md p-3">
                        <div className="flex items-center justify-between mb-1">
                          <h4 className="font-medium">{weakness.name}</h4>
                          <Badge variant={
                            weakness.impact === 'high' ? 'destructive' : 
                            weakness.impact === 'medium' ? 'default' : 'outline'
                          }>
                            {weakness.impact} impact
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">{weakness.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
                
                {/* Lineup Suggestions */}
                <div className="space-y-4 border-t pt-6">
                  <h3 className="text-lg font-medium flex items-center">
                    <Users className="mr-2 h-5 w-5" />
                    {analysisResults.lineupSuggestions.title}
                  </h3>
                  
                  <div className="space-y-3">
                    {analysisResults.lineupSuggestions.suggestions.map((lineup, i) => (
                      <div key={i} className="border rounded-md p-3">
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="font-medium">{lineup.name}</h4>
                          <Badge variant={
                            parseFloat(lineup.netRating) > 5 ? 'default' : 
                            parseFloat(lineup.netRating) > 0 ? 'outline' : 'destructive'
                          }>
                            {lineup.netRating}
                          </Badge>
                        </div>
                        <div className="flex flex-wrap gap-1 mb-2">
                          {lineup.players.map((player, j) => (
                            <Badge key={j} variant="secondary">{player}</Badge>
                          ))}
                        </div>
                        <p className="text-sm text-muted-foreground">{lineup.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
                
                {/* Trade Targets */}
                <div className="space-y-4 border-t pt-6">
                  <h3 className="text-lg font-medium flex items-center">
                    <Briefcase className="mr-2 h-5 w-5" />
                    {analysisResults.tradeTargets.title}
                  </h3>
                  
                  <div className="space-y-3">
                    {analysisResults.tradeTargets.targets.map((target, i) => (
                      <div key={i} className="border rounded-md p-3">
                        <div className="flex items-center justify-between mb-1">
                          <div>
                            <h4 className="font-medium">{target.name}</h4>
                            <p className="text-xs text-muted-foreground">{target.team} | {target.position}</p>
                          </div>
                          <Badge variant={
                            target.fit === 'high' ? 'default' : 
                            target.fit === 'medium' ? 'outline' : 'secondary'
                          }>
                            {target.fit} fit
                          </Badge>
                        </div>
                        <p className="text-sm mb-1">{target.description}</p>
                        <p className="text-xs text-muted-foreground">Contract: {target.contract}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

// Types
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface AnalysisResults {
  gameAnalysis: {
    title: string;
    summary: string;
    keyMetrics: Array<{
      name: string;
      value: string;
      trend: 'up' | 'down' | 'neutral';
    }>;
    recommendations: string[];
  };
  weaknesses: {
    title: string;
    areas: Array<{
      name: string;
      description: string;
      impact: 'high' | 'medium' | 'low';
    }>;
  };
  lineupSuggestions: {
    title: string;
    suggestions: Array<{
      name: string;
      players: string[];
      netRating: string;
      description: string;
    }>;
  };
  tradeTargets: {
    title: string;
    targets: Array<{
      name: string;
      team: string;
      position: string;
      fit: 'high' | 'medium' | 'low';
      description: string;
      contract: string;
    }>;
  };
} 