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
      "p-2 shadow-sm border-2 border-l-4",
      status === "started" ? "bg-blue-50 dark:bg-blue-950/30 border-blue-300 dark:border-blue-800" :
      isError ? "bg-red-50 dark:bg-red-950/30 border-red-300 dark:border-red-800" :
      "bg-green-50 dark:bg-green-950/30 border-green-300 dark:border-green-800"
    )}>
      <div className="flex items-center gap-2">
        {status === "started" && <Loader2 className="h-4 w-4 animate-spin text-blue-600 dark:text-blue-400" />}
        {status === "completed" && !isError && <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />}
        {(status === "error" || isError) && <AlertCircle className="h-4 w-4 text-red-600 dark:text-red-400" />}
        <div className="flex flex-col">
          <span className="font-mono text-xs font-bold text-foreground">{tool_name}</span>
          {status === "started" && <span className="text-[11px] font-medium text-blue-700 dark:text-blue-400">Running...</span>}
          {status === "completed" && !isError && <span className="text-[11px] font-medium text-green-700 dark:text-green-400">Completed</span>}
          {(status === "error" || isError) && <span className="text-[11px] font-medium text-red-700 dark:text-red-400">Error</span>}
        </div>
      </div>

      {isExpanded && args && Object.keys(args).length > 0 && (
        <div className="mt-2 pt-2 border-t border-border/30">
          <div className="flex items-center gap-1.5 mb-1">
            <TerminalSquare className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" />
            <span className="text-[11px] font-semibold text-blue-700 dark:text-blue-400">Arguments:</span>
          </div>
          <pre className="text-[11px] text-blue-800 dark:text-blue-300 bg-blue-100 dark:bg-blue-950/40 p-2 rounded font-mono max-w-full overflow-x-auto whitespace-pre-wrap break-all">
            {JSON.stringify(args, null, 2)}
          </pre>
        </div>
      )}

      {content && typeof content === 'string' && content.trim() && (
        <div className="mt-2 pt-2 border-t border-border/30">
          <div className="flex items-center gap-1.5 mb-1">
            {isError ?
              <AlertCircle className="h-3.5 w-3.5 text-red-600 dark:text-red-400" /> :
              <CheckCircle2 className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
            }
            <span className={cn(
              "text-[11px] font-semibold",
              isError ? "text-red-700 dark:text-red-400" : "text-green-700 dark:text-green-400"
            )}>
              {isError ? "Error Details:" : "Output:"}
            </span>
          </div>
          <pre className={cn(
            "text-[11px] p-2 rounded font-mono max-w-full overflow-x-auto whitespace-pre-wrap break-all",
            isError ?
              "bg-red-100 dark:bg-red-950/40 text-red-800 dark:text-red-300" :
              "bg-green-100 dark:bg-green-950/40 text-green-800 dark:text-green-300"
          )}>
            {displayedContent}
          </pre>
          {isTruncated && (
            <Button
              variant="link"
              className="text-xs h-auto p-0 mt-1.5 font-medium"
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