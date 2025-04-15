// nba-analytics-frontend/app/ai-assistant/page.tsx
"use client";

import React, { useEffect, useRef } from 'react';
import { useAgentChatSSE } from '@/lib/hooks/useAgentChatSSE';
import { InitialChatScreen } from '@/components/agent/InitialChatScreen';
import { PromptInputForm } from '@/components/agent/PromptInputForm';
import { ChatMessageDisplay } from '@/components/agent/ChatMessageDisplay';
import { ErrorDisplay } from '@/components/agent/ErrorDisplay';
import { ScrollArea } from "@/components/ui/scroll-area";
// import { Separator } from "@/components/ui/separator"; // Component not found, needs to be added via shadcn CLI

// Renamed function component
export default function AiAssistantPage() {
  const {
    isLoading,
    error,
    chatHistory,
    submitPrompt,
    closeConnection, // Get closeConnection if needed for cleanup
  } = useAgentChatSSE({ apiUrl: '/ask' }); // apiUrl is technically ignored by the hook now

  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom whenever chatHistory changes
  useEffect(() => {
    if (scrollAreaRef.current) {
      // Use setTimeout to allow the DOM to update before scrolling
      setTimeout(() => {
        if (scrollAreaRef.current) {
           scrollAreaRef.current.scrollTo({ top: scrollAreaRef.current.scrollHeight, behavior: 'smooth' });
        }
      }, 100); // Small delay might be needed
    }
  }, [chatHistory]);

  // Optional: Close SSE connection on component unmount
  useEffect(() => {
    return () => {
      closeConnection();
    };
  }, [closeConnection]);

  const handlePromptSubmit = (prompt: string) => {
    submitPrompt(prompt);
  };

  const handleExamplePromptClick = (prompt: string) => {
     handlePromptSubmit(prompt);
  };


  return (
    <div className="flex flex-col h-[calc(100vh-theme(space.24))]"> {/* Adjust height as needed */}
      {/* Chat messages area */}
      <ScrollArea className="flex-grow p-4" ref={scrollAreaRef}>
        {chatHistory.length === 0 && !isLoading && !error ? (
          <InitialChatScreen 
            onExampleClick={handleExamplePromptClick}
            onSubmit={handlePromptSubmit}
            isLoading={isLoading}
          />
        ) : (
          <>
            {chatHistory.map((msg, index) => (
              <ChatMessageDisplay 
                key={index} 
                message={msg} 
                isLatest={index === chatHistory.length - 1}
              />
            ))}
            {error && <ErrorDisplay error={error} />}
          </>
        )}
      </ScrollArea>

      {/* <Separator /> */} {/* Component not found, needs to be added via shadcn CLI */}

      {/* Input area - only show when there's chat history */}
      {chatHistory.length > 0 && (
        <div className="p-4 space-y-4">
          <PromptInputForm onSubmit={handlePromptSubmit} isLoading={isLoading} />
          <p className="text-xs text-center text-muted-foreground">
            AI may produce inaccurate information. Verify important details.
          </p>
        </div>
      )}
    </div>
  );
}