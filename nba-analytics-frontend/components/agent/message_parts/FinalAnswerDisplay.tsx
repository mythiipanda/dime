"use client";

import React from 'react';
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Copy, Check, BookOpen } from "lucide-react";
import { GenerativeUIRenderer } from '../GenerativeUIRenderer';

const FINAL_ANSWER_MARKER = "FINAL_ANSWER::";

interface ToolCall {
  tool_name: string;
  content?: string;
  status: string;
  args?: any;
}

export interface FinalAnswerDisplayProps {
  content: string;
  onCopy: (text: string) => Promise<void>;
  copied: boolean;
  markdownComponents: Components;
  generativeUIContent?: string;
  toolCalls?: ToolCall[];
}

export const FinalAnswerDisplay: React.FC<FinalAnswerDisplayProps> = ({
  content,
  onCopy,
  copied,
  markdownComponents,
  generativeUIContent,
  toolCalls
}) => {
  const displayContent = content.startsWith(FINAL_ANSWER_MARKER)
    ? content.substring(FINAL_ANSWER_MARKER.length)
    : content;

  return (
    <div className="final-answer-container prose prose-sm dark:prose-invert max-w-full break-words">
      <div className="flex items-center justify-between mb-1.5 -mt-0.5">
          <div className="flex items-center gap-1.5 text-primary">
            <BookOpen className="h-4 w-4" />
            <span className="text-xs font-semibold">Final Answer</span>
          </div>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => onCopy(displayContent)}>
                  {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
                </Button>
              </TooltipTrigger>
              <TooltipContent><p className="text-xs">{copied ? 'Copied!' : 'Copy answer'}</p></TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

      {/* Generative UI Components - Render before markdown content */}
      {generativeUIContent && (
        <GenerativeUIRenderer
          content={generativeUIContent}
          toolCalls={toolCalls}
        />
      )}

      <ReactMarkdown components={markdownComponents} remarkPlugins={[remarkGfm]}>
        {displayContent || ''}
      </ReactMarkdown>
    </div>
  );
};