// components/agent/ChatMessageDisplay.tsx
"use client"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { UserIcon, BotIcon, Loader2, CheckCircle2, XCircle, ChevronDown, ChevronUp, Brain } from "lucide-react"
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import { Progress } from "@/components/ui/progress"
import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"

interface ToolCall {
  tool_name: string
  status: "started" | "completed" | "error"
  content?: string
}

interface ChatMessage {
  role: "user" | "assistant"
  content: string
  event?: string
  status?: "thinking" | "error" | "complete"
  progress?: number
  toolCalls?: ToolCall[]
}

interface ChatMessageDisplayProps {
  message: ChatMessage
  isLatest?: boolean
}

export function ChatMessageDisplay({ message, isLatest = false }: ChatMessageDisplayProps) {
  const isUser = message.role === "user"
  const [isThinkingExpanded, setIsThinkingExpanded] = useState(true)
  const [intermediateSteps, setIntermediateSteps] = useState<{
    thinking: string[]
    tools: ToolCall[]
  }>({ thinking: [], tools: [] })
  
  // Update intermediate steps when message changes
  useEffect(() => {
    if (!isUser && message.content) {
      if (message.status === "thinking" || message.event === "RunResponse") {
        setIntermediateSteps(prev => {
          // Skip if content is empty, generic message, or contains "Final Answer"
          if (!message.content || 
              message.content === "Starting to process your request..." ||
              message.content.includes("Final Answer:")) {
            return prev;
          }

          // Create new thinking array with unique entries
          const thoughts: string[] = Array.from(new Set([...prev.thinking, message.content]));
          
          // Filter out redundant thoughts and final answers
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
          
          // Update or add new tools
          message.toolCalls?.forEach(newTool => {
            const existing = existingTools.get(newTool.tool_name);
            if (!existing || existing.status !== newTool.status) {
              existingTools.set(newTool.tool_name, newTool);
            }
          });

          // Convert back to array and sort
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

  const components: Partial<Components> = {
    code: ({ className, children }) => {
      const match = /language-(\w+)/.exec(className || '')
      if (!match) {
        return (
          <code className={cn(
            "rounded-sm bg-muted px-1.5 py-0.5",
            isUser ? "bg-primary-foreground/20" : "bg-primary/10"
          )}>
            {children}
          </code>
        )
      }

      return (
        <div className="relative my-4 rounded-md bg-muted/50">
          <div className="absolute right-3 top-3 text-xs text-muted-foreground">
            {match[1]}
          </div>
          <pre className={cn(
            "overflow-x-auto rounded-lg p-4 text-sm",
            isUser ? "bg-primary-foreground/10" : "bg-primary/5"
          )}>
            <code className="block">{children}</code>
          </pre>
        </div>
      )
    },
    p(props) {
      return <p {...props} className="mb-3 last:mb-0 leading-relaxed" />
    },
    ul(props) {
      return <ul {...props} className="list-disc pl-6 mb-3 last:mb-0 space-y-1" />
    },
    ol(props) {
      return <ol {...props} className="list-decimal pl-6 mb-3 last:mb-0 space-y-1" />
    },
    table(props) {
      return (
        <div className="overflow-x-auto my-4">
          <table {...props} className="min-w-full divide-y divide-border" />
        </div>
      )
    },
    th(props) {
      return <th {...props} className="px-3 py-2 font-semibold bg-muted/50 text-left" />
    },
    td(props) {
      return <td {...props} className="px-3 py-2 border-t" />
    }
  }

  return (
    <div
      className={cn(
        "flex w-full gap-4 p-4",
        isUser ? "flex-row-reverse" : "flex-row",
        isLatest && "animate-in fade-in slide-in-from-bottom-5"
      )}
    >
      <Avatar className={cn(
        "h-10 w-10 ring-2 shrink-0",
        isUser ? "bg-primary ring-primary" : "bg-muted ring-muted"
      )}>
        {isUser ? (
          <>
            <AvatarFallback>
              <UserIcon className="h-5 w-5" />
            </AvatarFallback>
          </>
        ) : (
          <>
            <AvatarFallback>
              <BotIcon className="h-5 w-5" />
            </AvatarFallback>
          </>
        )}
      </Avatar>

      <div className="flex-1 space-y-3">
        {/* User Message */}
        {isUser && (
          <Card className="rounded-2xl px-4 py-3 shadow-md bg-primary text-primary-foreground">
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown components={components}>
                {message.content}
              </ReactMarkdown>
            </div>
          </Card>
        )}

        {/* Assistant Response */}
        {!isUser && (
          <>
            {/* Intermediate Updates Box */}
            {showThinkingProcess && (
              <Card className="rounded-2xl px-4 py-3 shadow-sm bg-muted/5 border border-muted/20">
                <Collapsible
                  open={isThinkingExpanded}
                  onOpenChange={setIsThinkingExpanded}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <CollapsibleTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0 hover:bg-muted/20"
                      >
                        {isThinkingExpanded ? (
                          <ChevronUp className="h-3 w-3" />
                        ) : (
                          <ChevronDown className="h-3 w-3" />
                        )}
                      </Button>
                    </CollapsibleTrigger>
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Brain className="h-3 w-3" />
                      <span className="text-xs font-medium">
                        {isThinking ? "Thinking..." : "Steps"}
                      </span>
                    </div>
                    {message.progress !== undefined && (
                      <Progress 
                        value={message.progress} 
                        className="h-1 flex-1"
                      />
                    )}
                  </div>

                  <CollapsibleContent className="space-y-2">
                    {/* Show intermediate thinking content */}
                    {intermediateSteps.thinking.map((thought, index) => (
                      <div 
                        key={`thought-${index}-${thought.substring(0, 20)}`} 
                        className={cn(
                          "rounded-lg p-2.5 text-xs",
                          index % 2 === 0 
                            ? "bg-blue-500/5 border border-blue-500/10" 
                            : "bg-purple-500/5 border border-purple-500/10"
                        )}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <Brain className="h-3 w-3 text-muted-foreground" />
                          <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
                            Reasoning Step {index + 1}
                          </span>
                        </div>
                        <div className="text-foreground">
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
                          "rounded-lg p-2.5 text-xs",
                          tool.status === "started" 
                            ? "bg-yellow-500/5 border border-yellow-500/10" 
                            : tool.status === "completed" 
                              ? "bg-green-500/5 border border-green-500/10" 
                              : "bg-red-500/5 border border-red-500/10"
                        )}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          {tool.status === "started" && (
                            <Loader2 className="h-3 w-3 animate-spin text-yellow-500" />
                          )}
                          {tool.status === "completed" && (
                            <CheckCircle2 className="h-3 w-3 text-green-500" />
                          )}
                          {tool.status === "error" && (
                            <XCircle className="h-3 w-3 text-red-500" />
                          )}
                          <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
                            {tool.tool_name}
                          </span>
                        </div>
                        {tool.content && (
                          <div className="text-foreground">
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
              "rounded-2xl px-4 py-3",
              !isComplete 
                ? "shadow-sm bg-card" 
                : "bg-gradient-to-br from-blue-500/5 to-purple-500/5 border border-blue-500/10"
            )}>
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <div className={cn(
                  "transition-opacity duration-200",
                  isThinking ? "opacity-50" : "opacity-100"
                )}>
                  <ReactMarkdown components={components}>
                    {isComplete ? message.content : (message.content || "Thinking...")}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}