'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { SendHorizonal, Loader2, Sparkles, Search, ChevronsUpDown, Lightbulb, Terminal, BotMessageSquare } from 'lucide-react';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import ResearchReportViewer from '@/components/research/ResearchReportViewer';
import { Checkbox } from "@/components/ui/checkbox";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// Import the mock components
import SimulationSetup from '@/components/research/SimulationSetup';
import CustomAgentConfigurator from '@/components/research/CustomAgentConfigurator';
import DraftBoardViewer from '@/components/research/DraftBoardViewer';
// Import new mock components
import StatComparisonTool from '@/components/research/StatComparisonTool';
import GameAnalysisViewer from '@/components/research/GameAnalysisViewer';
import PlayerScoutingReportGenerator from '@/components/research/PlayerScoutingReportGenerator';

// Placeholder for the eventual report viewer component
// import ResearchReportViewer from '@/components/research/ResearchReportViewer';

// Define available sections/analysis types
const availableSections = [
    { id: 'basic', label: 'Basic Info' },
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
];

type ResearchType = 'player-deep-dive' | 'team-analysis' | 'player-comparison' | '';

// Simplified research state
interface ResearchState {
  topic: string; 
  // Remove: researchType, playerA, playerB, teamName, gameID
  isLoading: boolean;
  error: string | null;
  reportContent: string | null; // SSE stream content
  followUpSuggestions: string[];
  selectedSections: string[]; // Keep section selection
  // New state for prompt suggestions
  promptSuggestions: string[];
  isSuggesting: boolean; // Loading state for suggestions
}

export default function ResearchPage() {
  const [state, setState] = useState<ResearchState>({
    topic: '',
    // Remove initial state for researchType, playerA, etc.
    isLoading: false,
    error: null,
    reportContent: null,
    followUpSuggestions: [],
    selectedSections: availableSections.map(s => s.id), // Default to all sections
    promptSuggestions: [],
    isSuggesting: false,
  });

  const eventSourceRef = useRef<EventSource | null>(null);
  const reportEndRef = useRef<HTMLDivElement | null>(null); // For scrolling
  const topicTextareaRef = useRef<HTMLTextAreaElement | null>(null); // Ref for the textarea

  // Cleanup function
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        console.log("Closing EventSource connection on unmount.");
        eventSourceRef.current.close();
      }
    };
  }, []);

  // Handler for checkbox changes
  const handleSectionChange = (sectionId: string, checked: boolean) => {
    setState(prev => {
      const newSelectedSections = checked
        ? [...prev.selectedSections, sectionId]
        : prev.selectedSections.filter(id => id !== sectionId);
      return { ...prev, selectedSections: newSelectedSections };
    });
  };

  // --- Fetch Prompt Suggestions (Updated) --- 
  const fetchPromptSuggestions = async () => {
    let promptToSend = state.topic; // Default to the full topic

    // Check for selected text in the textarea
    const textarea = topicTextareaRef.current;
    if (textarea && textarea.selectionStart !== textarea.selectionEnd) {
      promptToSend = textarea.value.substring(textarea.selectionStart, textarea.selectionEnd);
      console.log("Detected selected text, sending snippet for suggestions:", promptToSend);
    } else {
      console.log("No text selected, sending full topic for suggestions:", promptToSend);
      // Optionally handle empty topic case specifically here if needed
      if (!promptToSend) {
         console.log("Topic is empty, backend will provide generic suggestions.");
         // No need to set promptToSend to empty string, backend handles it.
      }
    }

    setState(prev => ({ ...prev, isSuggesting: true, promptSuggestions: [], error: null }));

    try {
      const response = await fetch('/api/v1/research/prompt-suggestions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_prompt: promptToSend }), // Send either full topic or selected snippet
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const suggestions: string[] = await response.json();
      setState(prev => ({ ...prev, promptSuggestions: suggestions, isSuggesting: false }));

    } catch (error) {
      console.error('Failed to fetch prompt suggestions:', error);
      setState(prev => ({
        ...prev,
        error: 'Failed to fetch prompt suggestions.',
        isSuggesting: false,
        promptSuggestions: [],
      }));
    }
  };

  // --- Rename: Use Prompt Suggestion --- 
  const usePromptSuggestion = (suggestion: string) => {
    console.log("Using suggestion:", suggestion);
    // Simply update the main topic input
    setState(prev => ({ 
      ...prev, 
      topic: suggestion, 
      promptSuggestions: [], // Close popover
      isSuggesting: false, // Ensure loading state is off
    }));
  };

  // Main submit handler (simplified)
  const handleSubmit = useCallback(async () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close(); // Close previous connection if any
    }

    setState(prev => ({
      ...prev,
      isLoading: true,
      error: null,
      reportContent: '', // Reset report content
      followUpSuggestions: [],
    }));

    // Reset scroll position (optional)
    // window.scrollTo(0, 0);

    const requestBody = {
      topic: state.topic, // Only send topic
      selected_sections: state.selectedSections,
    };

    console.log('Starting research with:', requestBody);

    try {
      // Connect to the SSE endpoint
      const eventSource = new EventSource(`/api/v1/research/?topic=${encodeURIComponent(state.topic)}&selected_sections=${encodeURIComponent(JSON.stringify(state.selectedSections))}`);
      eventSourceRef.current = eventSource;

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // console.log('SSE message received:', data); // Debug log

          if (data.event === 'suggestions') {
            // Handle final follow-up suggestions
            setState(prev => ({ ...prev, followUpSuggestions: data.suggestions || [] }));
            console.log("Follow-up suggestions received:", data.suggestions);
          } else if (data.event === 'error') {
             // Handle errors from the stream
             console.error("SSE Error:", data.content);
             setState(prev => ({ ...prev, error: data.content || 'An unknown error occurred during research.', isLoading: false }));
             eventSource.close();
             eventSourceRef.current = null;
          } else {
            // Append content chunks to reportContent
            // Ensure content exists and is a string before appending
            const contentChunk = data.content;
            if (typeof contentChunk === 'string') {
              setState(prev => ({ ...prev, reportContent: (prev.reportContent || '') + contentChunk }));
            } else if (contentChunk) {
              // If content is not a string but exists, log it - might need specific handling
              // console.log("Received non-string content chunk:", contentChunk);
            }
            // Add specific handling for Stat Cards or Charts if needed based on data.event or data.type
            // Example:
            // if (data.type === 'stat_card') { /* update state with stat card data */ }
            // if (data.type === 'chart') { /* update state with chart data */ }
          }
        } catch (e) {
          console.error('Error parsing SSE message:', e, 'Raw data:', event.data);
          // Optionally set an error state here
          setState(prev => ({ ...prev, error: 'Error processing research update.', isLoading: false }));
          eventSource.close();
          eventSourceRef.current = null;
        }
      };

      eventSource.onerror = (error) => {
        console.error('EventSource failed:', error);
        setState(prev => ({
          ...prev,
          error: 'Connection to research service failed.',
          isLoading: false,
        }));
        eventSource.close();
        eventSourceRef.current = null;
      };

      eventSource.onopen = () => {
          console.log("SSE connection opened.");
      };

      // The stream will automatically close when done, or handle explicitly if needed
      // We might need a specific 'end' event from the backend to set isLoading = false reliably
      // For now, assume error or suggestions marks the end

    } catch (err) {
      console.error('Failed to initiate research:', err);
      let errorMessage = 'An unknown error occurred.';
      if (err instanceof Error) {
        errorMessage = err.message;
      }
      setState(prev => ({ ...prev, error: errorMessage, isLoading: false }));
    }
  //}, [state.topic, state.researchType, state.playerA, state.playerB, state.teamName, state.gameID, state.selectedSections]);
  // Update dependencies
  }, [state.topic, state.selectedSections]);

   // Effect to scroll to the bottom of the report
   useEffect(() => {
    if (state.reportContent) {
      reportEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [state.reportContent]);

  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        console.log("Closing EventSource connection on unmount.");
        eventSourceRef.current.close();
      }
    };
  }, []);

  // Constants for sections defined outside the component render
  const reportSections = [
    { id: 'executive_summary', label: 'Executive Summary' },
    { id: 'key_stat_cards', label: 'Key Stat Cards' },
    { id: 'comparative_analysis', label: 'Comparative Analysis (if applicable)' },
    { id: 'historical_context', label: 'Historical Context/Trends' },
    { id: 'visualizations', label: 'Visualizations (Charts/Graphs)' },
    { id: 'strengths_weaknesses', label: 'Strengths & Weaknesses' },
    { id: 'potential_impact', label: 'Potential Impact/Outlook' },
    { id: 'data_sources', label: 'Data Sources & Methodology' },
  ];

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

        {/* Research Tab Content */}
        <TabsContent value="research">
            <Card>
              <CardContent className="pt-6 space-y-6">
                {/* --- Input Section --- */}
                <div className="space-y-4">
                  {/* Topic Input */}
                  <div>
                    <Label htmlFor="research-topic" className="text-lg font-semibold mb-2 block">Research Topic / Question</Label>
                    <div className="relative">
                      <Textarea
                        ref={topicTextareaRef}
                        id="research-topic"
                        placeholder="Enter your research topic..."
                        value={state.topic}
                        onChange={(e) => setState({ ...state, topic: e.target.value, error: null })}
                        className="min-h-[100px] text-base p-3 pr-12 w-full"
                        rows={4}
                      />
                      <Popover>
                        <PopoverTrigger asChild>
                          <Button
                            variant="ghost" size="icon"
                            onClick={fetchPromptSuggestions}
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
                                  <CommandItem key={index} onSelect={() => usePromptSuggestion(suggestion)} className="cursor-pointer">
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

                  {/* Report Section Selection */}
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

                {/* --- Action Button --- */}
                <div className="text-center">
            <Button 
                    onClick={handleSubmit}
                    disabled={state.isLoading || !state.topic.trim()}
                    size="lg"
                    className="w-full md:w-auto"
                  >
                    {state.isLoading ? (
                      <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Researching...
                      </>
              ) : (
                      'Run Research'
              )}
            </Button>
                </div>
        </CardContent>
      </Card>

            {/* --- Output Section --- */}
            <div className="mt-6 space-y-6">
              {/* Error Display */}
              {state.error && (
                <Alert variant="destructive">
                  <Terminal className="h-4 w-4" />
                  <AlertTitle>Error</AlertTitle>
                  <AlertDescription>{state.error}</AlertDescription>
                </Alert>
              )}

              {/* Report Viewer */}
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
        
              {/* Follow-up Suggestions */}
              {state.followUpSuggestions.length > 0 && (
                <div>
                  <h3 className="text-xl font-semibold mb-3">Follow-up Suggestions:</h3>
                  <ul className="list-disc pl-5 space-y-2">
                    {state.followUpSuggestions.map((suggestion, index) => (
                      <li key={index} className="text-muted-foreground">
                        <button
                          onClick={() => setState(prev => ({...prev, topic: suggestion, reportContent: null, followUpSuggestions: [] }))}
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

        {/* Stat Comparison Tab Content */}
        <TabsContent value="comparison">
           <StatComparisonTool />
        </TabsContent>

        {/* Game Analysis Tab Content */}
        <TabsContent value="game-analysis">
            <GameAnalysisViewer />
        </TabsContent>
        
        {/* Player Scouting Tab Content */}
        <TabsContent value="scouting">
            <PlayerScoutingReportGenerator />
        </TabsContent>

        {/* Simulation Tab Content */}
        <TabsContent value="simulation">
          <SimulationSetup />
        </TabsContent>

        {/* Custom Agents Tab Content */}
        <TabsContent value="custom-agents">
          <CustomAgentConfigurator />
        </TabsContent>

        {/* Draft Board Tab Content */}
        <TabsContent value="draft-board">
          <DraftBoardViewer />
        </TabsContent>

      </Tabs>

    </div>
  );
} 