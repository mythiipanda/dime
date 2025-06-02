// nba-analytics-frontend/app/(app)/ai-assistant/page.tsx
"use client";

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useLangGraphAgentChatSSE, FrontendChatMessage, IntermediateStep } from '@/lib/hooks/useLangGraphAgentChatSSE';
import { InitialChatScreen } from '@/components/agent/InitialChatScreen';
import { PromptInputForm } from '@/components/agent/PromptInputForm';
import { ErrorDisplay } from '@/components/agent/ErrorDisplay';
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { 
    UserIcon, BotIcon, Wrench, PlayCircle, AlertTriangle, Cpu, ChevronDown, ChevronUp, Copy, Check, BookOpen, Loader2, CheckCircle2, Settings2, Brain
} from 'lucide-react';
import ReactMarkdown, { Components, ExtraProps } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';

const copyToClipboardUtil = async (textToCopy: string, setCopied: (isCopied: boolean) => void) => {
  try {
    await navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  } catch (err) {
    console.error('Failed to copy text: ', err);
  }
};

interface CustomCodeProps extends React.HTMLAttributes<HTMLElement>, ExtraProps {
  inline?: boolean;
  className?: string;
  children?: React.ReactNode;
  isCopiedState?: boolean;
  setIsCopiedState?: (isCopied: boolean) => void;
}

const createMarkdownComponents = (isCopiedState?: boolean, setIsCopiedState?: (isCopied: boolean) => void): Components => ({
    code({ node, inline, className, children, ...props }: CustomCodeProps) {
      const match = /language-(\w+)/.exec(className || '');
      const codeText = String(children).replace(/\n$/, '');
      
      const actualSetIsCopiedState = typeof setIsCopiedState === 'function' ? setIsCopiedState : () => {};

      return !inline ? (
        <div className="relative my-2 group">
          <div className="absolute right-2 top-2 z-10 flex items-center gap-1.5">
            {match && <span className="rounded-sm bg-black/70 px-1.5 py-0.5 text-[10px] font-mono text-white/70">{match[1]}</span>}
            <TooltipProvider><Tooltip><TooltipTrigger asChild>
                <button 
                    className="opacity-0 group-hover:opacity-100 h-5 w-5 p-0 flex items-center justify-center rounded hover:bg-muted/50 transition-opacity"
                    onClick={() => copyToClipboardUtil(codeText, actualSetIsCopiedState)} >
                    {isCopiedState ? <Check className="h-2.5 w-2.5 text-green-500" /> : <Copy className="h-2.5 w-2.5 text-muted-foreground" />}
                </button>
            </TooltipTrigger><TooltipContent><p className="text-xs">{isCopiedState ? 'Copied!' : 'Copy code'}</p></TooltipContent></Tooltip></TooltipProvider>
          </div>
          <pre className="rounded-md border bg-muted/50 p-3 font-mono text-xs overflow-x-auto"><code className={className} {...props}>{children}</code></pre>
        </div>
      ) : (
        <code className="relative rounded bg-muted/70 px-[0.3rem] py-[0.2rem] font-mono text-xs font-semibold" {...props}>
          {children}
        </code>
      );
    },
    p: ({ node, ...props }) => <p className="mb-2 leading-relaxed last:mb-0" {...props} />,
    ul: ({ node, ...props }) => <ul className="my-2 ml-5 list-disc marker:text-muted-foreground [&>li]:mt-1" {...props} />,
    ol: ({ node, ...props }) => <ol className="my-2 ml-5 list-decimal marker:text-muted-foreground [&>li]:mt-1" {...props} />,
    li: ({ node, ...props }) => <li className="leading-relaxed" {...props} />,
    a: ({ node, ...props }) => <a className="font-medium text-primary underline underline-offset-4 hover:text-primary/80" target="_blank" rel="noopener noreferrer" {...props} />,
    strong: ({ node, ...props }) => <strong className="font-semibold text-foreground/90" {...props} />,
    table: ({ node, ...props }) => <div className="overflow-x-auto my-2"><table className="w-full border-collapse border border-border text-xs" {...props} /></div>,
    thead: ({ node, ...props }) => <thead className="bg-muted/50 dark:bg-muted/30" {...props} />,
    th: ({ node, ...props }) => <th className="border border-border px-2 py-1.5 text-left font-medium" {...props} />,
    td: ({ node, ...props }) => <td className="border border-border px-2 py-1.5" {...props} />,
});

const IntermediateStepDisplay: React.FC<{ step: IntermediateStep, index: number }> = ({ step, index }) => {
    const [isExpanded, setIsExpanded] = useState(true); 
    const [isCopied, setIsCopied] = useState(false);

    const stepMarkdownComponents = React.useMemo(() => createMarkdownComponents(isCopied, setIsCopied), [isCopied]);

    switch (step.type) {
        case 'tool_call':
            return (
                <div className="p-2 my-1 rounded-md border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30">
                    <div className="flex items-center gap-2 mb-1">
                        <Wrench className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400 shrink-0" />
                        <span className="text-xs font-semibold text-blue-700 dark:text-blue-400">Tool Call</span>
                    </div>
                    {step.toolCalls?.map(tc => (
                        <div key={tc.id} className="ml-2 pl-2 border-l border-blue-300 dark:border-blue-700 py-1 last:pb-0">
                            <p className="font-mono text-[11px] font-medium text-blue-800 dark:text-blue-300">{tc.name}</p>
                            {tc.args && Object.keys(tc.args).length > 0 && (
                                <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
                                    <CollapsibleTrigger asChild>
                                        <Button variant="link" size="sm" className="text-blue-500 dark:text-blue-400 px-0 h-auto -mt-0.5 text-[10px]">
                                            {isExpanded ? <ChevronUp className="h-2.5 w-2.5 mr-0.5" /> : <ChevronDown className="h-2.5 w-2.5 mr-0.5" />}
                                            Arguments
                                        </Button>
                                    </CollapsibleTrigger>
                                    <CollapsibleContent className="animate-collapsible-down">
                                        <pre className="text-[10px] text-blue-700 dark:text-blue-300 bg-blue-100 dark:bg-blue-900/50 p-1.5 mt-0.5 rounded font-mono max-w-full overflow-x-auto whitespace-pre-wrap break-all">
                                            {JSON.stringify(tc.args, null, 2)}
                                        </pre>
                                    </CollapsibleContent>
                                </Collapsible>
                            )}
                        </div>
                    ))}
                </div>
            );
        case 'tool_result':
            const isErrorResult = step.isError;
            const StatusIcon = isErrorResult ? AlertTriangle : CheckCircle2;
            return (
                <div className={cn(
                    "p-2 my-1 rounded-md border",
                    isErrorResult ? "border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30" : "border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-950/30"
                )}>
                    <div className="flex items-center gap-2 mb-0.5">
                        <StatusIcon className={cn("h-3.5 w-3.5 shrink-0", isErrorResult ? "text-red-600 dark:text-red-400" : "text-green-600 dark:text-green-400")} />
                        <span className={cn("text-xs font-semibold", isErrorResult ? "text-red-700 dark:text-red-400" : "text-green-700 dark:text-green-400")}>
                            Tool Result: {step.toolName} {step.toolCallId && <span className="text-[9px] font-normal text-muted-foreground/70">(ID: {step.toolCallId.slice(-6)})</span>}
                        </span>
                    </div>
                    {step.toolResultContent && (
                         <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
                            <CollapsibleTrigger asChild>
                                <Button variant="link" size="sm" className={cn("px-0 h-auto text-[10px] ml-5 -mt-0.5", isErrorResult ? "text-red-500 dark:text-red-400" : "text-green-500 dark:text-green-400")}>
                                    {isExpanded ? <ChevronUp className="h-2.5 w-2.5 mr-0.5" /> : <ChevronDown className="h-2.5 w-2.5 mr-0.5" />}
                                    {isErrorResult ? "Error Details" : "Output"}
                                </Button>
                            </CollapsibleTrigger>
                            <CollapsibleContent className="animate-collapsible-down">
                                <pre className={cn(
                                    "text-[10px] p-1.5 mt-0.5 rounded font-mono max-w-full overflow-x-auto whitespace-pre-wrap break-all",
                                    isErrorResult ? "bg-red-100 dark:bg-red-900/50 text-red-800 dark:text-red-300" : "bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-300"
                                )}>
                                    {step.toolResultContent}
                                </pre>
                            </CollapsibleContent>
                        </Collapsible>
                    )}
                </div>
            );
        case 'system_event':
            return (
                <div className="p-1.5 my-1 rounded-md border border-purple-200 dark:border-purple-800 bg-purple-50 dark:bg-purple-950/30 flex items-center text-xs">
                    <Settings2 size={12} className="mr-1.5 text-purple-600 dark:text-purple-400 shrink-0" />
                    <span className="text-purple-700 dark:text-purple-300"><span className="font-medium">{step.nodeName || 'System'}:</span> {step.systemEventContent}</span>
                </div>
            );
         case 'thought_chunk':
            return (
                <div className="p-2 my-1 rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/30">
                    <div className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400 mb-1">
                        <Brain size={12} className="shrink-0" /> 
                        <span className="font-medium">Thinking...</span>
                    </div>
                    <div className="prose prose-xs dark:prose-invert max-w-full text-gray-700 dark:text-gray-300 text-[11px] leading-snug">
                        <ReactMarkdown components={stepMarkdownComponents} remarkPlugins={[remarkGfm]}>{step.thoughtChunkContent || ''}</ReactMarkdown>
                    </div>
                </div>
            );
        case 'error_event':
            return (
                <div className="p-2 my-1 rounded-md border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30 flex items-center text-xs">
                    <AlertTriangle size={12} className="mr-1.5 text-red-600 dark:text-red-400 shrink-0" />
                    <span className="text-red-700 dark:text-red-400"><span className="font-medium">Error:</span> {step.errorEventContent}</span>
                </div>
            );
        default: return <div className="text-xs p-1">Unsupported step: {step.type}</div>;
    }
};

const ChatMessageCard: React.FC<{ message: FrontendChatMessage; isLatest: boolean }> = ({ message, isLatest }) => {
  const [isFinalAnswerCopied, setIsFinalAnswerCopied] = useState(false);
  const [isProcessExpanded, setIsProcessExpanded] = useState(message.isStreaming && (!message.content || message.content.length === 0));

  useEffect(() => {
    if (isLatest && message.isStreaming === false && message.content && message.content.length > 0) {
        setIsProcessExpanded(false);
    } else if (isLatest && message.isStreaming && (!message.content || message.content.length === 0)) {
        setIsProcessExpanded(true);
    }
  }, [isLatest, message.isStreaming, message.content]);
  
  const finalAnswerMarkdownComponents = React.useMemo(() => createMarkdownComponents(isFinalAnswerCopied, setIsFinalAnswerCopied), [isFinalAnswerCopied]);

  const renderHumanMessage = () => (
    <Card className="prose prose-sm dark:prose-invert max-w-full rounded-xl bg-primary text-primary-foreground p-3 shadow-md break-words">
      <ReactMarkdown components={finalAnswerMarkdownComponents} remarkPlugins={[remarkGfm]}>{message.content || ''}</ReactMarkdown>
    </Card>
  );

  const renderAIMessage = () => {
    const hasFinalContent = message.content && message.content.length > 0;
    const hasIntermediateSteps = message.intermediateSteps && message.intermediateSteps.length > 0;

    return (
      <Card className="rounded-xl bg-card text-card-foreground p-0 shadow-md w-full break-words">
        {hasIntermediateSteps && (
            <Collapsible open={isProcessExpanded} onOpenChange={setIsProcessExpanded} className="border-b dark:border-border/50">
                <CollapsibleTrigger asChild>
                    <div className="flex items-center justify-between p-2.5 hover:bg-muted/50 dark:hover:bg-muted/20 cursor-pointer rounded-t-xl">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Settings2 size={14} className={cn(message.isStreaming && "animate-spin-slow")} />
                            <span>{message.isStreaming && !hasFinalContent ? "AI is working..." : "Show process"}</span>
                        </div>
                        {isProcessExpanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                    </div>
                </CollapsibleTrigger>
                <CollapsibleContent className="animate-collapsible-down p-2 bg-muted/30 dark:bg-muted/10 max-h-96 overflow-y-auto custom-scrollbar">
                    <div className="space-y-1.5">
                        {message.intermediateSteps?.map((step, idx) => (
                            <IntermediateStepDisplay key={step.id} step={step} index={idx} />
                        ))}
                    </div>
                </CollapsibleContent>
            </Collapsible>
        )}

        {hasFinalContent ? (
            <div className="p-3 final-answer-container prose prose-sm dark:prose-invert max-w-full break-words">
                 <div className="flex items-center justify-between mb-1.5 -mt-0.5">
                    <div className="flex items-center gap-1.5 text-primary">
                        <BookOpen className="h-4 w-4" />
                        <span className="text-xs font-semibold">Final Answer</span>
                    </div>
                    <TooltipProvider>
                        <Tooltip>
                        <TooltipTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => copyToClipboardUtil(message.content!, setIsFinalAnswerCopied)}>
                            {isFinalAnswerCopied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent><p className="text-xs">{isFinalAnswerCopied ? 'Copied!' : 'Copy answer'}</p></TooltipContent>
                        </Tooltip>
                    </TooltipProvider>
                </div>
                <ReactMarkdown components={finalAnswerMarkdownComponents} remarkPlugins={[remarkGfm]}>
                    {message.content}
                </ReactMarkdown>
            </div>
        ) : message.isStreaming && !hasIntermediateSteps ? (
             <div className="flex items-center text-sm opacity-80 p-3">
                <Loader2 size={16} className="mr-2 animate-spin" /> AI is thinking...
            </div>
        ) : null}
      </Card>
    );
  };
  
  let contentWrapper;
  let avatar;
  let messageRowClasses = "flex gap-3 py-2 my-1 items-start";
  let contentContainerClasses = "w-full max-w-[calc(100%-44px)]";

  switch (message.type) {
    case 'human':
      contentWrapper = renderHumanMessage();
      avatar = <Avatar className="h-8 w-8 border shadow-sm shrink-0"><AvatarFallback className="bg-secondary"><UserIcon className="h-5 w-5 text-secondary-foreground" /></AvatarFallback></Avatar>;
      messageRowClasses = "flex gap-3 py-2 my-1 items-end justify-end";
      contentContainerClasses = "max-w-[80%]";
      break;
    case 'ai':
      contentWrapper = renderAIMessage();
      avatar = <Avatar className="h-8 w-8 border shadow-sm shrink-0"><AvatarFallback className="bg-primary/10 text-primary"><BotIcon className="h-5 w-5" /></AvatarFallback></Avatar>;
      break;
    default:
      contentWrapper = <Card className="p-3"><p className="text-xs text-red-500">Unknown message type</p></Card>; 
      avatar = <Avatar className="h-8 w-8 border shadow-sm shrink-0"><AvatarFallback>?</AvatarFallback></Avatar>;
  }

  return (
    <div className={cn(messageRowClasses)}>
      {message.type === 'ai' && avatar}
      <div className={cn("flex flex-col gap-1.5", contentContainerClasses)}>
        {contentWrapper}
      </div>
      {message.type === 'human' && avatar}
    </div>
  );
};

export default function AiAssistantPage() {
  const {
    isLoading,
    error,
    chatHistory,
    submitPrompt,
    closeConnection,
    setChatHistory
  } = useLangGraphAgentChatSSE({ apiUrl: 'http://localhost:8000/api/v1/agent/stream' });

  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chatHistory, isLoading]);

  useEffect(() => {
    return () => closeConnection(true);
  }, [closeConnection]);

  const handlePromptSubmit = useCallback((prompt: string) => {
    const userMessage: FrontendChatMessage = {
        id: Date.now().toString() + '-human',
        type: 'human',
        content: prompt,
    };
    setChatHistory((prev: FrontendChatMessage[]) => [...prev, userMessage]); 
    submitPrompt(prompt);
  }, [submitPrompt, setChatHistory]);

  const handleStop = useCallback(() => closeConnection(),[closeConnection]);

  const renderChatArea = () => {
    if (chatHistory.length === 0 && !isLoading && !error) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center p-4 sm:p-6 bg-gradient-to-br from-background to-muted/30 dark:from-background dark:to-muted/10">
          <div className="w-full max-w-3xl">
            <InitialChatScreen onExampleClick={handlePromptSubmit} />
          </div>
        </div>
      );
    }
    return (
      <ScrollArea className="flex-1 p-4 sm:p-6 bg-muted/10 dark:bg-muted/5" ref={scrollAreaRef}>
        <div className="space-y-0 max-w-3xl mx-auto pb-4">
          {chatHistory.map((msg, index) => (
            <ChatMessageCard
              key={msg.id}
              message={msg}
              isLatest={index === chatHistory.length - 1}
            />
          ))}
          {isLoading && chatHistory.length > 0 && chatHistory[chatHistory.length -1].type === 'human' && (
            <div className={cn("flex gap-3 py-2 my-1 items-start")}>
                <Avatar className="h-8 w-8 border shadow-sm shrink-0"><AvatarFallback className="bg-primary/10 text-primary"><BotIcon className="h-5 w-5" /></AvatarFallback></Avatar>
                <div className={cn("flex flex-col gap-1.5 w-full max-w-[calc(100%-44px)]")}>
                    <Card className="rounded-xl bg-card text-card-foreground p-3 shadow-md break-words w-full">
                        <div className="flex items-center text-sm opacity-80">
                            <Loader2 size={16} className="mr-2 animate-spin" /> AI is connecting...
                        </div>
                    </Card>
                </div>
            </div>
           )}
          {error && 
            <div className="max-w-3xl mx-auto py-2 px-3">
              <ErrorDisplay error={error} />
            </div>
          }
          <div ref={chatEndRef} />
        </div>
      </ScrollArea>
    );
  };

  return (
    <div className="h-full flex flex-col bg-background">
      <main className="flex-1 flex flex-col overflow-hidden">
        {renderChatArea()}
      </main>
      <div className="bg-background border-t p-3 sm:p-4 sticky bottom-0 z-10">
        <div className="max-w-3xl mx-auto space-y-2">
          <PromptInputForm onSubmit={handlePromptSubmit} onStop={handleStop} isLoading={isLoading} />
          <p className="text-xs text-center text-muted-foreground opacity-75 transition-opacity hover:opacity-100">
            AI may produce inaccurate information. Verify important details.
          </p>
        </div>
      </div>
    </div>
  );
}