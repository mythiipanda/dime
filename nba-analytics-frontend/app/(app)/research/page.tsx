'use client';

import { useState, useRef, useEffect } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { SendHorizonal, Loader2, Sparkles, Search, ChevronsUpDown } from 'lucide-react';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import ResearchReportViewer from '@/components/research/ResearchReportViewer';

// Placeholder for the eventual report viewer component
// import ResearchReportViewer from '@/components/research/ResearchReportViewer';

type ResearchType = 'player-deep-dive' | 'team-analysis' | 'player-comparison' | '';

export default function ResearchPage() {
  // State for structured input
  const [researchType, setResearchType] = useState<ResearchType>('');
  const [playerA, setPlayerA] = useState<string>('');
  const [playerB, setPlayerB] = useState<string>('');
  const [teamName, setTeamName] = useState<string>('');
  // const [topic, setTopic] = useState<string>(''); // Keep if needed for other types or fallback
  
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  // Separate state for accumulating report and final suggestions
  const [currentReportContent, setCurrentReportContent] = useState<string>('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [intermediateSteps, setIntermediateSteps] = useState<any[]>([]);

  // Ref to manage the fetch controller
  const abortControllerRef = useRef<AbortController | null>(null);

  // Cleanup function
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort(); // Abort fetch on unmount
    };
  }, []);

  const handleResearchSubmit = async (event?: React.FormEvent<HTMLFormElement>, researchTopic: string = '') => {
    event?.preventDefault();
    
    // Construct prompt based on research type
    let constructedTopic = '';
    let isValid = false;
    switch (researchType) {
        case 'player-deep-dive':
            if (playerA) {
                constructedTopic = `Generate a deep dive research report on player: ${playerA}. Include their basic info, current season stats (if applicable), career overview, strengths, and weaknesses.`;
                isValid = true;
            }
            break;
        case 'team-analysis':
            if (teamName) {
                constructedTopic = `Provide a detailed analysis of the ${teamName} for the current season. Include roster overview, key stats (offensive/defensive ratings, pace), recent performance trends, and overall outlook.`;
                isValid = true;
            }
            break;
        case 'player-comparison':
            if (playerA && playerB) {
                constructedTopic = `Compare and contrast players ${playerA} and ${playerB}. Focus on their statistical output (scoring, playmaking, rebounding, efficiency), playstyles, and impact on their respective teams.`;
                isValid = true;
            }
            break;
        default:
            setError("Please select a research type and fill in the required fields.");
            return;
    }

    if (!isValid || isLoading) {
        if (!isValid) setError("Please fill in all required fields for the selected research type.");
        return;
    } 

    // Abort previous request if any
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();

    setIsLoading(true);
    setError(null);
    setCurrentReportContent(''); 
    setSuggestions([]);
    setIntermediateSteps([]); 

    console.log(`Starting research type: "${researchType}" with topic: "${constructedTopic}"`);

    try {
      const response = await fetch('/api/v1/research', { 
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream', 
        },
        body: JSON.stringify({ topic: constructedTopic }), // Send the constructed topic
        signal: abortControllerRef.current.signal, 
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      // Process the stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          console.log('Stream finished.');
          break; // Exit loop when stream is done
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || ''; // Keep the last (potentially incomplete) message in buffer

        for (const line of lines) {
          if (!line.trim()) continue;

          let event = 'message'; // Default event type
          let data = '';
          const eventMatch = line.match(/^event: (.*)$/m);
          if (eventMatch) {
            event = eventMatch[1].trim();
          }
          const dataMatch = line.match(/^data: (.*)$/m);
          if (dataMatch) {
            data = dataMatch[1].trim();
          }

          if (!data) continue;

          try {
            const parsedData = JSON.parse(data);
            console.log('Received SSE Event:', event, 'Data:', parsedData);

            if (event === 'message') {
              const messageEvent = parsedData.event; 
              const messageContent = parsedData.content;

              // Revert: Append to report content if it's a response chunk
              if (messageEvent === 'RunResponse' && typeof messageContent === 'string') {
                setCurrentReportContent((prev) => prev + messageContent);
              }
              
              // Store intermediate steps 
              if (messageEvent !== 'RunResponse' && messageEvent !== 'RunCompleted') { 
                setIntermediateSteps(prev => [...prev, parsedData]);
              }

            // Revert: Handle suggestions event
            } else if (event === 'suggestions') {
              if (parsedData.suggestions && Array.isArray(parsedData.suggestions)) {
                 setSuggestions(parsedData.suggestions);
                 console.log("Received suggestions:", parsedData.suggestions);
              } 
            } else if (event === 'error') {
              setError(parsedData.content || 'An error occurred in the stream.');
              abortControllerRef.current?.abort(); 
              break; 
            }
          } catch (parseError) {
            console.error('Failed to parse SSE data:', data, parseError);
            // Handle non-JSON data or parse errors if necessary
          }
        }
         if (error) break; // Exit outer loop if an error event was received
      }

    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
         console.log('Research request aborted.');
      } else {
         console.error('Research request failed:', err);
         setError(err instanceof Error ? err.message : 'An unknown error occurred during fetch.');
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null; // Clear the controller
    }
  };

  // Restore suggestion handler
  const handleSuggestionClick = (suggestion: string) => {
     handleResearchSubmit(undefined, suggestion); // Trigger research with the suggestion
  };

  const renderInputFields = () => {
      switch (researchType) {
          case 'player-deep-dive':
              return (
                  <div className="space-y-2">
                      <Label htmlFor="playerA">Player Name</Label>
                      <Input id="playerA" placeholder="e.g., LeBron James" value={playerA} onChange={e => setPlayerA(e.target.value)} disabled={isLoading} />
                  </div>
              );
          case 'team-analysis':
              return (
                  <div className="space-y-2">
                      <Label htmlFor="teamName">Team Name / Abbreviation</Label>
                      <Input id="teamName" placeholder="e.g., Lakers or LAL" value={teamName} onChange={e => setTeamName(e.target.value)} disabled={isLoading} />
                  </div>
              );
          case 'player-comparison':
              return (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                          <Label htmlFor="playerA">Player A</Label>
                          <Input id="playerA" placeholder="e.g., Stephen Curry" value={playerA} onChange={e => setPlayerA(e.target.value)} disabled={isLoading} />
                      </div>
                      <div className="space-y-2">
                          <Label htmlFor="playerB">Player B</Label>
                          <Input id="playerB" placeholder="e.g., Damian Lillard" value={playerB} onChange={e => setPlayerB(e.target.value)} disabled={isLoading} />
                      </div>
                  </div>
              );
          default:
              return <p className="text-sm text-muted-foreground">Select a research type to begin.</p>;
      }
  };

  return (
    <div className="flex flex-col h-full p-4 md:p-6 space-y-4 bg-background text-foreground"> {/* Use theme variables */}
      {/* Header */}
      <div className="flex items-center space-x-3 mb-2">
        <Sparkles className="w-6 h-6 text-primary" /> {/* Use theme variable */} 
        <h1 className="text-2xl font-semibold tracking-tight">
          NBA Research Lab
        </h1>
      </div>

      {/* Input Area - Revised Structure */}
      <Card className="sticky top-0 z-10 border-border bg-card shadow-sm"> {/* Use theme variables */}
         <CardContent className="pt-6">
            <form onSubmit={handleResearchSubmit} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                    {/* Research Type Selector */}
                    <div className="space-y-2 md:col-span-1">
                        <Label htmlFor="researchType">Research Type</Label>
                        <Select value={researchType} onValueChange={(value: ResearchType) => setResearchType(value)} disabled={isLoading}>
                            <SelectTrigger id="researchType">
                                <SelectValue placeholder="Select type..." />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="player-deep-dive">Player Deep Dive</SelectItem>
                                <SelectItem value="team-analysis">Team Analysis</SelectItem>
                                <SelectItem value="player-comparison">Player Comparison</SelectItem>
                                {/* Add more types later */}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Dynamic Input Fields */} 
                    <div className="md:col-span-2">
                        {renderInputFields()}
                    </div>
                </div>

                {/* Submit Button */} 
                <div className="flex justify-end pt-2">
                     <Button 
                         type="submit" 
                         disabled={isLoading || !researchType} // Disable if no type selected or loading
                         className="min-w-[120px] group"
                     >
                         {isLoading ? (
                             <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                         ) : (
                             <Search className="mr-2 h-4 w-4 transition-transform group-hover:scale-110" />
                         )}
                         <span>{isLoading ? 'Researching...' : 'Generate Report'}</span>
                     </Button>
                 </div>
            </form>
         </CardContent>
      </Card>

      {/* Report Display Area */}
      <div className="flex-grow overflow-y-auto space-y-4 pr-2 scrollbar-thin scrollbar-thumb-muted scrollbar-track-transparent"> {/* Adjusted scrollbar */}
        {/* Loading Indicator */}
        {isLoading && !currentReportContent && ( // Revert condition
          <div className="flex items-center justify-center h-60 text-muted-foreground">
            <Loader2 className="mr-3 h-6 w-6 animate-spin text-primary" />
            <span>Generating research report...</span>
          </div>
        )}
        
        {error && (
         <Card className="border-red-500/50 bg-red-900/20 m-4">
           <CardHeader>
             <CardTitle className="text-red-400">Error</CardTitle>
           </CardHeader>
           <CardContent className="text-red-300">
             <p>Failed to generate report: {error}</p>
           </CardContent>
         </Card>
      )}

        {/* Pass props back to viewer */} 
        {(currentReportContent || suggestions.length > 0 || isLoading || error) && !(!isLoading && !currentReportContent && error && suggestions.length === 0 ) && (
            <ResearchReportViewer 
                reportContent={currentReportContent} // Pass text content 
                suggestions={suggestions}          // Pass suggestions array
                onSuggestionClick={handleSuggestionClick} // Pass handler
                intermediateSteps={intermediateSteps} // Keep passing this
                isLoading={isLoading}
            />
        )}

        {/* Initial state message */} 
        {!isLoading && !currentReportContent && !error && suggestions.length === 0 && (
           <div className="flex items-center justify-center h-60 text-muted-foreground">
             <span>Select a research type and enter details to begin.</span>
           </div>
        )}
      </div>

    </div>
  );
} 