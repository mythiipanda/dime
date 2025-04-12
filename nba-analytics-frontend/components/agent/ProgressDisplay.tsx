// components/agent/ProgressDisplay.tsx
import { Loader2, WrenchIcon, Brain, Database, Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface ProgressStep {
  type: 'tool' | 'thinking' | 'data' | 'complete';
  message: string;
  status: 'loading' | 'complete' | 'error';
}

interface ProgressDisplayProps {
  progressSteps: string[];
  className?: string;
}

export function ProgressDisplay({ progressSteps, className }: ProgressDisplayProps) {
  // Parse progress messages to determine their type
  const parseSteps = (messages: string[]): ProgressStep[] => {
    return messages.map(message => {
      if (message.toLowerCase().includes('tool')) {
        return {
          type: 'tool',
          message,
          status: message.toLowerCase().includes('complete') ? 'complete' : 'loading'
        };
      } else if (message.toLowerCase().includes('thinking') || message.toLowerCase().includes('analyzing')) {
        return {
          type: 'thinking',
          message,
          status: message.toLowerCase().includes('complete') ? 'complete' : 'loading'
        };
      } else if (message.toLowerCase().includes('data') || message.toLowerCase().includes('fetching')) {
        return {
          type: 'data',
          message,
          status: message.toLowerCase().includes('complete') ? 'complete' : 'loading'
        };
      } else {
        return {
          type: 'complete',
          message,
          status: 'complete'
        };
      }
    });
  };

  const steps = parseSteps(progressSteps);

  return (
    <div className={cn("space-y-2", className)}>
      {steps.map((step, index) => (
        <div
          key={index}
          className={cn(
            "flex items-center gap-2 text-sm p-2 rounded-lg transition-colors",
            step.status === 'loading' ? "bg-muted animate-pulse" : "bg-muted/50"
          )}
        >
          {/* Icon based on step type */}
          {step.type === 'tool' && (
            step.status === 'loading' ? (
              <WrenchIcon className="h-4 w-4 animate-spin text-primary" />
            ) : (
              <WrenchIcon className="h-4 w-4 text-primary" />
            )
          )}
          {step.type === 'thinking' && (
            step.status === 'loading' ? (
              <Brain className="h-4 w-4 animate-pulse text-yellow-500" />
            ) : (
              <Brain className="h-4 w-4 text-yellow-500" />
            )
          )}
          {step.type === 'data' && (
            step.status === 'loading' ? (
              <Database className="h-4 w-4 animate-bounce text-blue-500" />
            ) : (
              <Database className="h-4 w-4 text-blue-500" />
            )
          )}
          {step.type === 'complete' && (
            <Check className="h-4 w-4 text-green-500" />
          )}

          {/* Step message */}
          <span className={cn(
            "flex-1",
            step.status === 'error' && "text-destructive",
            step.status === 'complete' && "text-muted-foreground"
          )}>
            {step.message}
          </span>

          {/* Loading spinner for active steps */}
          {step.status === 'loading' && (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          )}
        </div>
      ))}
    </div>
  );
}