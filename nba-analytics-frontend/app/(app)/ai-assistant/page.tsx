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

  const handleStop = () => {
    closeConnection();
  };

  const renderChatArea = () => {
    if (chatHistory.length === 0 && !isLoading && !error) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center p-4 sm:p-6">
          <div className="w-full max-w-3xl">
            <InitialChatScreen
              onExampleClick={handlePromptSubmit}
            />
          </div>
        </div>
      );
    } else {
      return (
        <ScrollArea className="flex-1 p-4 sm:p-6" ref={scrollAreaRef}>
          <div className="space-y-6 max-w-3xl mx-auto">
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
      );
    }
  };

  return (
    <div className="h-full flex flex-col animate-in fade-in-0 duration-300">
      <main className="flex-1 flex flex-col overflow-hidden">
        {renderChatArea()}
      </main>
      <div className="border-t bg-background/95 p-3 sm:p-4 sticky bottom-0">
        <div className="max-w-3xl mx-auto space-y-2">
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
  );
}