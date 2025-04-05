"use client";

import * as React from "react"; // Keep for local input state & effect
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
// Import the new hook and components
import { useAgentSSE } from "@/lib/hooks/useAgentSSE";
import { PromptInputForm } from "@/components/agent/PromptInputForm";
import { ProgressDisplay } from "@/components/agent/ProgressDisplay";
import { ResultsDisplay } from "@/components/agent/ResultsDisplay";

// Agent Dashboard Page Content
export default function AgentDashboardPage() {
  // Local state for the controlled input
  const [inputValue, setInputValue] = React.useState("");

  // Use the custom hook for SSE logic
  const {
    isLoading,
    response,
    error,
    progress,
    resultData,
    submitPrompt,
    closeConnection, // Get the close function
  } = useAgentSSE({
    apiUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/ask_team", // Fallback URL
  });

  // Handle form submission
  const handleFormSubmit = (e?: React.FormEvent<HTMLFormElement>) => {
    if (e) e.preventDefault();
    submitPrompt(inputValue);
    setInputValue(""); // Clear input after submission
  };

  // Effect to clean up SSE connection on component unmount
  React.useEffect(() => {
    // Return the cleanup function
    return () => {
      closeConnection();
    };
  }, [closeConnection]); // Dependency array includes closeConnection

  // This component now renders *only* the content area within the main layout
  return (
    <ResizablePanelGroup direction="vertical" className="h-full"> {/* Use h-full to fill parent */}
      <ResizablePanel defaultSize={75} className="flex flex-col"> {/* Main results area */}
        {/* Scrollable Results Area */}
        <main className="flex flex-1 flex-col gap-4 overflow-hidden p-4 lg:gap-6 lg:p-6">
          <ScrollArea className="flex-1 rounded-lg border p-4"> {/* Added border */}
            <h2 className="mb-4 text-lg font-semibold">Results</h2>
            {/* Placeholder for Agent Output / Visualizations */}
            <div className="space-y-4">
              {/* Use new components, passing state from hook */}
              <ProgressDisplay progressSteps={progress} />
              <ResultsDisplay
                isLoading={isLoading}
                error={error}
                response={response}
                resultData={resultData}
              />
            </div>
          </ScrollArea>
        </main>
      </ResizablePanel>
      <ResizableHandle withHandle />
      <ResizablePanel defaultSize={25} minSize={15} maxSize={40}> {/* Input/Command area */}
         <div className="flex flex-col h-full p-4 border-t">
           <h2 className="text-lg font-semibold mb-2">Enter Prompt</h2>
           {/* Use new PromptInputForm component */}
           <PromptInputForm
             inputValue={inputValue}
             onInputChange={setInputValue}
             onSubmit={handleFormSubmit}
             isLoading={isLoading}
           />
         </div>
      </ResizablePanel>
    </ResizablePanelGroup>
  );
}
