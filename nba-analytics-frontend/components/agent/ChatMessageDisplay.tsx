// components/agent/ChatMessageDisplay.tsx
"use client"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { UserIcon, BotIcon, Loader2, CheckCircle2, XCircle, ChevronDown, ChevronUp, Brain, Copy, Check } from "lucide-react"
import ReactMarkdown, { Components } from 'react-markdown'
import { Progress } from "@/components/ui/progress"
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

interface ChatMessageDisplayProps {
  message: SSEChatMessage
  isLatest?: boolean
}

export function ChatMessageDisplay({ message, isLatest = false }: ChatMessageDisplayProps) {
  const isUser = message.role === "user"
  const [isThinkingExpanded, setIsThinkingExpanded] = useState(true)
  const [copied, setCopied] = useState(false)
  const [intermediateSteps, setIntermediateSteps] = useState<{
    thinking: string[]
    tools: ToolCall[]
  }>({ thinking: [], tools: [] })
  
  // Update intermediate steps when message changes
  useEffect(() => {
    if (!isUser && message.content) {
      if (message.status === "thinking" || message.event === "RunResponse") {
        setIntermediateSteps(prev => {
          if (!message.content || 
              message.content === "Starting to process your request..." ||
              message.content.includes("Final Answer:")) {
            return prev;
          }

          const thoughts: string[] = Array.from(new Set([...prev.thinking, message.content]));
          
          const uniqueThoughts = thoughts.filter(thought => 
            !thoughts.some(other => 
              other !== thought && 
              other.includes(thought) && 
              other.length > thought.length
            ) && !thought.includes("Final Answer:")
          );

          return {
            ...prev,
            thinking: uniqueThoughts
          };
        });
      }
      
      if (message.toolCalls?.length) {
        setIntermediateSteps(prev => {
          const existingTools = new Map(prev.tools.map(tool => [tool.tool_name, tool]));
          
          message.toolCalls?.forEach(newTool => {
            const existing = existingTools.get(newTool.tool_name);
            if (!existing || existing.status !== newTool.status) {
              existingTools.set(newTool.tool_name, newTool);
            }
          });

          const sortedTools = Array.from(existingTools.values())
            .sort((a, b) => {
              const statusOrder = { started: 0, completed: 1, error: 2 };
              return (statusOrder[a.status] || 0) - (statusOrder[b.status] || 0);
            });

          return {
            ...prev,
            tools: sortedTools
          };
        });
      }
    }
  }, [message.content, message.toolCalls, isUser, message.event, message.status]);

  const isThinking = message.status === "thinking" || message.event === "RunResponse"
  const isComplete = message.status === "complete"
  const hasIntermediateContent = intermediateSteps.thinking.length > 0 || intermediateSteps.tools.length > 0
  const showThinkingProcess = !isUser && (isThinking || hasIntermediateContent)

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy text: ', err)
    }
  }

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
    <div
      className={cn(
        "group relative flex gap-6 py-6",
        isUser ? "flex-row-reverse" : "flex-row",
        isLatest && "animate-in fade-in slide-in-from-bottom-2 duration-300"
      )}
    >
      <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center">
        <Avatar className={cn(
          "h-8 w-8 ring-2 transition-colors",
          isUser 
            ? "bg-background ring-border" 
            : "bg-background ring-border"
        )}>
          <AvatarFallback>
            {isUser ? (
              <UserIcon className="h-4 w-4 text-white" />
            ) : (
              <BotIcon className="h-4 w-4 text-white" />
            )}
          </AvatarFallback>
        </Avatar>
      </div>

      <div className={cn(
        "flex-1 space-y-4",
        isUser && "items-end"
      )}>
        {/* User Message */}
        {isUser && (
          <div className={cn(
            "prose prose-neutral dark:prose-invert max-w-none",
            "rounded-lg border bg-background p-4",
            "shadow-sm transition-colors hover:border-border"
          )}>
            <ReactMarkdown components={components}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {/* Assistant Response */}
        {!isUser && (
          <>
            {/* Intermediate Updates Box */}
            {showThinkingProcess && (
              <Card className={cn(
                "rounded-lg border bg-background p-4",
                "shadow-sm transition-colors hover:border-border"
              )}>
                <Collapsible
                  open={isThinkingExpanded}
                  onOpenChange={setIsThinkingExpanded}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <CollapsibleTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 hover:bg-accent"
                      >
                        {isThinkingExpanded ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                        <span className="sr-only">
                          {isThinkingExpanded ? "Hide details" : "Show details"}
                        </span>
                      </Button>
                    </CollapsibleTrigger>
                    <div className="flex items-center gap-2">
                      <Brain className="h-4 w-4 text-foreground" />
                      <span className="text-sm font-medium">
                        {isThinking ? "Thinking..." : "Steps"}
                      </span>
                    </div>
                    {message.progress !== undefined && (
                      <Progress 
                        value={message.progress} 
                        className="h-1.5 flex-1"
                      />
                    )}
                  </div>

                  <CollapsibleContent className="space-y-3">
                    {/* Show intermediate thinking content */}
                    {intermediateSteps.thinking.map((thought, index) => (
                      <div 
                        key={`thought-${index}-${thought.substring(0, 20)}`} 
                        className={cn(
                          "rounded-lg border p-3 text-sm transition-colors",
                          index % 2 === 0 
                            ? "border bg-background hover:border-border" 
                            : "border bg-accent hover:border-border"
                        )}
                      >
                        <div className="flex items-center gap-2 mb-2">
                          <Brain className="h-3.5 w-3.5 text-muted-foreground" />
                          <span className="text-xs font-medium tracking-wide text-muted-foreground">
                            Reasoning Step {index + 1}
                          </span>
                        </div>
                        <div className="prose prose-sm prose-neutral dark:prose-invert">
                          <ReactMarkdown components={components}>
                            {thought}
                          </ReactMarkdown>
                        </div>
                      </div>
                    ))}
                    
                    {/* Show tool calls */}
                    {intermediateSteps.tools.map((tool) => (
                      <div 
                        key={`${tool.tool_name}-${tool.status}`}
                        className={cn(
                          "rounded-lg border p-3 text-sm transition-colors",
                          tool.status === "started" 
                            ? "border bg-background hover:border-border" 
                            : tool.status === "completed" 
                              ? "border bg-background hover:border-border" 
                              : "border bg-destructive/10 hover:border-border"
                        )}
                      >
                        <div className="flex items-center gap-2 mb-2">
                          {tool.status === "started" && (
                            <Loader2 className="h-3.5 w-3.5 animate-spin text-yellow-600" />
                          )}
                          {tool.status === "completed" && (
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                          )}
                          {tool.status === "error" && (
                            <XCircle className="h-3.5 w-3.5 text-red-600" />
                          )}
                          <span className="text-xs font-medium tracking-wide text-muted-foreground">
                            {tool.tool_name}
                          </span>
                        </div>
                        {tool.content && (
                          <div className="prose prose-sm prose-neutral dark:prose-invert">
                            <ReactMarkdown components={components}>
                              {tool.content}
                            </ReactMarkdown>
                          </div>
                        )}
                      </div>
                    ))}
                  </CollapsibleContent>
                </Collapsible>
              </Card>
            )}

            {/* Final Response */}
            <div className={cn(
              "prose prose-neutral dark:prose-invert max-w-none",
              "rounded-2xl border p-4 transition-all duration-200",
              !isComplete 
                ? "border bg-background shadow-sm" 
                : "border bg-background shadow-sm hover:border-border",
              isThinking && "opacity-60"
            )}>
              <ReactMarkdown components={components}>
                {isComplete ? message.content : (message.content || "Thinking...")}
              </ReactMarkdown>
            </div>
          </>
        )}
      </div>
    </div>
  )
}