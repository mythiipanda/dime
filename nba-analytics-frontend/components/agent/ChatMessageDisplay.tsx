// components/agent/ChatMessageDisplay.tsx
"use client"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"
import { UserIcon, BotIcon, Loader2, CheckCircle2, XCircle, ChevronDown, ChevronUp, Brain, Copy, Check, Link, BookOpen, TerminalSquare, AlertCircle } from "lucide-react"
import ReactMarkdown, { Components } from 'react-markdown'
import { useState, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ChatMessage as SSEChatMessage } from "@/lib/hooks/useAgentChatSSE"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import remarkGfm from 'remark-gfm'

// Import sub-components
import UserMessageCard from './message_parts/UserMessageCard';
import { AssistantMessageCard } from './message_parts/AssistantMessageCard';

export interface ToolCall {
  tool_name: string
  args?: any
  status: "started" | "completed" | "error"
  content?: string
  error?: string
  isError?: boolean
}

export interface Source {
  title: string
  url?: string
  content?: string
}

export interface MessageMetadata {
  agent_id?: string
  session_id?: string
  run_id?: string
  model?: string
  timestamp?: number
}

export interface ReasoningData {
  thinking?: string
  content?: string
}

interface ChatMessageDisplayProps {
  message: SSEChatMessage
  isLatest?: boolean
}

const FINAL_ANSWER_MARKER = "FINAL_ANSWER::";

const copyToClipboardUtil = async (textToCopy: string, setCopiedState: (copied: boolean) => void) => {
  try {
    await navigator.clipboard.writeText(textToCopy)
    setCopiedState(true)
    setTimeout(() => setCopiedState(false), 2000)
  } catch (err) {
    console.error('Failed to copy text: ', err)
  }
};

const createMarkdownComponentsConfig = (onCopy: (text: string) => Promise<void>, isCopied: () => boolean): Components => ({
  code(props) {
    const { children, className, ...rest } = props;
    const match = /language-(\w+)/.exec(className || '');
    const codeText = String(children).replace(/\n$/, '');
    const currentlyCopied = isCopied();

    if (match) {
        return (
          <div className="relative my-3 group">
            <div className="absolute right-2 top-2 z-10 flex items-center gap-1.5">
              <span className="rounded-sm bg-black/70 px-1.5 py-0.5 text-[10px] font-mono text-white/70">
                {match[1]}
              </span>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      className="opacity-0 group-hover:opacity-100 h-5 w-5 p-0 flex items-center justify-center rounded hover:bg-muted/50 transition-opacity"
                      onClick={() => onCopy(codeText)}
                    >
                      {currentlyCopied ? <Check className="h-2.5 w-2.5 text-green-500" /> : <Copy className="h-2.5 w-2.5 text-muted-foreground" />}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent><p className="text-xs">{currentlyCopied ? 'Copied!' : 'Copy code'}</p></TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <pre className="rounded-md border bg-muted/50 p-3 font-mono text-xs overflow-x-auto"><code className={className} {...rest}>{children}</code></pre>
          </div>
        );
    }
    return <code className="relative rounded bg-muted/70 px-[0.3rem] py-[0.2rem] font-mono text-xs font-semibold" {...rest}>{children}</code>;
  },
  p: ({node, ...props}) => <p className="mb-3 leading-relaxed last:mb-0" {...props} />,
  ul: ({node, ...props}) => <ul className="my-3 ml-5 list-disc marker:text-muted-foreground [&>li]:mt-1.5" {...props} />,
  ol: ({node, ...props}) => <ol className="my-3 ml-5 list-decimal marker:text-muted-foreground [&>li]:mt-1.5" {...props} />,
  li: ({node, ...props}) => <li className="leading-relaxed" {...props} />,
  a: ({node, ...props}) => <a className="font-medium text-primary underline underline-offset-4 hover:text-primary/80" target="_blank" rel="noopener noreferrer" {...props} />,
  strong: ({node, ...props}) => <strong className="font-semibold text-foreground/90" {...props} />,
  table: ({node, ...props}) => <div className="overflow-x-auto my-3"><table className="w-full border-collapse border border-border text-xs" {...props} /></div>,
  thead: ({node, ...props}) => <thead className="bg-muted/50 dark:bg-muted/30" {...props} />,
  th: ({node, ...props}) => <th className="border border-border px-2 py-1.5 text-left font-medium" {...props} />,
  td: ({node, ...props}) => <td className="border border-border px-2 py-1.5" {...props} />,
});

export function ChatMessageDisplay({ message, isLatest = false }: ChatMessageDisplayProps) {
  const [isUserMsgCopied, setIsUserMsgCopied] = useState(false);
  const [isFinalAnswerCopied, setIsFinalAnswerCopied] = useState(false);
  const [isThinkingExpanded, setIsThinkingExpanded] = useState(isLatest || false);
  const [expandedToolContent, setExpandedToolContent] = useState<{ [key: number]: boolean }>({});
  const [isCodeCopied, setIsCodeCopied] = useState(false);

  // Extract content for display
  let reasoningNarrative = "";
  let finalAnswerForDisplay = "";
  const fullContent = message.content || "";

  // Get agent name from metadata or fallback to message.agentName
  let agentDisplayName = "Assistant";
  if (message.metadata?.agent_id) {
    const agentIdParts = message.metadata.agent_id.split('-');
    agentDisplayName = agentIdParts[0] || "Assistant";
  } else if (message.agentName) {
    agentDisplayName = message.agentName.includes('-') ?
      message.agentName.split('-')[0] : message.agentName;
  }

  // Extract reasoning data if available
  const thinkingProcess = message.reasoning?.thinking || "";
  const reasoningContent = message.reasoning?.content || "";

  // Extract thinking patterns from content
  const extractThinkingPatterns = (content: string): { thinking: string, planning: string, analyzing: string } => {
    const patterns = {
      thinking: /\*\*Thinking:\*\*(.*?)(?=\*\*|$)/gi,
      planning: /\*\*Planning:\*\*(.*?)(?=\*\*|$)/gi,
      analyzing: /\*\*Analyzing:\*\*(.*?)(?=\*\*|$)/gi,
    };

    const extracted = {
      thinking: "",
      planning: "",
      analyzing: ""
    };

    // Extract each pattern
    for (const [key, pattern] of Object.entries(patterns)) {
      const matches = [...content.matchAll(pattern)];
      if (matches.length > 0) {
        extracted[key as keyof typeof extracted] = matches.map(m => m[1].trim()).join("\n\n");
      }
    }

    return extracted;
  };

  if (message.role === 'assistant') {
    // Check for final answer marker
    const markerIndex = fullContent.indexOf(FINAL_ANSWER_MARKER);

    if (markerIndex !== -1) {
      // Split content at the marker
      reasoningNarrative = fullContent.substring(0, markerIndex).trim();
      finalAnswerForDisplay = fullContent.substring(markerIndex + FINAL_ANSWER_MARKER.length).trim();
    } else if (message.status === 'complete' && !message.dataType) {
      // If complete and no data type, treat all content as final answer
      finalAnswerForDisplay = fullContent.trim();
      reasoningNarrative = "";
    } else if (message.status === 'thinking' || message.status === 'tool_calling') {
      // If thinking or calling tools, treat all content as reasoning
      reasoningNarrative = fullContent.trim();
      finalAnswerForDisplay = "";
    } else {
      // Default case - treat as reasoning
      reasoningNarrative = fullContent.trim();
    }

    // Extract thinking patterns from content
    const extractedPatterns = extractThinkingPatterns(fullContent);

    // Build enhanced reasoning narrative
    let enhancedReasoning = reasoningNarrative;

    // If we have explicit reasoning data from the message metadata, add it
    if (thinkingProcess || reasoningContent || message.reasoning?.patterns) {
      if (enhancedReasoning) {
        enhancedReasoning += "\n\n";
      }

      if (thinkingProcess) {
        enhancedReasoning += `**Thinking Process:**\n${thinkingProcess}\n\n`;
      }

      if (reasoningContent) {
        enhancedReasoning += `**Reasoning:**\n${reasoningContent}\n\n`;
      }

      // Add patterns from the reasoning data if available
      if (message.reasoning?.patterns) {
        const patterns = message.reasoning.patterns;

        if (patterns.thinking && !enhancedReasoning.includes(patterns.thinking)) {
          enhancedReasoning += `\n\n**Thinking:**\n${patterns.thinking}\n\n`;
        }

        if (patterns.planning && !enhancedReasoning.includes(patterns.planning)) {
          enhancedReasoning += `\n\n**Planning:**\n${patterns.planning}\n\n`;
        }

        if (patterns.analyzing && !enhancedReasoning.includes(patterns.analyzing)) {
          enhancedReasoning += `\n\n**Analyzing:**\n${patterns.analyzing}\n\n`;
        }
      }
    }

    // Add extracted thinking patterns if they're not already in the reasoning
    if (extractedPatterns.thinking && !enhancedReasoning.includes(extractedPatterns.thinking)) {
      enhancedReasoning += `\n\n**Thinking:**\n${extractedPatterns.thinking}\n\n`;
    }

    if (extractedPatterns.planning && !enhancedReasoning.includes(extractedPatterns.planning)) {
      enhancedReasoning += `\n\n**Planning:**\n${extractedPatterns.planning}\n\n`;
    }

    if (extractedPatterns.analyzing && !enhancedReasoning.includes(extractedPatterns.analyzing)) {
      enhancedReasoning += `\n\n**Analyzing:**\n${extractedPatterns.analyzing}\n\n`;
    }

    // Update the reasoning narrative with the enhanced version
    reasoningNarrative = enhancedReasoning.trim();
  }

  // Track if the final event has been received
  const [finalEventReceived, setFinalEventReceived] = useState(false);

  // When the event changes to "RunCompleted" or "final", mark that the final event has been received
  useEffect(() => {
    if (message.event === "RunCompleted" || message.event === "final") {
      console.log(`ChatMessageDisplay: Received ${message.event} event`);
      setFinalEventReceived(true);
    }
  }, [message.event]);

  // Also check for the "complete" status with 100% progress as a fallback
  useEffect(() => {
    if (message.status === "complete" && message.progress === 100) {
      console.log("ChatMessageDisplay: Detected complete status with 100% progress");
      // Add a small delay to ensure all content is processed
      const timer = setTimeout(() => {
        setFinalEventReceived(true);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [message.status, message.progress]);

  // Log when final event is received for debugging
  useEffect(() => {
    if (finalEventReceived) {
      console.log("ChatMessageDisplay: Final event received, content should be complete");
    }
  }, [finalEventReceived]);

  useEffect(() => {
    if (isLatest && message.role === 'assistant') {
      // Auto-expand thinking process while in progress
      if (message.status === 'thinking' || message.status === 'tool_calling') {
        setIsThinkingExpanded(true);
      }
    }
  }, [isLatest, message.status, message.role]);

  // Separate effect for handling auto-collapse to avoid conflicts
  useEffect(() => {
    if (isLatest && message.role === 'assistant') {
      // Auto-collapse thinking process ONLY when final event is received AND has final answer
      if (finalEventReceived && finalAnswerForDisplay) {
        console.log("ChatMessageDisplay: Auto-collapsing thinking process");
        // Add a small delay to allow the user to see the final thinking state
        const collapseTimer = setTimeout(() => {
          setIsThinkingExpanded(false);
        }, 1500); // 1.5 second delay

        return () => clearTimeout(collapseTimer);
      }
    }
  }, [isLatest, message.role, finalAnswerForDisplay, finalEventReceived]);

  const handleCopyToClipboard = useCallback(async (text: string, type: 'user' | 'finalAnswer' | 'code') => {
    let setCopiedFunction;
    if (type === 'user') {
      setCopiedFunction = setIsUserMsgCopied;
    } else if (type === 'finalAnswer') {
      setCopiedFunction = setIsFinalAnswerCopied;
    } else {
      setCopiedFunction = setIsCodeCopied;
    }
    await copyToClipboardUtil(text, setCopiedFunction);
  }, []);

  const sharedMarkdownComponents = createMarkdownComponentsConfig(
    (text) => handleCopyToClipboard(text, 'code'),
    () => isCodeCopied
  );

  const toggleThinkingProcess = (isOpen: boolean) => {
    setIsThinkingExpanded(isOpen);
  };

  const toggleToolContent = (index: number) => {
    setExpandedToolContent(prev => ({ ...prev, [index]: !prev[index] }));
  };

  const hasReasoningToShow = !!reasoningNarrative.trim();
  const hasToolsToShow = !!(message.role === 'assistant' && message.toolCalls && message.toolCalls.length > 0);
  const showThinkingProcessCollapsible =
    message.role === 'assistant' &&
    (message.status === 'thinking' || message.status === 'tool_calling' || hasReasoningToShow || hasToolsToShow);

  return (
    <div className={cn("flex items-start gap-3 py-4", message.role === 'user' ? "justify-end" : "justify-start")}>
      {message.role === 'assistant' && (
        <Avatar className="h-8 w-8 border shadow-sm shrink-0">
          <AvatarFallback className="bg-primary/10 text-primary">
            <BotIcon className="h-5 w-5" />
          </AvatarFallback>
        </Avatar>
      )}

      <div className={cn("flex flex-col gap-1.5 w-full", message.role === 'user' ? "max-w-[70%]" : "max-w-[calc(100%-44px)]")}>
        {message.role === 'user' ? (
          <UserMessageCard
            content={message.content || ""}
            markdownComponents={sharedMarkdownComponents}
          />
        ) : (
          <AssistantMessageCard
            message={message as SSEChatMessage & { role: 'assistant' }}
            agentDisplayName={agentDisplayName}
            reasoningNarrative={reasoningNarrative}
            finalAnswerForDisplay={finalAnswerForDisplay}
            isThinkingExpanded={isThinkingExpanded}
            onThinkingToggle={toggleThinkingProcess}
            expandedToolContent={expandedToolContent}
            onToolContentToggle={toggleToolContent}
            showThinkingProcessCollapsible={showThinkingProcessCollapsible}
            hasReasoningToShow={hasReasoningToShow}
            hasToolsToShow={hasToolsToShow}
            markdownComponents={sharedMarkdownComponents}
            onCopyFinalAnswer={(text) => handleCopyToClipboard(text, 'finalAnswer')}
            isFinalAnswerCopied={isFinalAnswerCopied}
          />
        )}
      </div>

      {message.role === 'user' && (
        <Avatar className="h-8 w-8 border shadow-sm">
          <AvatarFallback className="bg-secondary">
            <UserIcon className="h-5 w-5 text-secondary-foreground" />
          </AvatarFallback>
        </Avatar>
      )}
    </div>
  );
}