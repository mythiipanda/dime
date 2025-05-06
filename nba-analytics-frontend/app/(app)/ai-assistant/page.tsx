// nba-analytics-frontend/app/ai-assistant/page.tsx
"use client";

import React, { useEffect, useRef } from 'react';
import { useAgentChatSSE } from '@/lib/hooks/useAgentChatSSE';
import { InitialChatScreen } from '@/components/agent/InitialChatScreen';
import { PromptInputForm } from '@/components/agent/PromptInputForm';
import { ChatMessageDisplay } from '@/components/agent/ChatMessageDisplay';
import { ErrorDisplay } from '@/components/agent/ErrorDisplay';
import { ScrollArea } from "@/components/ui/scroll-area";

export default function AiAssistantPage() {
  const {
    isLoading,
    error,
    chatHistory,
    submitPrompt,
    closeConnection,
  } = useAgentChatSSE({ apiUrl: '/api/v1/ask' });

  const scrollAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollAreaRef.current) {
      setTimeout(() => {
        if (scrollAreaRef.current) {
           scrollAreaRef.current.scrollTo({ top: scrollAreaRef.current.scrollHeight, behavior: 'smooth' });
        }
      }, 100);
    }
  }, [chatHistory]);

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

  const handleStop = () => {
    closeConnection();
  };

  return (
    // Use h-full to take height from parent (AppLayout's main content area)
    <div className="h-full flex flex-col animate-in fade-in-0 duration-300">
      <main className="flex-1 flex flex-col overflow-hidden"> {/* Added overflow-hidden for children like ScrollArea */}
        {chatHistory.length === 0 && !isLoading && !error ? (
          // Initial screen: keep centered, input at bottom
          <div className="flex-1 flex flex-col">
            <div className="flex-1 flex items-center justify-center p-4 sm:p-6">
              <div className="w-full max-w-3xl"> {/* Adjusted max-width for initial screen content */}
                <InitialChatScreen
                  onExampleClick={handleExamplePromptClick}
                />
              </div>
            </div>
            {/* Input form for initial screen */}
            <div className="border-t bg-background/95 p-3 sm:p-4">
              <div className="max-w-3xl mx-auto"> {/* Consistent max-width */}
                <PromptInputForm
                  onSubmit={handlePromptSubmit}
                  onStop={handleStop}
                  isLoading={isLoading}
                />
                 <p className="mt-2 text-xs text-center text-muted-foreground opacity-75">
                  AI may produce inaccurate information. Verify important details.
                </p>
              </div>
            </div>
          </div>
        ) : (
          // Active chat view: integrated messages and input
          <div className="flex-1 flex flex-col overflow-hidden">
            <ScrollArea className="flex-1 p-4 sm:p-6" ref={scrollAreaRef}>
              <div className="space-y-6 max-w-3xl mx-auto"> {/* Consistent max-width */}
                {chatHistory.map((msg, index) => (
                  <ChatMessageDisplay
                    key={index}
                    message={msg}
                    isLatest={index === chatHistory.length - 1}
                  />
                ))}
                {error && <ErrorDisplay error={error} />}
              </div>
              {/* Spacer for scroll to bottom, can be adjusted or removed if auto-scroll is perfect */}
              {/* <div className="h-8" />  */}
            </ScrollArea>

            {/* Input form for active chat */}
            <div className="border-t bg-background/95 p-3 sm:p-4">
              <div className="max-w-3xl mx-auto space-y-2"> {/* Consistent max-width */}
                <PromptInputForm
                  onSubmit={handlePromptSubmit}
                  onStop={handleStop}
                  isLoading={isLoading}
                />
                <p className="text-xs text-center text-muted-foreground opacity-75 transition-opacity hover:opacity-100">
                  AI may produce inaccurate information. Verify important details.
                </p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}