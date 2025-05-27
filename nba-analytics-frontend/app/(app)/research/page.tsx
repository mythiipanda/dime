'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Target } from 'lucide-react';
import { useAgentChatSSE } from '@/lib/hooks/useAgentChatSSE';
import { ErrorDisplay } from '@/components/agent/ErrorDisplay';
import { EnhancedWorkflowDisplay } from '@/components/research/EnhancedWorkflowDisplay';
import SimulationSetup from '@/components/research/SimulationSetup';
import CustomAgentConfigurator from '@/components/research/CustomAgentConfigurator';
import DraftBoardViewer from '@/components/research/DraftBoardViewer';
import StatComparisonTool from '@/components/research/StatComparisonTool';
import GameAnalysisViewer from '@/components/research/GameAnalysisViewer';
import PlayerScoutingReportGenerator from '@/components/research/PlayerScoutingReportGenerator';

// NBA Teams for summer strategy analysis
const nbaTeams = [
  'Atlanta Hawks', 'Boston Celtics', 'Brooklyn Nets', 'Charlotte Hornets', 'Chicago Bulls',
  'Cleveland Cavaliers', 'Dallas Mavericks', 'Denver Nuggets', 'Detroit Pistons', 'Golden State Warriors',
  'Houston Rockets', 'Indiana Pacers', 'LA Clippers', 'Los Angeles Lakers', 'Memphis Grizzlies',
  'Miami Heat', 'Milwaukee Bucks', 'Minnesota Timberwolves', 'New Orleans Pelicans', 'New York Knicks',
  'Oklahoma City Thunder', 'Orlando Magic', 'Philadelphia 76ers', 'Phoenix Suns', 'Portland Trail Blazers',
  'Sacramento Kings', 'San Antonio Spurs', 'Toronto Raptors', 'Utah Jazz', 'Washington Wizards'
];

export default function ResearchPage() {
  const [selectedTeam, setSelectedTeam] = useState<string>('');
  const [season, setSeason] = useState<string>('2024-25');

  const {
    isLoading,
    error,
    chatHistory,
    submitPrompt,
    closeConnection
  } = useAgentChatSSE({ apiUrl: '/api/v1/summer-strategy' });

  const scrollAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollAreaRef.current) {
      setTimeout(() => {
        if (scrollAreaRef.current) {
           scrollAreaRef.current.scrollTo({ top: scrollAreaRef.current.scrollHeight, behavior: 'smooth' });
        }
      }, 100);
    }
  }, [chatHistory]);

  useEffect(() => {
    return () => {
      closeConnection();
    };
  }, [closeConnection]);

  const handleSummerStrategySubmit = () => {
    if (!selectedTeam) {
      alert('Please select a team for summer strategy analysis');
      return;
    }
    // Submit with team parameter for summer strategy endpoint
    // The API route will parse this from the prompt parameter
    submitPrompt(`team_name=${encodeURIComponent(selectedTeam)}&season=${encodeURIComponent(season)}`);
  };

  const handleStop = () => {
    closeConnection();
  };

  return (
    <div className="container mx-auto p-4 space-y-6 max-w-5xl">
      <header className="text-center space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">NBA Research Hub</h1>
        <p className="text-muted-foreground">
          Generate comprehensive NBA research reports and strategic analysis.
        </p>
      </header>

      <Tabs defaultValue="summer-strategy" className="w-full">
        <TabsList className="grid w-full grid-cols-3 md:grid-cols-7 mb-4">
          <TabsTrigger value="summer-strategy">Summer Strategy</TabsTrigger>
          <TabsTrigger value="simulation">Simulation</TabsTrigger>
          <TabsTrigger value="customAgent">Custom Agent</TabsTrigger>
          <TabsTrigger value="draftBoard">Draft Board</TabsTrigger>
          <TabsTrigger value="statComparison">Stat Comparison</TabsTrigger>
          <TabsTrigger value="gameAnalysis">Game Analysis</TabsTrigger>
          <TabsTrigger value="scoutingReport">Scouting Report</TabsTrigger>
        </TabsList>

        <TabsContent value="summer-strategy" className="space-y-6">
          {/* Summer Strategy Configuration */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5" />
                Team Summer Strategy Analysis
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="team-select">NBA Team</Label>
                  <Select value={selectedTeam} onValueChange={setSelectedTeam}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select NBA team" />
                    </SelectTrigger>
                    <SelectContent>
                      {nbaTeams.map((team) => (
                        <SelectItem key={team} value={team}>{team}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="season-input">Season</Label>
                  <Input
                    id="season-input"
                    value={season}
                    onChange={(e) => setSeason(e.target.value)}
                    placeholder="2024-25"
                  />
                </div>
              </div>

              <div className="flex gap-2">
                <Button
                  onClick={handleSummerStrategySubmit}
                  disabled={!selectedTeam || isLoading}
                  className="flex-1"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    `Analyze ${selectedTeam || 'Team'} Summer Strategy`
                  )}
                </Button>
                {isLoading && (
                  <Button variant="outline" onClick={handleStop}>
                    Stop
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Error Display */}
          {error && (
            <ErrorDisplay error={error} />
          )}

          {/* Enhanced Workflow Display */}
          {(chatHistory.length > 0 || isLoading) && (
            <EnhancedWorkflowDisplay
              messages={chatHistory}
              isLoading={isLoading}
            />
          )}

          {/* Empty State */}
          {chatHistory.length === 0 && !isLoading && !error && (
            <Card className="p-6 text-center">
              <Target className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
              <p className="text-muted-foreground">Select a team above to generate a comprehensive summer strategy analysis.</p>
            </Card>
          )}
        </TabsContent>
        <TabsContent value="simulation"><SimulationSetup /></TabsContent>
        <TabsContent value="customAgent"><CustomAgentConfigurator /></TabsContent>
        <TabsContent value="draftBoard"><DraftBoardViewer /></TabsContent>
        <TabsContent value="statComparison"><StatComparisonTool /></TabsContent>
        <TabsContent value="gameAnalysis"><GameAnalysisViewer /></TabsContent>
        <TabsContent value="scoutingReport"><PlayerScoutingReportGenerator /></TabsContent>
      </Tabs>
    </div>
  );
}