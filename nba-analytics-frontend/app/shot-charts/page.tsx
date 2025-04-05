"use client"; // Required for state and event handlers used in Command, Tabs etc.

import * as React from "react";
import ReactMarkdown from 'react-markdown'; // Import ReactMarkdown
import remarkGfm from 'remark-gfm'; // Import remark-gfm for tables, etc.

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea"; // Assuming Textarea is added
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  BotIcon,
  TerminalIcon,
  FileTextIcon,
  BarChartIcon,
  TableIcon,
  SendIcon,
} from "lucide-react";

// Agent Dashboard Page Content
export default function AgentDashboardPage() {
  // Basic state for the command input (replace with actual logic later)
  const [inputValue, setInputValue] = React.useState("");
  const [agentIsThinking, setAgentIsThinking] = React.useState(false);
  // const [agentResponse, setAgentResponse] = React.useState<string | null>(null); // Replaced by chatHistory
  const [agentError, setAgentError] = React.useState<string | null>(null);
  // State for chat history
  interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
  }
  const [chatHistory, setChatHistory] = React.useState<ChatMessage[]>([]);
  const [progressSteps, setProgressSteps] = React.useState<string[]>([]); // State for progress messages
  const eventSourceRef = React.useRef<EventSource | null>(null); // Ref to manage EventSource
  const [resultData, setResultData] = React.useState<any>(null); // To hold structured results
  const messagesEndRef = React.useRef<HTMLDivElement | null>(null); // Ref for auto-scrolling

  const handleCommandSubmit = (e?: React.FormEvent<HTMLFormElement>) => {
    if (e) e.preventDefault();
    if (!inputValue.trim() || agentIsThinking) return; // Don't submit empty or while thinking

    const currentPrompt = inputValue;
    console.log("Submitting prompt:", currentPrompt);
    setInputValue("");
    setAgentIsThinking(true);
    // Add user message to history
    setChatHistory(prev => [...prev, { role: 'user', content: currentPrompt }]);
    setAgentError(null); // Clear previous error
    setResultData(null); // Clear previous structured data
    setProgressSteps(["Connecting to agent..."]); // Initial progress

    // Close existing connection if any
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Create new EventSource connection
    const eventSource = new EventSource(`http://localhost:8000/ask_team?prompt=${encodeURIComponent(currentPrompt)}`); // Send prompt via query param for GET SSE
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      console.log("SSE Message:", event.data);
      try {
        const data = JSON.parse(event.data);
        // Check for error type first
        if (data.type === 'error') {
          console.error("Received error from backend stream:", data.message);
          setAgentError(data.message || "Unknown error from backend stream.");
          setProgressSteps(prev => [...prev, `Error: ${data.message || "Unknown"}`]);
          setAgentIsThinking(false);
          eventSourceRef.current?.close(); // Close connection on error
          eventSourceRef.current = null;
        }
        // Handle agent steps (content chunks)
        else if (data.type === 'agent_step') {
          setChatHistory(prev => {
            const lastMessage = prev[prev.length - 1];
            // If last message is from assistant, append content
            if (lastMessage?.role === 'assistant') {
              return [
                ...prev.slice(0, -1), // All messages except last
                { ...lastMessage, content: lastMessage.content + data.message } // Updated last message
              ];
            } else {
              // Otherwise, add a new assistant message
              return [...prev, { role: 'assistant', content: data.message }];
            }
          });
        }
        // Update progress for other status/tool events
        else if (data.type === 'status' || data.type === 'tool_start' || data.type === 'tool_end' || data.type === 'thinking' || data.type === 'tool_call' || data.type === 'reasoning') {
           // Add specific progress messages based on type if desired
           const progressMessage = data.message || `Processing: ${data.type}`;
           setProgressSteps(prev => [...prev, progressMessage]);
        }
        // Handle other potential structured data types if needed
      } catch (e) {
        console.error("Failed to parse SSE data:", e);
         // Treat as plain text message if parsing fails (could be simple status)
         setProgressSteps(prev => [...prev, event.data]);
      }
    };

     // Listen for specific 'final' event
     eventSource.addEventListener('final', (event: MessageEvent) => { // Add type annotation
       console.log("SSE Final Event:", event.data);
       try {
         const data = JSON.parse(event.data);
         if (data.type === 'final_response') {
           // Always add the final response as a new assistant message
           const finalContent = data.content; // Store content
           setChatHistory(prev => {
             // Explicitly define the role type for the new message
             const newMessage: ChatMessage = { role: 'assistant', content: finalContent };
             const newHistory = [...prev, newMessage];
             console.log("Final handler: Updating chat history with:", newHistory); // Log the intended new state
             return newHistory;
           });
           setProgressSteps(prev => [...prev, "Final response received."]);
           // TODO: Parse final content for structured data and set resultData if needed
           // setResultData(parseStructuredData(finalContent));
         }
       } catch (e) {
         console.error("Failed to parse final SSE data:", e);
         // Don't set agentResponse, maybe add error to chat history?
         setChatHistory(prev => [...prev, { role: 'assistant', content: "Error: Failed to parse final event data." }]);
       }
       setAgentIsThinking(false);
       eventSource.close(); // Close connection on final message
       eventSourceRef.current = null;
     });

    // Handle generic EventSource errors (like connection closed)
    eventSource.onerror = (err) => {
      console.error("EventSource failed:", err);
      // Only set error if we weren't already in a final state (response received or error set)
      // and the connection wasn't closed intentionally.
      // Check if the last message isn't an error and connection still exists
      const lastHistoryMessage = chatHistory[chatHistory.length - 1];
      // Only set error if we were still thinking and hadn't already received an error
      if (agentIsThinking && !agentError) {
         console.error("EventSource connection error or closed unexpectedly.");
         setAgentError("Connection to agent lost or failed.");
         setProgressSteps(prev => [...prev, "Error: Connection lost."]);
         setAgentIsThinking(false);
         eventSourceRef.current = null; // Ensure ref is cleared
      } else {
         console.log("EventSource closed, likely intentionally after 'final' or 'error' event.");
      }
      // Ensure closure regardless
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  };

  // This component now renders *only* the content area within the main layout
  return (
    <ResizablePanelGroup direction="vertical" className="h-full"> {/* Use h-full to fill parent */}
      <ResizablePanel defaultSize={75} className="flex flex-col"> {/* Main results area */}
        {/* Scrollable Results Area */}
        <main className="flex flex-1 flex-col gap-2 p-2 lg:gap-3 lg:p-3"> {/* Removed overflow-hidden */}
          <ScrollArea className="flex-1 rounded-lg border p-2"> {/* Reduced padding */}
            <h2 className="mb-4 text-lg font-semibold">Results</h2>
            {/* Placeholder for Agent Output / Visualizations */}
            <div className="space-y-4">
              {/* Display Progress Steps */}
              {progressSteps.length > 0 && (
                <Card className="mb-4 bg-secondary/50">
                  <CardHeader><CardTitle className="text-sm">Progress</CardTitle></CardHeader>
                  <CardContent className="p-2"> {/* Reduced padding */}
                    <ul className="list-disc pl-4 text-[11px] text-muted-foreground space-y-0.5"> {/* Reduced padding, font size, spacing */}
                      {progressSteps.map((step, index) => <li key={index}>{step}</li>)}
                    </ul>
                  </CardContent>
                </Card>
              )}
              {/* Display Chat History */}
              <div className="space-y-4 mb-4"> {/* Add bottom margin */}
                {chatHistory.map((message, index) => (
                  <div key={index} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <Card className={`max-w-[75%] ${message.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
                      <CardContent className={`p-2 ${message.role === 'assistant' ? 'max-h-[60vh] overflow-y-auto' : ''}`}> {/* Reduced padding */}
                        {message.role === 'assistant' ? (
                          <div className="prose prose-sm dark:prose-invert max-w-none">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {message.content}
                            </ReactMarkdown>
                          </div>
                        ) : (
                          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                ))}
                 {/* Empty div at the end of messages for auto-scrolling */}
                 <div ref={messagesEndRef} />
              </div>

              {/* Display Loading Indicator during thought process */}
              {agentIsThinking && (
                 <div className="flex justify-start mt-4">
                    <Skeleton className="h-10 w-16 rounded-lg" />
                 </div>
              )}

              {/* Display Error Alert if an error occurred */}
              {agentError && (
                 <Alert variant="destructive" className="mt-4">
                   <TerminalIcon className="h-4 w-4" />
                   <AlertTitle>Error</AlertTitle>
                   <AlertDescription>
                     {agentError}
                   </AlertDescription>
                 </Alert>
              )}
               {/* TODO: Re-integrate structured data display (resultData) if needed */}
               {/* This section might need adjustment based on how structured data is handled alongside chat history */}
               {/* {!agentIsThinking && !agentError && resultData && ( ... Tabs component ... )} */}
               {/* Initial Placeholder - Show only if history is empty and not thinking */}
               {chatHistory.length === 0 && !agentIsThinking && !agentError && (
                 <div className="flex flex-1 items-center justify-center rounded-lg border border-dashed shadow-sm p-4">
                   <div className="flex flex-col items-center gap-1 text-center">
                     <h3 className="text-2xl font-bold tracking-tight">
                       Ask the NBA Agent
                     </h3>
                     <p className="text-sm text-muted-foreground">
                       Enter your query below to get started.
                     </p>
                   </div>
                 </div>
               )}
            </div>
          </ScrollArea>
        </main>
      </ResizablePanel>
      <ResizableHandle withHandle />
      <ResizablePanel defaultSize={20} minSize={15} maxSize={35}> {/* Reduced default/max size */}
         <div className="flex flex-col h-full p-2 border-t"> {/* Reduced padding */}
           <h2 className="text-lg font-semibold mb-2">Enter Prompt</h2>
           {/* Wrap input and button in a form */}
           <form onSubmit={handleCommandSubmit} className="flex flex-col flex-1 gap-2">
             <Command className="rounded-lg border shadow-md flex-1">
               <CommandInput
                 placeholder="Type your NBA query here..."
                 value={inputValue}
                 onValueChange={setInputValue}
                 disabled={agentIsThinking} // Disable input while thinking
               />
               {/* We can add CommandList suggestions later */}
               {/* <CommandList> <CommandEmpty>No results.</CommandEmpty> ... </CommandList> */}
             </Command>
             <Button type="submit" className="mt-auto" disabled={agentIsThinking || !inputValue.trim()}> {/* Disable if thinking or input empty */}
               <SendIcon className="mr-2 h-4 w-4" /> Send Prompt
             </Button>
           </form>
         </div>
      </ResizablePanel>
    </ResizablePanelGroup>
  ); // End of return statement

  // Effect for auto-scrolling (Placed before return, inside component)
  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]); // Run whenever chatHistory changes

} // End of AgentDashboardPage component function
