"use client";

import * as React from "react"; // Keep for local input state & effect
import { ScrollArea } from "@/components/ui/scroll-area";
// Remove Resizable components
// Import the CHAT hook and specific components needed
import { useAgentChatSSE, ChatMessage } from "@/lib/hooks/useAgentChatSSE"; // Switch hook
import { PromptInputForm } from "@/components/agent/PromptInputForm";
import { ChatMessageDisplay } from "@/components/agent/ChatMessageDisplay"; // Import message display
import { ErrorDisplay } from "@/components/agent/ErrorDisplay"; // Keep for potential top-level errors

// Agent Dashboard Page Content
export default function AgentDashboardPage() {
  // Local state for the controlled input
  const [inputValue, setInputValue] = React.useState("");

  // Use the CHAT SSE hook
  const {
    isLoading,
    error,
    // progress, // Progress might be handled differently now
    chatHistory, // Get chat history
    // resultData, // Not using structured data display for now
    submitPrompt,
    closeConnection,
  } = useAgentChatSSE({
    apiUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/ask_team", // Fallback URL
  });

  // Ref for scrolling chat area
  const scrollAreaRef = React.useRef<HTMLDivElement>(null);

  // Handle form submission
  const handleFormSubmit = (e?: React.FormEvent<HTMLFormElement>) => {
    if (e) e.preventDefault();
    submitPrompt(inputValue);
    setInputValue(""); // Clear input after submission
  };

  // Effect to scroll down when chat history updates
  React.useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTo({ top: scrollAreaRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [chatHistory]);

  // Effect to clean up SSE connection on component unmount
  React.useEffect(() => {
    return () => {
      closeConnection();
    };
  }, [closeConnection]);

  // This component now renders *only* the content area within the main layout
  return (
    // Main container with flex column layout
    <div className="flex flex-col h-full max-h-full"> {/* Ensure it fills height */}
      {/* Optional: Display top-level errors */}
      {error && !isLoading && <ErrorDisplay error={error} />}

      {/* Scrollable Chat History Area */}
      <ScrollArea className="flex-1 p-4" ref={scrollAreaRef}>
        <div className="space-y-4">
          {chatHistory.map((message, index) => (
            <ChatMessageDisplay key={index} message={message} />
          ))}
          {/* Optional: Show loading indicator at the end */}
          {isLoading && (
             <div className="flex justify-start">
                <div className="p-2 text-sm text-muted-foreground">Agent is thinking...</div>
             </div>
          )}
        </div>
      </ScrollArea>

      {/* Input Form Area */}
      <div className="p-4 border-t">
        <PromptInputForm
          inputValue={inputValue}
          onInputChange={setInputValue}
          onSubmit={handleFormSubmit}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}
