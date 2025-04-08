"use client";

import * as React from "react"; // Keep for local input state & effect
import { ScrollArea } from "@/components/ui/scroll-area";
// Remove Resizable components
// Import the CHAT hook and specific components needed
import { useAgentChatSSE } from "@/lib/hooks/useAgentChatSSE"; // Removed unused ChatMessage
import { PromptInputForm } from "@/components/agent/PromptInputForm";
import { ChatMessageDisplay } from "@/components/agent/ChatMessageDisplay";
import { InitialChatScreen } from "@/components/agent/InitialChatScreen"; // Import new component
import { ErrorDisplay } from "@/components/agent/ErrorDisplay"; // Keep for potential top-level errors

// Agent Dashboard Page Content
export default function AgentDashboardPage() {
  // Local state for the controlled input
  const [inputValue, setInputValue] = React.useState("");

  // Use the CHAT SSE hook
  const {
    isLoading,
    error,
    chatText,  // Get live chat text
    chatHistory,
    // resultData, // Not using structured data display for now
    submitPrompt,
    closeConnection,
  } = useAgentChatSSE({
    apiUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  });

  console.log("Render: isLoading", isLoading);
  console.log("Render: error", error);
  console.log("Render: chatText", chatText);
  console.log("Render: chatHistory", chatHistory);

  // Ref for scrolling chat area
  const scrollAreaRef = React.useRef<HTMLDivElement>(null);

  // Handle form submission
  const handleFormSubmit = (e?: React.FormEvent<HTMLFormElement>) => {
    if (e) e.preventDefault();
    submitPrompt(inputValue);
    // Don't clear input here, submitPrompt handles it via state update triggering re-render
    // setInputValue("");
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

  // Handle clicking an example prompt
  const handleExampleClick = (prompt: string) => {
    setInputValue(prompt); // Set input value
    // Optionally, submit immediately after setting? Or let user press send?
    // For now, just set the input value. User can press send.
    // If immediate submit is desired: submitPrompt(prompt); setInputValue('');
  };

  // This component now renders *only* the content area within the main layout
  return (
    // Main container with flex column layout
    <div className="flex flex-col h-full max-h-full"> {/* Ensure it fills height */}
      {/* Optional: Display top-level errors */}
      {error && !isLoading && <ErrorDisplay error={error} />}

      {/* Conditional Rendering: Initial Screen or Chat History */}
      {chatHistory.length === 0 && !isLoading && !error ? (
        <InitialChatScreen onExampleClick={handleExampleClick} />
      ) : (
        <ScrollArea className="flex-1 p-4 h-[60vh] overflow-y-auto" ref={scrollAreaRef}> {/* Added fixed height and scroll */}
          <div className="space-y-4">
            {chatHistory.map((message, index) => (
              <ChatMessageDisplay key={index} message={message} />
            ))}
            {/* Optional: Show loading indicator at the end */}
            {isLoading && (
               <div className="flex justify-start">
                  <div className="p-2 text-sm text-muted-foreground">
                    {chatText}  {/* Show live chatText updates */}
                  </div>
               </div>
            )}
          </div>
        </ScrollArea>
      )}

      {/* Input Form Area (Always visible unless maybe error state?) */}
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
