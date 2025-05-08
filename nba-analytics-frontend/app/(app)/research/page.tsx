'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { Command, CommandInput, CommandList, CommandEmpty, CommandGroup, CommandItem } from '@/components/ui/command';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible';
import { Loader2, Terminal, BotMessageSquare, Lightbulb } from 'lucide-react';
import ResearchReportViewer from '@/components/research/ResearchReportViewer';
import SimulationSetup from '@/components/research/SimulationSetup';
import CustomAgentConfigurator from '@/components/research/CustomAgentConfigurator';
import DraftBoardViewer from '@/components/research/DraftBoardViewer';
import StatComparisonTool from '@/components/research/StatComparisonTool';
import GameAnalysisViewer from '@/components/research/GameAnalysisViewer';
import PlayerScoutingReportGenerator from '@/components/research/PlayerScoutingReportGenerator';

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

interface ResearchState {
  topic: string; 
  isLoading: boolean;
  error: string | null;
  reportContent: string | null;
  followUpSuggestions: string[];
  selectedSections: string[];
  promptSuggestions: string[];
  isSuggesting: boolean;
}

export default function ResearchPage() {
  const [state, setState] = useState<ResearchState>({
    topic: '',
    isLoading: false,
    error: null,
    reportContent: null,
    followUpSuggestions: [],
    selectedSections: reportSections.map(s => s.id), // Initialize with all reportSections
    promptSuggestions: [],
    isSuggesting: false,
  });

  const eventSourceRef = useRef<EventSource | null>(null);
  const reportEndRef = useRef<HTMLDivElement | null>(null);
  const topicTextareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Cleanup EventSource on unmount - ONE cleanup effect is sufficient
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        console.log("Closing EventSource connection on unmount.");
        eventSourceRef.current.close();
        eventSourceRef.current = null; // Explicitly nullify after closing
      }
    };
  }, []); // Empty dependency array means this runs once on mount and cleanup on unmount

  // --- Fetch Prompt Suggestions ---
  const handleFetchPromptSuggestions = async () => {
    let promptToSend = state.topic;
    const textarea = topicTextareaRef.current;
    if (textarea && textarea.selectionStart !== textarea.selectionEnd) {
      promptToSend = textarea.value.substring(textarea.selectionStart, textarea.selectionEnd);
    } 
    setState((prev) => ({ ...prev, isSuggesting: true, promptSuggestions: [], error: null }));
    try {
      const response = await fetch('/api/v1/research/prompt-suggestions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_prompt: promptToSend }),
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const suggestions: string[] = await response.json();
      setState((prev) => ({ ...prev, promptSuggestions: suggestions, isSuggesting: false }));
    } catch (error) {
      console.error('Failed to fetch prompt suggestions:', error);
      setState((prev) => ({ ...prev, error: 'Failed to fetch prompt suggestions.', isSuggesting: false, promptSuggestions: [] }));
    }
  };

  // Handler for checkbox changes
  const handleSectionChange = (sectionId: string, checked: boolean) => {
    setState((prev) => {
      const newSelectedSections = checked
        ? [...prev.selectedSections, sectionId]
        : prev.selectedSections.filter(id => id !== sectionId);
      return { ...prev, selectedSections: newSelectedSections };
    });
  };

  const handlePromptSuggestion = (suggestion: string) => {
    setState((prev) => ({ 
      ...prev, 
      topic: suggestion, 
      promptSuggestions: [],
      // isSuggesting: false, // isSuggesting should be false after suggestions are loaded
    }));
  };

  // Main submit handler
  const handleSubmit = useCallback(async () => {
    if (eventSourceRef.current) {
      console.log("Closing previous EventSource connection.");
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    setState((prev) => ({
      ...prev,
      isLoading: true,
      error: null,
      reportContent: '',
      followUpSuggestions: [],
    }));

    const requestBody = {
      topic: state.topic,
      selected_sections: state.selectedSections,
    };
    console.log('Starting research with:', requestBody); // Keep for debugging

    try {
      // Note: SSE GET request parameters must be URL encoded.
      const queryParams = new URLSearchParams({
        topic: state.topic,
        selected_sections: JSON.stringify(state.selectedSections),
      });
      const eventSource = new EventSource(`/api/v1/research/?${queryParams.toString()}`);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
          console.log("SSE connection opened.");
          // Clear error on successful (re)connection if one existed from previous attempt
          if(state.error) setState(prev => ({...prev, error: null})); 
      };

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === 'suggestions') {
            setState((prev) => ({ ...prev, followUpSuggestions: data.suggestions || [], isLoading: false })); // Stop loading on suggestions
            console.log("Follow-up suggestions received:", data.suggestions);
            if (eventSourceRef.current) eventSourceRef.current.close(); // Close after final suggestions
          } else if (data.event === 'error') {
             console.error("SSE Error:", data.content);
             setState((prev) => ({ ...prev, error: data.content || 'An unknown error occurred during research.', isLoading: false }));
             if (eventSourceRef.current) eventSourceRef.current.close();
          } else if (data.event === 'final_content_end') { // Assume backend sends this event
             console.log("SSE stream indicated end of content.");
             setState((prev) => ({ ...prev, isLoading: false }));
             if (eventSourceRef.current) eventSourceRef.current.close();
          }else {
            const contentChunk = data.content;
            if (typeof contentChunk === 'string') {
              setState((prev) => ({ ...prev, reportContent: (prev.reportContent || '') + contentChunk }));
            } 
            // Add specific handling for Stat Cards or Charts based on data.type/data.event if implemented
          }
        } catch (e) {
          console.error('Error parsing SSE message:', e, 'Raw data:', event.data);
          setState((prev) => ({ ...prev, error: 'Error processing research update.', isLoading: false }));
          if (eventSourceRef.current) eventSourceRef.current.close();
        }
      };

      eventSource.onerror = (errorEvent) => {
        console.error('EventSource failed:', errorEvent);
        setState((prev) => ({
          ...prev,
          error: 'Connection to research service failed. Please try again.',
          isLoading: false,
        }));
        if (eventSourceRef.current) eventSourceRef.current.close();
      };

    } catch (err) {
      console.error('Failed to initiate research (setup error):', err);
      setState((prev) => ({ ...prev, error: err instanceof Error ? err.message : 'Failed to start research.', isLoading: false }));
    }
  }, [state.topic, state.selectedSections, state.error]); // Added state.error to dependencies of handleSubmit for onopen error clearing

   // Effect to scroll to the bottom of the report
   useEffect(() => {
    if (state.reportContent && reportEndRef.current) {
      reportEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [state.reportContent]);

  return (
    <div className="container mx-auto p-4 md:p-8 max-w-5xl">
      <h1 className="text-3xl font-bold mb-6 text-center">NBA Research Lab</h1>

      <Tabs defaultValue="research" className="w-full">
        <TabsList className="grid w-full grid-cols-7 mb-6">
          <TabsTrigger value="research">Research</TabsTrigger>
          <TabsTrigger value="comparison">Comparison</TabsTrigger>
          <TabsTrigger value="game-analysis">Game Analysis</TabsTrigger>
          <TabsTrigger value="scouting">Scouting</TabsTrigger>
          <TabsTrigger value="simulation">Simulation</TabsTrigger>
          <TabsTrigger value="custom-agents">Custom Agents</TabsTrigger>
          <TabsTrigger value="draft-board">Draft Board</TabsTrigger>
        </TabsList>

        <TabsContent value="research">
            <Card>
              <CardContent className="pt-6 space-y-6">
                {/* Input Section */}
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="research-topic" className="text-lg font-semibold mb-2 block">Research Topic / Question</Label>
                    <div className="relative">
                      <Textarea
                        ref={topicTextareaRef}
                        id="research-topic"
                        placeholder="Enter your research topic..."
                        value={state.topic}
                        onChange={(e) => setState((prev) => ({ ...prev, topic: e.target.value, error: null }))}
                        className="min-h-[100px] text-base p-3 pr-12 w-full"
                        rows={4}
                      />
                      <Popover>
                        <PopoverTrigger asChild>
                          <Button
                            variant="ghost" size="icon"
                            onClick={handleFetchPromptSuggestions}
                            disabled={state.isSuggesting || state.isLoading}
                            className="absolute top-2 right-2 h-8 w-8"
                            aria-label="Suggest prompt improvements"
                          >
                            <Lightbulb className={`h-5 w-5 ${state.isSuggesting ? 'animate-pulse text-yellow-500' : ''}`} />
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-[400px] p-0">
                          <Command>
                            <CommandInput placeholder="Filter suggestions..." />
                            <CommandList>
                              <CommandEmpty>{state.isSuggesting ? "Loading suggestions..." : "No suggestions found."}</CommandEmpty>
                              <CommandGroup heading="Prompt Suggestions">
                                {state.promptSuggestions.map((suggestion, index) => (
                                  <CommandItem key={index} onSelect={() => handlePromptSuggestion(suggestion)} className="cursor-pointer">
                                    {suggestion}
                                  </CommandItem>
                                ))}
                              </CommandGroup>
                            </CommandList>
                          </Command>
                        </PopoverContent>
                      </Popover>
                    </div>
                  </div>

                  <Collapsible className="border rounded-md p-4">
                    <CollapsibleTrigger asChild>
                      <Button variant="outline" className="w-full justify-between">
                        <span>Customize Report Sections ({state.selectedSections.length} selected)</span>
                      </Button>
                    </CollapsibleTrigger>
                    <CollapsibleContent className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {reportSections.map((section) => (
                        <div key={section.id} className="flex items-center space-x-2">
                          <Checkbox
                            id={section.id}
                            checked={state.selectedSections.includes(section.id)}
                            onCheckedChange={(checked) => handleSectionChange(section.id, !!checked)}
                          />
                          <Label htmlFor={section.id} className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                            {section.label}
                          </Label>
                        </div>
                      ))}
                    </CollapsibleContent>
                  </Collapsible>
                </div>

                {/* Action Button */}
                <div className="text-center">
                  <Button 
                    onClick={handleSubmit}
                    disabled={state.isLoading || !state.topic.trim()}
                    size="lg"
                    className="w-full md:w-auto"
                  >
                    {state.isLoading && !state.reportContent ? (
                      <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Researching...</>
                    ) : state.isLoading && state.reportContent ? (
                      <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Receiving Report...</>
                    ) : (
                      'Run Research'
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Output Section */}
            <div className="mt-6 space-y-6">
              {state.error && (
                <Alert variant="destructive">
                  <Terminal className="h-4 w-4" />
                  <AlertTitle>Error</AlertTitle>
                  <AlertDescription>{state.error}</AlertDescription>
                </Alert>
              )}

              {state.reportContent !== null && (
                <div className="border rounded-lg p-4 md:p-6 bg-card text-card-foreground shadow-sm">
                  <h2 className="text-2xl font-semibold mb-4 flex items-center">
                    <BotMessageSquare className="mr-2 h-6 w-6" />
                    Research Report
                  </h2>
                  <ResearchReportViewer reportContent={state.reportContent} />
                  <div ref={reportEndRef} />
                </div>
              )}
              
              {!state.isLoading && state.followUpSuggestions.length > 0 && (
                <div>
                  <h3 className="text-xl font-semibold mb-3">Follow-up Suggestions:</h3>
                  <ul className="list-disc pl-5 space-y-2">
                    {state.followUpSuggestions.map((suggestion, index) => (
                      <li key={index} className="text-muted-foreground">
                        <button
                          onClick={() => {
                            setState((prev) => ({...prev, topic: suggestion, reportContent: null, followUpSuggestions: [], error: null}));
                            // Optionally, trigger handleSubmit directly or let user click Run Research
                            // handleSubmit(); // If auto-submit is desired
                          }}
                          className="text-left hover:text-primary underline transition-colors duration-200"
                        >
                          {suggestion}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
        </TabsContent>
        
        {/* Other TabsContent for StatComparisonTool, GameAnalysisViewer etc. */}
        <TabsContent value="comparison"><StatComparisonTool /></TabsContent>
        <TabsContent value="game-analysis"><GameAnalysisViewer /></TabsContent>
        <TabsContent value="scouting"><PlayerScoutingReportGenerator /></TabsContent>
        <TabsContent value="simulation"><SimulationSetup /></TabsContent>
        <TabsContent value="custom-agents"><CustomAgentConfigurator /></TabsContent>
        <TabsContent value="draft-board"><DraftBoardViewer /></TabsContent>

      </Tabs>
    </div>
  );
} 