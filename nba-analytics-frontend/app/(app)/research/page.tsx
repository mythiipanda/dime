'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Loader2, Terminal, BotMessageSquare } from 'lucide-react';
import ResearchReportViewer from '@/components/research/ResearchReportViewer';
import SimulationSetup from '@/components/research/SimulationSetup';
import CustomAgentConfigurator from '@/components/research/CustomAgentConfigurator';
import DraftBoardViewer from '@/components/research/DraftBoardViewer';
import StatComparisonTool from '@/components/research/StatComparisonTool';
import GameAnalysisViewer from '@/components/research/GameAnalysisViewer';
import PlayerScoutingReportGenerator from '@/components/research/PlayerScoutingReportGenerator';
import { useResearchSSE } from '@/lib/hooks/useResearchSSE';
import { ResearchInputForm } from '@/components/research/ResearchInputForm';
import { ReportSectionSelector } from '@/components/research/ReportSectionSelector';

// This defines the sections available for the user to customize in the report.
// It's also used to initialize the default selected sections.
const reportSections = [
    { id: 'executive_summary', label: 'Executive Summary' },
    { id: 'key_stat_cards', label: 'Key Stat Cards' },
    { id: 'career_stats', label: 'Career Stats' },
    { id: 'current_stats', label: 'Current Season Stats' },
    { id: 'gamelog', label: 'Game Logs (Current Season)' },
    { id: 'awards', label: 'Awards' },
    { id: 'profile', label: 'Player Profile (Highs/Totals)' },
    { id: 'hustle', label: 'Hustle Stats' },
    { id: 'defense', label: 'Defensive Stats' },
    { id: 'shooting', label: 'Shooting (Shotchart)' },
    { id: 'passing', label: 'Passing Stats' },
    { id: 'rebounding', label: 'Rebounding Stats' },
    { id: 'clutch', label: 'Clutch Stats' },
    { id: 'analysis', label: 'YOY Analysis' }, // If applicable
    { id: 'insights', label: 'Player Insights' }, // If applicable
    { id: 'comparative_analysis', label: 'Comparative Analysis (if applicable)' },
    { id: 'historical_context', label: 'Historical Context/Trends' },
    { id: 'visualizations', label: 'Visualizations (Charts/Graphs)' },
    { id: 'strengths_weaknesses', label: 'Strengths & Weaknesses' },
    { id: 'potential_impact', label: 'Potential Impact/Outlook' },
    { id: 'data_sources', label: 'Data Sources & Methodology' },
];

interface PageSpecificState {
  topic: string;
  selectedSections: string[];
  promptSuggestions: string[];
  isSuggesting: boolean;
}

export default function ResearchPage() {
  const [pageState, setPageState] = useState<PageSpecificState>({
    topic: '',
    selectedSections: reportSections.map(s => s.id),
    promptSuggestions: [],
    isSuggesting: false,
  });

  const { 
    reportContent, 
    followUpSuggestions, 
    isLoading, 
    error, 
    startResearchStream 
  } = useResearchSSE();

  const reportEndRef = useRef<HTMLDivElement | null>(null);
  const topicTextareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (reportContent && reportEndRef.current) {
      reportEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [reportContent]);

  const handleFetchPromptSuggestions = async () => {
    let promptToSend = pageState.topic;
    const textarea = topicTextareaRef.current;
    if (textarea && textarea.selectionStart !== textarea.selectionEnd) {
      promptToSend = textarea.value.substring(textarea.selectionStart, textarea.selectionEnd);
    }
    setPageState((prev) => ({ ...prev, isSuggesting: true, promptSuggestions: []}));
    try {
      const response = await fetch('/api/v1/research/prompt-suggestions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_prompt: promptToSend }),
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const suggestions: string[] = await response.json();
      setPageState((prev) => ({ ...prev, promptSuggestions: suggestions, isSuggesting: false }));
    } catch (fetchError) {
      console.error('Failed to fetch prompt suggestions:', fetchError);
      setPageState((prev) => ({ ...prev, isSuggesting: false, promptSuggestions: [] })); 
    }
  };

  const handleSectionChange = (sectionId: string, checked: boolean) => {
    setPageState((prev) => {
      const newSelectedSections = checked
        ? [...prev.selectedSections, sectionId]
        : prev.selectedSections.filter(id => id !== sectionId);
      return { ...prev, selectedSections: newSelectedSections };
    });
  };

  const handlePromptSuggestion = (suggestion: string) => {
    setPageState((prev) => ({
      ...prev,
      topic: suggestion,
      promptSuggestions: [],
    }));
  };

  const handleTopicChange = (newTopic: string) => {
    setPageState(prev => ({ ...prev, topic: newTopic }));
  };

  const handleSubmit = useCallback(() => {
    startResearchStream(pageState.topic, pageState.selectedSections);
  }, [pageState.topic, pageState.selectedSections, startResearchStream]);

  return (
    <div className="container mx-auto p-4 space-y-6 max-w-5xl">
      <header className="text-center space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">AI-Powered Research Assistant</h1>
        <p className="text-muted-foreground">
          Generate comprehensive research reports on NBA players, teams, or concepts.
        </p>
      </header>

      <Card className="shadow-lg">
        <CardContent className="p-6 space-y-6">
          <ResearchInputForm
            topic={pageState.topic}
            onTopicChange={handleTopicChange}
            onFetchPromptSuggestions={handleFetchPromptSuggestions}
            promptSuggestions={pageState.promptSuggestions}
            onPromptSuggestionClick={handlePromptSuggestion}
            isLoading={isLoading}
            isSuggesting={pageState.isSuggesting}
            textareaRef={topicTextareaRef}
          />

          <ReportSectionSelector
            reportSections={reportSections}
            selectedSections={pageState.selectedSections}
            onSectionChange={handleSectionChange}
            isLoading={isLoading}
          />

          <Button 
            onClick={handleSubmit} 
            disabled={isLoading || !pageState.topic.trim()}
            className="w-full text-lg py-6"
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                Generating Report...
              </>
            ) : (
              'Generate Comprehensive Report'
            )}
          </Button>

          {error && (
            <Alert variant="destructive">
              <Terminal className="h-4 w-4" />
              <AlertTitle>Error Generating Report</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      <Tabs defaultValue="report" className="w-full">
        <TabsList className="grid w-full grid-cols-3 md:grid-cols-7 mb-4">
          <TabsTrigger value="report" disabled={!reportContent && !isLoading && !error}>Research Report</TabsTrigger>
          <TabsTrigger value="simulation">Simulation</TabsTrigger>
          <TabsTrigger value="customAgent">Custom Agent</TabsTrigger>
          <TabsTrigger value="draftBoard">Draft Board</TabsTrigger>
          <TabsTrigger value="statComparison">Stat Comparison</TabsTrigger>
          <TabsTrigger value="gameAnalysis">Game Analysis</TabsTrigger>
          <TabsTrigger value="scoutingReport">Scouting Report</TabsTrigger>
        </TabsList>

        <TabsContent value="report">
          {isLoading && !reportContent && (
            <Card className="p-6 text-center">
              <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
              <p className="text-muted-foreground">Generating your report, please wait...</p>
            </Card>
          )}
          {reportContent && (
            <ResearchReportViewer reportContent={reportContent} />
          )}
          {!isLoading && followUpSuggestions.length > 0 && (
            <Card className="mt-4 p-4">
              <h3 className="text-md font-semibold mb-2">Follow-up Suggestions:</h3>
              <div className="flex flex-wrap gap-2">
                {followUpSuggestions.map((suggestion, index) => (
                  <Button key={index} variant="outline" size="sm" onClick={() => handlePromptSuggestion(suggestion)}>
                    {suggestion}
                  </Button>
                ))}
              </div>
            </Card>
          )}
          {!isLoading && !reportContent && !error && (
             <Card className="p-6 text-center">
                <BotMessageSquare className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                <p className="text-muted-foreground">Your generated report will appear here once you submit a topic.</p>
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
      <div ref={reportEndRef} />
    </div>
  );
} 