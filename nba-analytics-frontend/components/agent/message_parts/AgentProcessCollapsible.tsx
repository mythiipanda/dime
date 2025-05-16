"use client";

import React from 'react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button"; // Added for consistency, though not directly in this snippet
import { Loader2, CheckCircle2, Brain, ChevronUp, ChevronDown } from "lucide-react";
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from "@/lib/utils";
import ToolCallItem from './ToolCallItem'; // Changed to default import

// Ensure these types are correctly imported or defined in a shared location
export interface ToolCall {
  tool_name: string;
  status: "started" | "completed" | "error";
  content?: string; 
}

// Assuming SSEChatMessage is defined elsewhere, e.g., in a types file or imported from the hook
// For now, let's define a minimal version here if not readily available for import path
// import { ChatMessage as SSEChatMessage } from "@/lib/hooks/useAgentChatSSE"; 
// If the above import path is not correct, ensure SSEChatMessage is defined appropriately.
// For the purpose of this component, we only need status and event from message.
interface MinimalSSEChatMessage {
    status?: 'thinking' | 'complete' | 'error' | 'idle' | 'streaming'; // Made status optional
    event?: string; 
}


export interface AgentProcessCollapsibleProps {
  reasoningNarrative: string;
  toolCalls: ToolCall[] | undefined;
  messageStatus?: MinimalSSEChatMessage['status']; // Made messageStatus optional
  messageEvent: MinimalSSEChatMessage['event'];   
  isThinkingExpanded: boolean;
  onThinkingToggle: (isOpen: boolean) => void;
  expandedToolContent: { [key: number]: boolean };
  onToolContentToggle: (index: number) => void;
  markdownComponents: Components;
  hasReasoningToShow: boolean;
  hasToolsToShow: boolean;
}

export const AgentProcessCollapsible: React.FC<AgentProcessCollapsibleProps> = ({
  reasoningNarrative,
  toolCalls,
  messageStatus,
  messageEvent,
  isThinkingExpanded,
  onThinkingToggle,
  expandedToolContent,
  onToolContentToggle,
  markdownComponents,
  hasReasoningToShow,
  hasToolsToShow
}) => {
  return (
    <Collapsible open={isThinkingExpanded} onOpenChange={onThinkingToggle} className="border-b border-border/30 pb-2 mb-2 last:border-b-0 last:pb-0 last:mb-0">
      <CollapsibleTrigger className="flex items-center justify-between w-full group/trigger py-1 hover:bg-muted/50 dark:hover:bg-muted/30 rounded-md px-1.5 -mx-1.5 transition-colors">
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-muted-foreground group-hover/trigger:text-primary transition-colors" />
          <span className="text-xs font-medium text-muted-foreground group-hover/trigger:text-primary transition-colors">Agent Process</span>
        </div>
        <div className="flex items-center gap-2">
          {messageStatus === 'thinking' && messageEvent !== "RunCompleted" && ( // Assuming RunCompleted is a valid event string
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
              {messageEvent === "ReasoningStarted" ? ( // Assuming ReasoningStarted is a valid event string
                <span className="text-xs text-muted-foreground">Initiating...</span>
              ) : toolCalls && toolCalls.some(tc => tc.status === 'started') ? (
                <span className="text-xs text-muted-foreground">Using Tools...</span>
              ) : (
                <span className="text-xs text-muted-foreground">Thinking...</span>
              )}
            </>
          )}
          {messageStatus === 'complete' && (hasReasoningToShow || hasToolsToShow) && (
              <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
          )}
          <ChevronUp className={cn("h-4 w-4 text-muted-foreground transition-transform duration-200", !isThinkingExpanded && "rotate-180")} />
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent className="prose prose-xs dark:prose-invert max-w-none text-muted-foreground data-[state=open]:animate-collapsible-down data-[state=closed]:animate-collapsible-up overflow-hidden">
        <div className="space-y-2 text-xs pt-2.5">
          {hasReasoningToShow && (
            <div className="reasoning-narrative p-2 bg-muted/30 dark:bg-muted/20 rounded-md border border-border/30">
              <ReactMarkdown components={markdownComponents} remarkPlugins={[remarkGfm]}>
                {reasoningNarrative}
              </ReactMarkdown>
            </div>
          )}
          {hasToolsToShow && toolCalls && (
            <div className="space-y-1.5 mt-2 pt-2 border-t border-border/30">
              <div className="text-xs font-medium text-muted-foreground mb-1">Tool Activity:</div>
              {toolCalls.map((tool, index) => (
                <ToolCallItem 
                  key={`${tool.tool_name}-${index}-${tool.status}`} // Ensure key is unique enough
                  tool={tool} 
                  isExpanded={expandedToolContent[index] || false} 
                  onToggleExpand={() => onToolContentToggle(index)} 
                />
              ))}
            </div>
          )}
          {!hasReasoningToShow && !hasToolsToShow && messageStatus !== 'complete' && (
            <p className="italic text-muted-foreground">Agent is initializing...</p>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}; 