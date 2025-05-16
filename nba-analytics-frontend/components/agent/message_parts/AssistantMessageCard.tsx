"use client";

import React from 'react';
import { Card } from "@/components/ui/card";
import { Components } from 'react-markdown'; // For markdownComponents prop type
import { AgentProcessCollapsible, AgentProcessCollapsibleProps, ToolCall } from './AgentProcessCollapsible'; // Assuming ToolCall is exported here too or from a shared types file
import { FinalAnswerDisplay, FinalAnswerDisplayProps } from './FinalAnswerDisplay';

// Minimal SSEChatMessage type needed for this component
// Actual import: import { ChatMessage as SSEChatMessage } from "@/lib/hooks/useAgentChatSSE";
interface MinimalSSEChatMessage {
  id?: string; // Changed to string | undefined
  role: 'assistant';
  content: string;
  toolCalls?: ToolCall[]; // Uses ToolCall from AgentProcessCollapsible import
  status?: 'thinking' | 'complete' | 'error'; // Aligned with hook's ChatMessage.status (removed streaming, idle)
  event?: string;
  error?: string;
  dataType?: string; // Added from hook's ChatMessage
  dataPayload?: any; // Added from hook's ChatMessage
}

export interface AssistantMessageCardProps {
  message: MinimalSSEChatMessage;
  reasoningNarrative: string;
  finalAnswerForDisplay: string;
  isThinkingExpanded: boolean;
  onThinkingToggle: (isOpen: boolean) => void;
  expandedToolContent: { [key: number]: boolean };
  onToolContentToggle: (index: number) => void;
  showThinkingProcessCollapsible: boolean;
  hasReasoningToShow: boolean;
  hasToolsToShow: boolean;
  markdownComponents: Components;
  onCopyFinalAnswer: (text: string) => Promise<void>;
  isFinalAnswerCopied: boolean;
}

export const AssistantMessageCard: React.FC<AssistantMessageCardProps> = ({
  message,
  reasoningNarrative,
  finalAnswerForDisplay,
  isThinkingExpanded,
  onThinkingToggle,
  expandedToolContent,
  onToolContentToggle,
  showThinkingProcessCollapsible,
  hasReasoningToShow,
  hasToolsToShow,
  markdownComponents,
  onCopyFinalAnswer,
  isFinalAnswerCopied,
}) => {
  return (
    <Card className="rounded-xl bg-card text-card-foreground p-3 shadow-md break-words w-full">
      {showThinkingProcessCollapsible && (
        <AgentProcessCollapsible 
          reasoningNarrative={reasoningNarrative}
          toolCalls={message.toolCalls}
          messageStatus={message.status}
          messageEvent={message.event}
          isThinkingExpanded={isThinkingExpanded}
          onThinkingToggle={onThinkingToggle}
          expandedToolContent={expandedToolContent}
          onToolContentToggle={onToolContentToggle}
          markdownComponents={markdownComponents} // Pass down markdown components
          hasReasoningToShow={hasReasoningToShow}
          hasToolsToShow={hasToolsToShow}
        />
      )}
      
      {(message.status === 'complete') && finalAnswerForDisplay && (
        <FinalAnswerDisplay 
          content={finalAnswerForDisplay} 
          onCopy={onCopyFinalAnswer} 
          copied={isFinalAnswerCopied} 
          markdownComponents={markdownComponents} 
        />
      )}

      {message.dataType && message.dataPayload && (message.status === 'complete') && !finalAnswerForDisplay && (
        <div className="mt-2.5 pt-2.5 border-t border-border/30">
          <p className="text-xs font-semibold mb-1 text-muted-foreground">Data: {message.dataType}</p>
          <pre className="text-xs bg-muted/50 dark:bg-muted/30 p-2 rounded overflow-x-auto font-mono border border-border/40">
            {typeof message.dataPayload === 'string' ? message.dataPayload : JSON.stringify(message.dataPayload, null, 2)}
          </pre>
        </div>
      )}

      {message.status === 'error' && message.error && (
        <div className="text-red-500 text-sm p-2 bg-red-500/10 rounded-md">
          <p className="font-semibold">An error occurred:</p>
          <p className="mt-1 font-mono text-xs whitespace-pre-wrap">{message.error}</p>
        </div>
      )}
      
      {/* Fallback for content if no final answer yet and not purely thinking/tool use, or for simpler messages */}
      {!finalAnswerForDisplay && message.content && !showThinkingProcessCollapsible && message.status !== 'error' && (
         <div className="prose prose-sm dark:prose-invert max-w-full break-words">
            <p>{message.content}</p> {/* Simplified display for non-final answer, non-process content */}
         </div>
      )}
    </Card>
  );
}; 