// nba-analytics-frontend/app/ai-assistant/page.tsx
"use client";

import React, { useEffect, useRef } from 'react';
import { useAgentChatSSE } from '@/lib/hooks/useAgentChatSSE';
import { InitialChatScreen } from '@/components/agent/InitialChatScreen';
import { PromptInputForm } from '@/components/agent/PromptInputForm';
import { ChatMessageDisplay } from '@/components/agent/ChatMessageDisplay';
import { ErrorDisplay } from '@/components/agent/ErrorDisplay';
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

export default function AiAssistantPage() {
  const {
    isLoading,
    error,
    chatHistory,
    submitPrompt,
    closeConnection,
  } = useAgentChatSSE({ apiUrl: '/ask' });

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

  return (
    <div className="min-h-screen flex flex-col">
      <main className="flex-1 flex flex-col">
        {chatHistory.length === 0 && !isLoading && !error ? (
          <div className="flex-1 flex flex-col">
            <div className="flex-1 flex items-center justify-center px-4">
              <div className="w-full max-w-5xl">
                <InitialChatScreen 
                  onExampleClick={handleExamplePromptClick}
                  onSubmit={handlePromptSubmit}
                  isLoading={isLoading}
                />
              </div>
            </div>
            <div className="border-t bg-background/95">
              <div className="container max-w-5xl mx-auto p-4">
                <PromptInputForm onSubmit={handlePromptSubmit} isLoading={isLoading} />
              </div>
            </div>
          </div>
        ) : (
          <>
            <ScrollArea className="flex-1 px-4 container" ref={scrollAreaRef}>
              <div className="py-4 space-y-6 max-w-5xl mx-auto">
                {chatHistory.map((msg, index) => (
                  <ChatMessageDisplay 
                    key={index} 
                    message={msg} 
                    isLatest={index === chatHistory.length - 1}
                  />
                ))}
                {error && <ErrorDisplay error={error} />}
              </div>
            </ScrollArea>

            <div className="border-t bg-background/95">
              <div className="container max-w-5xl mx-auto p-4 space-y-4">
                <PromptInputForm onSubmit={handlePromptSubmit} isLoading={isLoading} />
                <p className="text-xs text-center text-muted-foreground opacity-75 transition-opacity hover:opacity-100">
                  AI may produce inaccurate information. Verify important details.
                </p>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}