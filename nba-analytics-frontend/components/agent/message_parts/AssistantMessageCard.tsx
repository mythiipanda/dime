"use client";

import React from 'react';
import { Card } from "@/components/ui/card";
import { Components } from 'react-markdown';
import { AgentProcessCollapsible, AgentProcessCollapsibleProps, ToolCall } from './AgentProcessCollapsible';
import { FinalAnswerDisplay, FinalAnswerDisplayProps } from './FinalAnswerDisplay';

interface MessageMetadata {
  agent_id?: string;
  session_id?: string;
  run_id?: string;
  model?: string;
  timestamp?: number;
}

interface ReasoningData {
  thinking?: string;
  content?: string;
  patterns?: {
    thinking?: string;
    planning?: string;
    analyzing?: string;
    [key: string]: string | undefined;
  };
}

interface MinimalSSEChatMessage {
  id?: string;
  role: 'assistant';
  content: string;
  agentName?: string;
  toolCalls?: ToolCall[];
  status?: 'thinking' | 'tool_calling' | 'complete' | 'error';
  event?: string;
  error?: string;
  dataType?: string;
  dataPayload?: any;
  metadata?: MessageMetadata;
  reasoning?: ReasoningData;
}

export interface AssistantMessageCardProps {
  message: MinimalSSEChatMessage;
  agentDisplayName?: string;
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
  agentDisplayName,
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
  const modelName = message.metadata?.model || "";

  return (
    <Card className="rounded-xl bg-card text-card-foreground p-3 shadow-md break-words w-full">
      {/* Display agent name and model if available */}
      <div className="flex items-center justify-between mb-2">
        {agentDisplayName && (
          <p className="text-xs text-muted-foreground">
            <span className="font-semibold">{agentDisplayName}</span>
            {modelName && <span className="ml-1 opacity-70">({modelName})</span>}
          </p>
        )}
        {message.metadata?.timestamp && (
          <p className="text-xs text-muted-foreground">
            {new Date(message.metadata.timestamp * 1000).toLocaleTimeString()}
          </p>
        )}
      </div>

      {showThinkingProcessCollapsible && (
        <AgentProcessCollapsible
          reasoningNarrative={reasoningNarrative}
          toolCalls={message.toolCalls}
          messageStatus={message.status}
          messageEvent={message.event}
          agentDisplayName={agentDisplayName}
          isThinkingExpanded={isThinkingExpanded}
          onThinkingToggle={onThinkingToggle}
          expandedToolContent={expandedToolContent}
          onToolContentToggle={onToolContentToggle}
          markdownComponents={markdownComponents}
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