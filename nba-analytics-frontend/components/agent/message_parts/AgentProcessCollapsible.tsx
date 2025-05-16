"use client";

import React from 'react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button"; // Added for consistency, though not directly in this snippet
import { Loader2, CheckCircle2, Brain, ChevronUp, ChevronDown, Wrench, AlertCircle } from "lucide-react";
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from "@/lib/utils";
import ToolCallItem from './ToolCallItem'; // Changed to default import

// Ensure these types are correctly imported or defined in a shared location
export interface ToolCall {
  tool_name: string;
  args?: any;
  status: "started" | "completed" | "error";
  content?: string;
  isError?: boolean;
}

// Assuming SSEChatMessage is defined elsewhere, e.g., in a types file or imported from the hook
// For now, let's define a minimal version here if not readily available for import path
// import { ChatMessage as SSEChatMessage } from "@/lib/hooks/useAgentChatSSE";
// If the above import path is not correct, ensure SSEChatMessage is defined appropriately.
// For the purpose of this component, we only need status and event from message.
interface MinimalSSEChatMessage {
    status?: 'thinking' | 'tool_calling' | 'complete' | 'error';
    event?: string;
}


export interface AgentProcessCollapsibleProps {
  reasoningNarrative: string;
  toolCalls: ToolCall[] | undefined;
  messageStatus?: MinimalSSEChatMessage['status'];
  messageEvent: MinimalSSEChatMessage['event'];
  agentDisplayName?: string;
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
  agentDisplayName,
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
      <CollapsibleTrigger className={cn(
        "flex items-center justify-between w-full py-2 px-3 rounded-md transition-colors",
        messageEvent === "RunCompleted" || messageEvent === "final" || messageStatus === 'complete' ?
          "bg-green-50 dark:bg-green-950/30 hover:bg-green-100 dark:hover:bg-green-900/30" :
        messageStatus === 'thinking' ?
          "bg-blue-50 dark:bg-blue-950/30 hover:bg-blue-100 dark:hover:bg-blue-900/30" :
        messageStatus === 'tool_calling' ?
          "bg-amber-50 dark:bg-amber-950/30 hover:bg-amber-100 dark:hover:bg-amber-900/30" :
        messageStatus === 'error' ?
          "bg-red-50 dark:bg-red-950/30 hover:bg-red-100 dark:hover:bg-red-900/30" :
          "bg-muted/30 hover:bg-muted/50"
      )}>
        <div className="flex items-center gap-2">
          {messageStatus === 'thinking' && messageEvent !== "RunCompleted" && messageEvent !== "final" &&
            <Brain className="h-4 w-4 text-blue-600 dark:text-blue-400" />}
          {messageStatus === 'tool_calling' && messageEvent !== "RunCompleted" && messageEvent !== "final" &&
            <Wrench className="h-4 w-4 text-amber-600 dark:text-amber-400" />}
          {(messageStatus === 'complete' || messageEvent === "RunCompleted" || messageEvent === "final") &&
            <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />}
          {messageStatus === 'error' &&
            <AlertCircle className="h-4 w-4 text-red-600 dark:text-red-400" />}

          <div className="flex flex-col">
            <span className="text-xs font-semibold">
              {agentDisplayName ? `${agentDisplayName}'s Process` : "Agent Process"}
            </span>
            {hasToolsToShow && toolCalls && (
              <span className="text-[11px] text-muted-foreground">
                {toolCalls.length} tool{toolCalls.length === 1 ? '' : 's'} used
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {messageStatus === 'thinking' && messageEvent !== "RunCompleted" && messageEvent !== "final" && (
            <span className="text-[11px] font-medium text-blue-700 dark:text-blue-400 animate-pulse flex items-center">
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              Thinking...
            </span>
          )}
          {messageStatus === 'tool_calling' && messageEvent !== "RunCompleted" && messageEvent !== "final" && (
            <span className="text-[11px] font-medium text-amber-700 dark:text-amber-400 flex items-center">
              <Wrench className="h-3 w-3 mr-1" />
              Using tools...
            </span>
          )}
          {(messageEvent === "RunCompleted" || messageEvent === "final" || messageStatus === 'complete') && (
            <span className="text-[11px] font-medium text-green-700 dark:text-green-400 flex items-center">
              <CheckCircle2 className="h-3 w-3 mr-1" />
              Complete
            </span>
          )}
          <ChevronUp className={cn(
            "h-4 w-4 transition-transform duration-200",
            !isThinkingExpanded && "rotate-180",
            messageStatus === 'thinking' && messageEvent !== "RunCompleted" && messageEvent !== "final" ?
              "text-blue-600 dark:text-blue-400" :
            messageStatus === 'tool_calling' && messageEvent !== "RunCompleted" && messageEvent !== "final" ?
              "text-amber-600 dark:text-amber-400" :
            messageStatus === 'error' ?
              "text-red-600 dark:text-red-400" :
            (messageStatus === 'complete' || messageEvent === "RunCompleted" || messageEvent === "final") ?
              "text-green-600 dark:text-green-400" :
              "text-muted-foreground"
          )} />
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent className="prose prose-xs dark:prose-invert max-w-none data-[state=open]:animate-collapsible-down data-[state=closed]:animate-collapsible-up overflow-hidden">
        <div className="space-y-3 text-xs pt-3">
          {hasReasoningToShow && (
            <div className="reasoning-narrative p-3 bg-blue-50/50 dark:bg-blue-950/20 rounded-md border border-blue-200 dark:border-blue-800/50">
              <div className="flex items-center justify-between gap-1.5 mb-2">
                <div className="flex items-center gap-1.5">
                  <Brain className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" />
                  <span className="text-xs font-semibold text-blue-700 dark:text-blue-400">Thinking Process:</span>
                </div>
                {messageStatus === 'thinking' && messageEvent !== "RunCompleted" && messageEvent !== "final" && (
                  <span className="text-[10px] font-medium text-blue-700 dark:text-blue-400 animate-pulse flex items-center">
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                    Thinking...
                  </span>
                )}
                {(messageEvent === "RunCompleted" || messageEvent === "final") && (
                  <span className="text-[10px] font-medium text-green-700 dark:text-green-400 flex items-center">
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                    Complete
                  </span>
                )}
              </div>

              {/* Render the thinking process with animated highlighting for new content */}
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown components={markdownComponents} remarkPlugins={[remarkGfm]}>
                  {reasoningNarrative}
                </ReactMarkdown>
              </div>

              {/* Show a pulsing indicator when thinking is in progress */}
              {messageStatus === 'thinking' && messageEvent !== "RunCompleted" && messageEvent !== "final" && (
                <div className="mt-2 flex items-center justify-center">
                  <div className="h-1 w-full bg-blue-100 dark:bg-blue-900/30 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500 dark:bg-blue-600 animate-pulse-slow rounded-full"
                         style={{ width: '60%' }}></div>
                  </div>
                </div>
              )}

              {/* Show a complete progress bar when finished */}
              {(messageEvent === "RunCompleted" || messageEvent === "final" || messageStatus === 'complete') && (
                <div className="mt-2 flex items-center justify-center">
                  <div className="h-1 w-full bg-green-100 dark:bg-green-900/30 rounded-full overflow-hidden">
                    <div className="h-full bg-green-500 dark:bg-green-600 rounded-full"
                         style={{ width: '100%' }}></div>
                  </div>
                </div>
              )}
            </div>
          )}
          {hasToolsToShow && toolCalls && (
            <div className="space-y-2 mt-3">
              <div className="flex items-center gap-1.5 mb-2">
                <Wrench className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
                <span className="text-xs font-semibold text-amber-700 dark:text-amber-400">Tool Activity:</span>
              </div>
              {toolCalls.map((tool, index) => (
                <ToolCallItem
                  key={`${tool.tool_name}-${index}-${tool.status}`}
                  tool={tool}
                  isExpanded={expandedToolContent[index] || false}
                  onToggleExpand={() => onToolContentToggle(index)}
                />
              ))}
            </div>
          )}
          {!hasReasoningToShow && !hasToolsToShow && messageStatus !== 'complete' && (
            <div className="p-3 bg-blue-50/50 dark:bg-blue-950/20 rounded-md border border-blue-200 dark:border-blue-800/50">
              <p className="italic text-blue-700 dark:text-blue-400 text-center">Agent is initializing...</p>
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
};