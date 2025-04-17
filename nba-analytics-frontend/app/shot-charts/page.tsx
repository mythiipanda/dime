"use client";

import * as React from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { Skeleton } from "@/components/ui/skeleton"; // Keep Skeleton for loading state
// Import the hook and new components
import { useAgentChatSSE } from "@/lib/hooks/useAgentChatSSE";
import { PromptInputForm } from "@/components/agent/PromptInputForm";
import { ErrorDisplay } from "@/components/agent/ErrorDisplay";
import { ChatMessageDisplay } from "@/components/agent/ChatMessageDisplay";

// Agent Dashboard Page Content
// Rename component to reflect its purpose
export default function ShotChartChatPage() {
  // Local state for the controlled input
  const [inputValue, setInputValue] = React.useState("");
  const messagesEndRef = React.useRef<HTMLDivElement | null>(null); // Ref for auto-scrolling

  // Use the custom hook for SSE logic and state management
  const {
    isLoading,
    error,
    chatHistory, // Use chatHistory from hook
    // resultData, // Keep if structured data is needed later
    submitPrompt,
    closeConnection,
  } = useAgentChatSSE({ // Use the new chat-specific hook
    apiUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/ask_team", // Use env variable
  });

  // Handle form submission - Takes prompt string directly
  const handleFormSubmit = (submittedPrompt: string) => {
    submitPrompt(submittedPrompt);
    setInputValue(""); // Clear input after submission
  };

  // Effect to clean up SSE connection on component unmount
  React.useEffect(() => {
    return () => {
      closeConnection();
    };
  }, [closeConnection]);

  // Effect for auto-scrolling
  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]); // Run whenever chatHistory changes

  // This component now renders *only* the content area within the main layout
  return (
    <ResizablePanelGroup direction="vertical" className="h-full"> {/* Use h-full to fill parent */}
      <ResizablePanel defaultSize={75} className="flex flex-col"> {/* Main results area */}
        {/* Scrollable Results Area */}
        <main className="flex flex-1 flex-col gap-2 p-2 lg:gap-3 lg:p-3"> {/* Removed overflow-hidden */}
          <ScrollArea className="flex-1 rounded-lg border p-2"> {/* Reduced padding */}
            {/* Use page title specific to shot charts */}
            <h2 className="mb-4 text-lg font-semibold">Shot Chart Analysis Chat</h2>
            {/* Render using extracted components */}
            <div className="space-y-4">
              {/* Display Chat History */}
              <div className="space-y-4 mb-4">
                {chatHistory.map((message, index) => (
                  <ChatMessageDisplay key={index} message={message} />
                ))}
                {/* Empty div at the end of messages for auto-scrolling */}
                <div ref={messagesEndRef} />
              </div>

              {/* Display Loading Indicator */}
              {isLoading && (
                 <div className="flex justify-start mt-4">
                    <Skeleton className="h-10 w-16 rounded-lg" />
                 </div>
              )}

              {/* Display Error Alert */}
              <ErrorDisplay error={error} />

              {/* Initial Placeholder */}
              {chatHistory.length === 0 && !isLoading && !error && (
                 <div className="flex flex-1 items-center justify-center rounded-lg border border-dashed shadow-sm p-4">
                   <div className="flex flex-col items-center gap-1 text-center">
                     <h3 className="text-2xl font-bold tracking-tight">
                       Ask about Shot Charts
                     </h3>
                     <p className="text-sm text-muted-foreground">
                       Enter a player and season (e.g., "LeBron James 2023-24 shot chart") below. {/* Escaped quotes */}
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
           {/* Use PromptInputForm component */}
           <PromptInputForm
             onSubmit={handleFormSubmit}
             isLoading={isLoading}
           />
         </div>
      </ResizablePanel>
    </ResizablePanelGroup>
  ); // End of return statement

  // Auto-scrolling effect is now handled within the main component body
  // The messagesEndRef div is rendered within the chat history mapping

} // End of ShotChartChatPage component function
