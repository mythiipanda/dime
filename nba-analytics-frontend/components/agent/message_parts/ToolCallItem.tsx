"use client";

import React from 'react';
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, CheckCircle2, XCircle, AlertCircle, TerminalSquare } from "lucide-react";
import { ToolCall } from "../ChatMessageDisplay"; // Assuming ToolCall interface is exported from ChatMessageDisplay or a shared types file
import { cn } from "@/lib/utils";

interface ToolCallItemProps {
  tool: ToolCall;
  isExpanded: boolean;
  onToggleExpand: () => void;
}

const ToolCallItem: React.FC<ToolCallItemProps> = ({ tool, isExpanded, onToggleExpand }) => {
  const { content, tool_name, status, args, isError } = tool;
  const lines = content?.split('\n') || [];
  const MAX_LINES = 10;
  const MAX_TOOL_CONTENT_CHARS = 500;

  let tempDisplayedContent = content || "";
  let lineTruncated = false;
  let charTruncated = false;

  if (lines.length > MAX_LINES) {
    tempDisplayedContent = lines.slice(0, MAX_LINES).join('\n');
    lineTruncated = true;
  }

  if (tempDisplayedContent.length > MAX_TOOL_CONTENT_CHARS) {
    tempDisplayedContent = tempDisplayedContent.substring(0, MAX_TOOL_CONTENT_CHARS) + "...";
    charTruncated = true;
  }
  
  const isTruncated = lineTruncated || charTruncated;
  const displayedContent = isExpanded || !isTruncated ? content : tempDisplayedContent;

  return (
    <Card className={cn(
      "p-2 bg-background dark:bg-neutral-700/50 shadow-sm border-border/50",
      isError && "border-red-500/50 dark:border-red-400/40 bg-red-500/5 dark:bg-red-900/10"
    )}>
      <div className="flex items-center gap-2">
        {status === "started" && <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />}
        {status === "completed" && !isError && <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />}
        {(status === "error" || isError) && <AlertCircle className="h-3.5 w-3.5 text-red-500" />}
        <div className="flex flex-col">
          <span className="font-mono text-[11px] font-semibold text-foreground">{tool_name}</span>
          {status === "started" && <span className="text-[10px] text-blue-600 dark:text-blue-400">Running...</span>}
          {status === "completed" && !isError && <span className="text-[10px] text-green-600 dark:text-green-400">Completed</span>}
          {(status === "error" || isError) && <span className="text-[10px] text-red-600 dark:text-red-400">Error</span>}
        </div>
      </div>

      {isExpanded && args && Object.keys(args).length > 0 && (
        <div className="mt-1.5 pt-1.5 border-t border-border/30">
          <div className="flex items-center gap-1 mb-0.5">
            <TerminalSquare className="h-3 w-3 text-muted-foreground" />
            <span className="text-[10px] font-medium text-muted-foreground">Arguments:</span>
          </div>
          <pre className="text-[10px] text-muted-foreground/80 bg-muted/30 dark:bg-black/20 p-1.5 rounded font-mono max-w-full overflow-x-auto whitespace-pre-wrap break-all">
            {JSON.stringify(args, null, 2)}
          </pre>
        </div>
      )}

      {content && typeof content === 'string' && content.trim() && (
        <div className="mt-1.5 pt-1.5 border-t border-border/30">
          <div className="flex items-center gap-1 mb-0.5">
            {isError ? <AlertCircle className="h-3 w-3 text-red-500" /> : <CheckCircle2 className="h-3 w-3 text-green-500" />}
            <span className={cn("text-[10px] font-medium", isError ? "text-red-500" : "text-muted-foreground")}>
              {isError ? "Error Details:" : "Output:"}
            </span>
          </div>
          <pre className="text-[10px] text-muted-foreground/80 bg-muted/30 dark:bg-black/20 p-1.5 rounded font-mono max-w-full overflow-x-auto whitespace-pre-wrap break-all">
            {displayedContent}
          </pre>
          {isTruncated && (
            <Button 
              variant="link"
              className="text-xs h-auto p-0 mt-1 text-primary hover:text-primary/80"
              onClick={onToggleExpand}
            >
              {isExpanded ? "Show less" : "Show more..."}
            </Button>
          )}
        </div>
      )}
    </Card>
  );
};

export default ToolCallItem; 