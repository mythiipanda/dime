// components/agent/ChatMessageDisplay.tsx
"use client"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { UserIcon, BotIcon, Loader2, CheckCircle2, XCircle, ChevronDown, ChevronUp, Brain, Copy, Check, Link, BookOpen } from "lucide-react"
import ReactMarkdown, { Components } from 'react-markdown'
import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ChatMessage as SSEChatMessage } from "@/lib/hooks/useAgentChatSSE"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

interface ToolCall {
  tool_name: string
  status: "started" | "completed" | "error"
  content?: string
}

interface Source {
  title: string
  url?: string
  content?: string
}

interface ChatMessageDisplayProps {
  message: SSEChatMessage
  isLatest?: boolean
}

export function ChatMessageDisplay({ message, isLatest = false }: ChatMessageDisplayProps) {
  const isUser = message.role === "user"
  const [isThinkingExpanded, setIsThinkingExpanded] = useState(true)
  const [copied, setCopied] = useState(false)
  const [sources, setSources] = useState<Source[]>([])
  const [intermediateSteps, setIntermediateSteps] = useState<{
    thinking: string[]
    tools: ToolCall[]
  }>({ thinking: [], tools: [] })
  
  // Determine classes for the main message container, excluding animation for testing
  const messageContainerClasses = cn(
    "group relative flex gap-6 py-6",
    isUser ? "flex-row-reverse" : "flex-row"
  )

  useEffect(() => {
    if (isUser) return; // Only process for assistant messages

    // Process thinking steps
    if (message.content && (message.status === "thinking" || message.event === "RunResponse")) {
      // Temporarily disable setIntermediateSteps for testing refresh issue
      /* setIntermediateSteps(prev => { 
        if (!message.content || message.content === "Starting to process your request...") {
          return prev;
        }

        // Filter out "Final Answer:" before deduplication and further filtering
        const currentThought = message.content.includes("Final Answer:") ? null : message.content;
        if (!currentThought) return prev;

        const potentialNewThoughts = Array.from(new Set([...prev.thinking, currentThought]));
        
        const uniqueThoughts = potentialNewThoughts.filter(thought => 
          !potentialNewThoughts.some(other => 
            other !== thought && 
            other.includes(thought) && 
            other.length > thought.length
          )
        );

        // Avoid updating if a more complete thought already exists or if it's a substring of an existing one
        if (uniqueThoughts.some(existingThought => existingThought.includes(currentThought) && existingThought.length > currentThought.length)) {
            // This logic might need further refinement if partial updates are still desired but should be handled carefully
            return prev; 
        }

        return {
          ...prev,
          thinking: uniqueThoughts.filter(t => t.trim() !== "") // Ensure no empty thoughts
        };
      }); */
    }
    
    // Process tool calls and extract sources
    if (message.toolCalls?.length) {
      // Temporarily disable setIntermediateSteps and setSources for testing refresh issue
      /* setIntermediateSteps(prev => {
        const existingToolsMap = new Map(prev.tools.map(tool => [tool.tool_name + tool.status, tool])); // Key by name + status for updates
        const newSources: Source[] = [];

        message.toolCalls?.forEach(newTool => {
          const toolKey = newTool.tool_name + newTool.status;
          // Only add/update if the tool call is new or its status has changed meaningfully
          if (!existingToolsMap.has(toolKey)) {
             existingToolsMap.set(toolKey, newTool); // Add new or updated status tool

            if (newTool.content) {
              try {
                // Attempt to parse as JSON for structured sources
                const parsedContent = JSON.parse(newTool.content);
                newSources.push({
                  title: `${newTool.tool_name} Result (JSON)`,
                  content: JSON.stringify(parsedContent, null, 2)
                });
              } catch {
                // If not JSON, add as plain text source
                newSources.push({
                  title: `${newTool.tool_name} Result (Text)`,
                  content: newTool.content
                });
              }
            }
          } else {
            // If tool with same name and status exists, update its content if different (rare case)
            const existingTool = existingToolsMap.get(toolKey);
            if (existingTool && existingTool.content !== newTool.content) {
                existingToolsMap.set(toolKey, newTool);
                 // Optionally re-process sources for this updated tool if needed (complex, depends on requirements)
            }
          }
        });
        
        if (newSources.length > 0) {
            setSources(prevSrc => [...prevSrc, ...newSources]);
        }

        const sortedTools = Array.from(existingToolsMap.values())
          .sort((a, b) => {
            const statusOrder = { started: 0, completed: 1, error: 2 };
            return (statusOrder[a.status] || 3) - (statusOrder[b.status] || 3);
          });

        return {
          ...prev,
          tools: sortedTools
        };
      }); */
      /* setSources(prevSrc => { 
        // ... (original logic for newSources) ...
        if (newSources.length > 0) return [...prevSrc, ...newSources]; 
        return prevSrc; 
      }); */
    }
  }, [message.content, message.toolCalls, isUser, message.event, message.status]);

  const isThinkingPhase = message.status === "thinking" || message.event === "RunResponse";
  const isProcessingComplete = message.status === "complete";
  const hasMeaningfulIntermediateContent = intermediateSteps.thinking.length > 0 || intermediateSteps.tools.length > 0;
  const showThinkingProcessCollapsible = !isUser && (isThinkingPhase || hasMeaningfulIntermediateContent);

  const copyToClipboard = async (text: string | object) => {
    let textToCopy: string;
    if (typeof text === 'string') {
      textToCopy = text;
    } else {
      try {
        textToCopy = JSON.stringify(text, null, 2);
      } catch {
        textToCopy = "[Could not copy object]";
      }
    }
    try {
      await navigator.clipboard.writeText(textToCopy)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy text: ', err)
    }
  }

  const rawMarkdownContent = typeof message.content === 'string' 
    ? message.content 
    : (message.content && typeof message.content === 'object')
      ? `\`\`\`json\n${JSON.stringify(message.content, null, 2)}\n\`\`\`` 
      : '';

  const finalMarkdownContent = rawMarkdownContent.replace(/^Final Answer:\s*/i, "").trim();

  // Conditions for rendering main response content
  const hasDisplayableMarkdown = finalMarkdownContent.length > 0;
  const shouldShowMainContent = isProcessingComplete ? hasDisplayableMarkdown || sources.length > 0 : // If complete, show if markdown OR sources exist
                                 (hasDisplayableMarkdown && !rawMarkdownContent.toLowerCase().startsWith("final answer:")); // If thinking, show if markdown exists AND it's not just "Final Answer:"

  const shouldShowProcessingPlaceholder = isThinkingPhase && !hasMeaningfulIntermediateContent && !hasDisplayableMarkdown;
  
  const components: Components = {
    code(props) {
      const { className, children, ...rest } = props;
      const match = /language-(\w+)/.exec(className || '');
      const hasLanguage = Boolean(match);
      const codeText = String(children).replace(/\n$/, '')

      if (hasLanguage && match) {
        return (
          <div className="relative my-4 group">
            <div className="absolute right-4 top-3 z-10 flex items-center gap-2">
              <span className="rounded-md bg-muted px-2 py-1 text-xs font-mono text-muted-foreground">
                {match[1]}
              </span>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="opacity-0 group-hover:opacity-100 h-6 w-6 transition-opacity"
                      onClick={() => copyToClipboard(codeText)}
                    >
                      {copied ? (
                        <Check className="h-3 w-3" />
                      ) : (
                        <Copy className="h-3 w-3" />
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="text-xs">{copied ? 'Copied!' : 'Copy code'}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <pre className={cn(
              "rounded-lg border bg-muted px-4 py-4 font-mono text-sm",
              "overflow-x-auto transition-colors",
              !isUser && "border hover:border-border"
            )}>
              <code className={className} {...rest}>{children}</code>
            </pre>
          </div>
        );
      }

      return (
        <code
          className={cn(
            "relative rounded-md bg-muted px-[0.3rem] py-[0.2rem] font-mono text-sm",
            !isUser && "bg-muted",
            className
          )}
          {...rest}
        >
          {children}
        </code>
      );
    },
    p({ children, ...props }) {
      return <p {...props} className="mb-4 leading-7 last:mb-0">{children}</p>;
    },
    ul({ children, ...props }) {
      return <ul {...props} className="my-6 ml-6 list-disc marker:text-muted-foreground [&>li]:mt-2">{children}</ul>;
    },
    ol({ children, ...props }) {
      return <ol {...props} className="my-6 ml-6 list-decimal marker:text-muted-foreground [&>li]:mt-2">{children}</ol>;
    },
    li({ children, ...props }) {
      return <li {...props} className="leading-7">{children}</li>;
    },
    a({ children, href, ...props }) {
      return (
        <a 
          href={href}
          className="font-medium underline underline-offset-4 transition-colors hover:text-primary"
          target="_blank"
          rel="noopener noreferrer"
          {...props}
        >
          {children}
        </a>
      );
    }
  };

  return (
    <div className={messageContainerClasses}>
      <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center">
        <Avatar className={cn(
          "h-8 w-8 ring-1",
          isUser
            ? "bg-primary/10 ring-primary/30"
            : "bg-muted ring-border"
        )}>
          <AvatarFallback className={cn(isUser ? "text-primary" : "text-muted-foreground")}>
            {isUser ? (
              <UserIcon className="h-4 w-4" />
            ) : (
              <BotIcon className="h-4 w-4" />
            )}
          </AvatarFallback>
        </Avatar>
      </div>

      <div className={cn(
        "flex-1 space-y-3",
        isUser ? "flex flex-col items-end" : "flex flex-col items-start"
      )}>
        {isUser && (
          <div className={cn(
            "prose prose-sm sm:prose-base dark:prose-invert max-w-xl lg:max-w-2xl xl:max-w-3xl",
            "rounded-xl bg-primary text-primary-foreground p-3 sm:p-4",
            "shadow-md"
          )}>
            <ReactMarkdown components={components}>
              {finalMarkdownContent || ''}
            </ReactMarkdown>
          </div>
        )}

        {!isUser && (
          <div className={cn(
            "w-full max-w-xl lg:max-w-2xl xl:max-w-3xl rounded-xl bg-muted dark:bg-muted/60 p-3 sm:p-4 shadow-md space-y-3"
          )}>
            {showThinkingProcessCollapsible && (
              <Collapsible
                open={isThinkingExpanded}
                onOpenChange={setIsThinkingExpanded}
                className="border-b border-border/30 pb-2 mb-2 last:border-b-0 last:pb-0 last:mb-0"
              >
                <div className="flex items-center justify-between gap-3 mb-1">
                  <div className="flex items-center gap-2">
                    <Brain className="h-4 w-4 text-muted-foreground" />
                    <span className="text-xs font-medium text-muted-foreground">Thinking Process</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {isThinkingPhase && !isProcessingComplete && (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
                        <span className="text-xs text-muted-foreground">Processing...</span>
                      </>
                    )}
                    <CollapsibleTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-foreground">
                        {isThinkingExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                      </Button>
                    </CollapsibleTrigger>
                  </div>
                </div>
                <CollapsibleContent className="prose prose-xs dark:prose-invert max-w-none text-muted-foreground/90">
                  <div className="space-y-2 text-xs">
                    {intermediateSteps.thinking.length > 0 && (
                      <div className="space-y-1">
                        <div className="font-medium text-foreground/70">Reasoning:</div>
                        {intermediateSteps.thinking.map((thought, index) => (
                          <p key={index} className="pl-2 border-l-2 border-border/50 py-0.5 my-0.5">{thought}</p>
                        ))}
                      </div>
                    )}
                    {intermediateSteps.tools.length > 0 && (
                      <div className="space-y-1">
                        <div className="font-medium text-foreground/70">Actions:</div>
                        {intermediateSteps.tools.map((tool, index) => (
                          <div key={index} className="flex items-center gap-1.5 pl-2 border-l-2 border-border/50 py-0.5 my-0.5">
                            {tool.status === "started" && <Loader2 className="h-3 w-3 animate-spin" />}
                            {tool.status === "completed" && <CheckCircle2 className="h-3 w-3 text-green-600 dark:text-green-500" />}
                            {tool.status === "error" && <XCircle className="h-3 w-3 text-red-600 dark:text-red-500" />}
                            <span className="font-mono text-xs">{tool.tool_name}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {intermediateSteps.thinking.length === 0 && intermediateSteps.tools.length === 0 && (
                      <p className="italic">No detailed steps to show yet...</p>
                    )}
                  </div>
                </CollapsibleContent>
              </Collapsible>
            )}

            {shouldShowMainContent && (
              <div className="prose prose-sm sm:prose-base dark:prose-invert max-w-none relative">
                {isProcessingComplete && finalMarkdownContent && (
                  <div className="absolute top-0 right-0 z-10">
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-muted-foreground hover:text-foreground"
                            onClick={() => copyToClipboard(finalMarkdownContent)}
                          >
                            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="text-xs">{copied ? 'Copied!' : 'Copy response'}</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                )}
                <ReactMarkdown components={components}>
                  {finalMarkdownContent || ''}
                </ReactMarkdown>
              </div>
            )}
            {shouldShowProcessingPlaceholder && (
              <div className="prose prose-sm sm:prose-base dark:prose-invert max-w-none text-muted-foreground italic">
                Processing...
              </div>
            )}

            {sources.length > 0 && isProcessingComplete && (
              <div className="mt-3 pt-3 border-t border-border/30">
                <div className="flex items-center gap-2 mb-2">
                  <BookOpen className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-xs font-medium text-muted-foreground">Sources</span>
                </div>
                <div className="space-y-2">
                  {sources.map((source, index) => (
                    <Card key={index} className="p-2 bg-background/50 dark:bg-muted/30 text-xs shadow-none border-border/50">
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="font-medium truncate">{source.title}</span>
                        {source.url && (
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary/80 hover:text-primary hover:underline text-xs"
                          >
                            <Link className="h-3 w-3 inline" /> Visit
                          </a>
                        )}
                      </div>
                      {source.content && (
                        <pre className="text-xs overflow-x-auto p-1.5 bg-black/5 dark:bg-black/20 rounded-sm font-mono">
                          {source.content}
                        </pre>
                      )}
                    </Card>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}