// components/agent/ChatMessageDisplay.tsx
"use client"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { UserIcon, BotIcon, Loader2, CheckCircle2, XCircle, ChevronDown, ChevronUp, Brain, Copy, Check, Link, BookOpen } from "lucide-react"
import ReactMarkdown, { Components } from 'react-markdown' // Removed ReactMarkdownProps
import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ChatMessage as SSEChatMessage } from "@/lib/hooks/useAgentChatSSE" // Ensure this path is correct
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import remarkGfm from 'remark-gfm' // For GitHub Flavored Markdown (tables, etc.)

// Keep ToolCall and Source interfaces as they are if they are used by other parts or for future use
interface ToolCall {
  tool_name: string
  status: "started" | "completed" | "error"
  content?: string // This might hold arguments or brief results
}

interface Source {
  title: string
  url?: string
  content?: string
}

interface ChatMessageDisplayProps {
  message: SSEChatMessage
  isLatest?: boolean // Might be useful for auto-expanding the latest assistant message's thinking process
}

const FINAL_ANSWER_MARKER = "FINAL_ANSWER::";

export function ChatMessageDisplay({ message, isLatest = false }: ChatMessageDisplayProps) {
  const isUser = message.role === "user"
  const [isThinkingExpanded, setIsThinkingExpanded] = useState(isLatest && !isUser) // Auto-expand latest assistant message
  const [copied, setCopied] = useState(false)
  const [sources, setSources] = useState<Source[]>([])
  const [expandedToolContent, setExpandedToolContent] = useState<{ [key: number]: boolean }>({}); // State for tool content expansion
  
  const [reasoningNarrative, setReasoningNarrative] = useState<string>("")
  const [finalAnswerForDisplay, setFinalAnswerForDisplay] = useState<string>("")

  useEffect(() => {
    if (isUser || !message.content) {
      setReasoningNarrative("");
      setFinalAnswerForDisplay(message.content || ""); // User message content or empty for assistant before content
      return;
    }

    let fullContent = message.content || "";
    let reasoning = fullContent;
    let finalPart = "";

    const markerIndex = fullContent.indexOf(FINAL_ANSWER_MARKER);

    if (markerIndex !== -1) {
      reasoning = fullContent.substring(0, markerIndex).trim();
      finalPart = fullContent.substring(markerIndex + FINAL_ANSWER_MARKER.length).trim();
    } else if (message.status === 'complete' && !message.dataType) {
      // If complete and no marker, and no rich data, assume all content is the final answer.
      // The reasoning part would be the same in this case if we want to show the full log.
      // For a cleaner separation, if no marker, the "reasoning" could be empty or a summary.
      // Let's keep reasoning as the full content for the collapsible for now.
      finalPart = fullContent; // The main display will show this.
      // Reasoning will also show this full content in the collapsible.
    }
    
    setReasoningNarrative(reasoning);
    setFinalAnswerForDisplay(finalPart);

    // Extract sources from tool calls (simplified)
    const newSources: Source[] = [];
    message.toolCalls?.forEach(tool => {
      if (tool.status === 'completed' && tool.content) {
        // Basic source extraction, can be made more sophisticated
        newSources.push({ title: `${tool.tool_name} Result`, content: typeof tool.content === 'string' ? tool.content : JSON.stringify(tool.content, null, 2) });
      }
    });
    if (newSources.length > 0) {
      setSources(prevSrc => {
        const existingTitles = new Set(prevSrc.map(s => s.title + s.content)); // More robust duplicate check
        const uniqueNewSources = newSources.filter(ns => !existingTitles.has(ns.title + ns.content));
        return [...prevSrc, ...uniqueNewSources];
      });
    }

  }, [message.content, message.toolCalls, message.status, isUser, message.dataType]);

  const isProcessingComplete = message.status === "complete";
  const hasReasoningToShow = reasoningNarrative && reasoningNarrative.length > 0;
  const hasToolsToShow = message.toolCalls && message.toolCalls.length > 0;
  const showThinkingProcessCollapsible = !isUser && (hasReasoningToShow || hasToolsToShow);

  const copyToClipboard = async (textToCopy: string) => {
    try {
      await navigator.clipboard.writeText(textToCopy)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy text: ', err)
    }
  }
  
  const markdownComponents: Components = {
    code(props) {
      const { className, children, ...rest } = props;
      const match = /language-(\w+)/.exec(className || '');
      const codeText = String(children).replace(/\n$/, '');
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
                    <Button variant="ghost" size="icon" className="opacity-0 group-hover:opacity-100 h-5 w-5 transition-opacity" onClick={() => copyToClipboard(codeText)}>
                      {copied ? <Check className="h-2.5 w-2.5" /> : <Copy className="h-2.5 w-2.5" />}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent><p className="text-xs">{copied ? 'Copied!' : 'Copy code'}</p></TooltipContent>
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
    strong: ({node, ...props}) => <strong className="font-semibold text-foreground/90" {...props} />, // For **Planning:** etc.
    table: ({node, ...props}) => <div className="overflow-x-auto my-3"><table className="w-full border-collapse border border-border text-xs" {...props} /></div>,
    thead: ({node, ...props}) => <thead className="bg-muted/50 dark:bg-muted/30" {...props} />,
    th: ({node, ...props}) => <th className="border border-border px-2 py-1.5 text-left font-medium" {...props} />,
    td: ({node, ...props}) => <td className="border border-border px-2 py-1.5" {...props} />,
  };

  return (
    <div className={cn("group relative flex gap-x-3 sm:gap-x-4 py-5", isUser ? "flex-row-reverse" : "flex-row")}>
      <Avatar className={cn("h-7 w-7 sm:h-8 sm:w-8 ring-1 mt-0.5", isUser ? "bg-primary/10 ring-primary/30" : "bg-muted ring-border")}>
        <AvatarFallback className={cn("text-[10px] sm:text-xs",isUser ? "text-primary" : "text-muted-foreground")}>
          {isUser ? <UserIcon className="h-3.5 w-3.5 sm:h-4 sm:w-4" /> : <BotIcon className="h-3.5 w-3.5 sm:h-4 sm:w-4" />}
        </AvatarFallback>
      </Avatar>

      <div className={cn("flex-1 space-y-2.5", isUser ? "flex flex-col items-end" : "flex flex-col items-start")}>
        {isUser && (
          <Card className="prose prose-sm dark:prose-invert max-w-full rounded-xl bg-primary text-primary-foreground p-3 shadow-md break-words">
            <ReactMarkdown components={markdownComponents} remarkPlugins={[remarkGfm]}>{message.content || ''}</ReactMarkdown>
          </Card>
        )}

        {!isUser && (
          <Card className="w-full max-w-2xl rounded-xl bg-background dark:bg-neutral-800 p-3 sm:p-4 shadow-lg border border-border/60 space-y-3">
            {showThinkingProcessCollapsible && (
              <Collapsible open={isThinkingExpanded} onOpenChange={setIsThinkingExpanded} className="border-b border-border/30 pb-2 mb-2 last:border-b-0 last:pb-0 last:mb-0">
                <CollapsibleTrigger className="flex items-center justify-between w-full group/trigger py-1 hover:bg-muted/50 dark:hover:bg-muted/30 rounded-md px-1.5 -mx-1.5 transition-colors">
                  <div className="flex items-center gap-2">
                    <Brain className="h-4 w-4 text-muted-foreground group-hover/trigger:text-primary transition-colors" />
                    <span className="text-xs font-medium text-muted-foreground group-hover/trigger:text-primary transition-colors">Agent Process</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {message.status === 'thinking' && message.event !== "RunCompleted" && (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
                        {message.event === "ReasoningStarted" ? (
                          <span className="text-xs text-muted-foreground">Initiating...</span>
                        ) : message.toolCalls && message.toolCalls.some(tc => tc.status === 'started') ? (
                          <span className="text-xs text-muted-foreground">Using Tools...</span>
                        ) : (
                          <span className="text-xs text-muted-foreground">Thinking...</span>
                        )}
                      </>
                    )}
                    {message.status === 'complete' && (hasReasoningToShow || hasToolsToShow) && (
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
                    
                    {hasToolsToShow && (
                      <div className="space-y-1.5 mt-2 pt-2 border-t border-border/30">
                        <div className="text-xs font-medium text-muted-foreground mb-1">Tool Activity:</div>
                        {message.toolCalls?.map((tool, index) => (
                          <Card key={`${tool.tool_name}-${index}-${tool.status}`} className="p-2 bg-background dark:bg-neutral-700/50 shadow-sm border-border/50">
                            <div className="flex items-center gap-2">
                              {tool.status === "started" && <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />}
                              {tool.status === "completed" && <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />}
                              {tool.status === "error" && <XCircle className="h-3.5 w-3.5 text-red-500" />}
                              <div className="flex flex-col">
                                <span className="font-mono text-[11px] font-semibold text-foreground">{tool.tool_name}</span>
                                {tool.status === "started" && <span className="text-[10px] text-blue-600 dark:text-blue-400">Running...</span>}
                                {tool.status === "completed" && <span className="text-[10px] text-green-600 dark:text-green-400">Completed</span>}
                                {tool.status === "error" && <span className="text-[10px] text-red-600 dark:text-red-400">Error</span>}
                              </div>
                            </div>
                            {tool.content && typeof tool.content === 'string' && tool.content.trim() && (() => {
                              const toolContentKey = index; // Use index as key for expansion state
                              const isExpanded = expandedToolContent[toolContentKey] || false;
                              const lines = tool.content.split('\n');
                              const MAX_LINES = 10;
                              const isTruncated = lines.length > MAX_LINES;
                              const displayedContent = isExpanded || !isTruncated ? tool.content : lines.slice(0, MAX_LINES).join('\n');

                              return (
                                <div className="mt-1.5">
                                  <pre className="text-[10px] text-muted-foreground/80 bg-muted/30 dark:bg-black/20 p-1.5 rounded font-mono max-w-full overflow-x-auto whitespace-pre-wrap break-all">
                                    {displayedContent}
                                  </pre>
                                  {isTruncated && (
                                    <Button 
                                      variant="link"
                                      className="text-xs h-auto p-0 mt-1 text-primary hover:text-primary/80"
                                      onClick={() => setExpandedToolContent(prev => ({...prev, [toolContentKey]: !isExpanded}))}
                                    >
                                      {isExpanded ? "Show less" : "Show more..."}
                                    </Button>
                                  )}
                                </div>
                              );
                            })()}
                          </Card>
                        ))}
                      </div>
                    )}
                    {!hasReasoningToShow && !hasToolsToShow && message.status !== 'complete' && (
                      <p className="italic text-muted-foreground">Agent is initializing...</p>
                    )}
                  </div>
                </CollapsibleContent>
              </Collapsible>
            )}

            {/* Main content area: Final Answer or Rich Data */}
            {message.dataType && message.dataPayload && (
              <div className="mt-2.5 pt-2.5 border-t border-border/30">
                {message.dataType === "TABLE_DATA" && (
                  <div className="rich-table">
                    {message.dataPayload.title && <h4 className="text-sm font-semibold mb-1.5">{message.dataPayload.title}</h4>}
                    {/* Placeholder: Actual table component needed here */}
                    <pre className="text-xs bg-muted/50 dark:bg-muted/30 p-2 rounded overflow-x-auto font-mono border border-border/40">
                      {JSON.stringify(message.dataPayload, null, 2)}
                    </pre>
                    {message.dataPayload.caption && <p className="text-xs text-muted-foreground mt-1 italic">{message.dataPayload.caption}</p>}
                  </div>
                )}
                {message.dataType === "CHART_DATA" && (
                   <div className="rich-chart">
                    {message.dataPayload.title && <h4 className="text-sm font-semibold mb-1.5">{message.dataPayload.title}</h4>}
                    <Card className="p-3 border-border/40 bg-muted/50 dark:bg-muted/30"> {/* Placeholder for chart */}
                       <pre className="text-xs font-mono">CHART_PLACEHOLDER: {JSON.stringify(message.dataPayload.data)}</pre>
                    </Card>
                  </div>
                )}
                {message.dataType === "STAT_CARD" && (
                  <Card className="p-3.5 bg-gradient-to-br from-primary/10 to-background border-primary/30 shadow-lg">
                    <div className="text-sm font-medium text-muted-foreground">{message.dataPayload.label}</div>
                    <div className="text-3xl font-bold text-primary mt-0.5">{message.dataPayload.value} {message.dataPayload.unit || ""}</div>
                    {message.dataPayload.description && <div className="text-xs text-muted-foreground mt-1.5">{message.dataPayload.description}</div>}
                  </Card>
                )}
              </div>
            )}
            
            {isProcessingComplete && finalAnswerForDisplay && (!message.dataType || !message.dataPayload) && (
              <div className="prose prose-sm sm:prose-base dark:prose-invert max-w-none relative mt-2.5 pt-2.5 border-t border-border/30">
                {finalAnswerForDisplay && ( 
                  <div className="absolute top-1 right-0 z-10">
                     <TooltipProvider>
                       <Tooltip>
                         <TooltipTrigger asChild>
                           <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-foreground" onClick={() => copyToClipboard(finalAnswerForDisplay)}>
                             {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                           </Button>
                         </TooltipTrigger>
                         <TooltipContent><p className="text-xs">{copied ? 'Copied!' : 'Copy final answer'}</p></TooltipContent>
                       </Tooltip>
                     </TooltipProvider>
                  </div>
                )}
                <ReactMarkdown components={markdownComponents} remarkPlugins={[remarkGfm]}>
                  {finalAnswerForDisplay}
                </ReactMarkdown>
              </div>
            )}

            {message.status === 'thinking' && !showThinkingProcessCollapsible && !message.dataType && reasoningNarrative.length === 0 && (!message.toolCalls || message.toolCalls.length === 0) && ( 
              <div className="prose prose-sm sm:prose-base dark:prose-invert max-w-none text-muted-foreground italic mt-2">
                Agent is processing...
              </div>
            )}

            {sources.length > 0 && isProcessingComplete && (
              <div className="mt-3 pt-3 border-t border-border/30">
                <div className="flex items-center gap-2 mb-1.5">
                  <BookOpen className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-xs font-medium text-muted-foreground">Sources</span>
                </div>
                <div className="space-y-1.5">
                  {sources.map((source, index) => (
                    <Card key={index} className="p-2 bg-muted/30 dark:bg-muted/20 text-xs shadow-none border-border/40">
                      <div className="flex items-center justify-between gap-2 mb-0.5">
                        <span className="font-medium truncate text-foreground/90">{source.title}</span>
                        {source.url && (
                          <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-primary/90 hover:text-primary hover:underline text-[11px] flex items-center gap-0.5">
                            <Link className="h-2.5 w-2.5" /> Visit
                          </a>
                        )}
                      </div>
                      {source.content && (
                        <pre className="text-[11px] text-muted-foreground/80 overflow-x-auto p-1.5 bg-background/50 dark:bg-black/20 rounded-sm font-mono whitespace-pre-wrap break-all">
                          {source.content}
                        </pre>
                      )}
                    </Card>
                  ))}
                </div>
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}