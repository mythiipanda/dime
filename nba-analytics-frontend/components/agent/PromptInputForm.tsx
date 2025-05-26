"use client"

import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { SendIcon, Loader2Icon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PromptInputFormProps {
  onSubmit: (prompt: string) => void;
  onStop?: () => void;
  isLoading?: boolean;
  className?: string;
}

export function PromptInputForm({
  onSubmit,
  onStop,
  isLoading = false,
  className,
}: PromptInputFormProps) {
  const [prompt, setPrompt] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.transition = 'height 0.15s ease-out';
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [prompt]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedPrompt = prompt.trim();
    if (trimmedPrompt && !isLoading) {
      onSubmit(trimmedPrompt);
      setPrompt('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !isLoading) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className={cn(
        'relative flex w-full items-end gap-2 rounded-xl border bg-card p-3 shadow-md',
        'focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-background transition-shadow',
        className
      )}
    >
      <textarea
        ref={textareaRef}
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask Dime about stats, players, or game analysis... or type '/' for commands."
        className={cn(
          "flex-1 resize-none appearance-none bg-transparent px-3 py-2 text-base leading-relaxed",
          "min-h-[40px] max-h-[150px]",
          "focus:outline-none focus-visible:ring-0 focus-visible:border-transparent border-0",
          "disabled:cursor-not-allowed disabled:opacity-60 placeholder:text-muted-foreground/70"
        )}
        disabled={isLoading}
        rows={1}
      />
      <div className="flex items-center gap-2 self-end">
        {isLoading && onStop ? (
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={onStop}
            className={cn(
              "h-9 w-9 shrink-0 rounded-lg text-muted-foreground hover:bg-muted/60",
              "transition-colors duration-200"
            )}
            title="Stop generating"
          >
            <Loader2Icon className="h-5 w-5 animate-spin" />
            <span className="sr-only">Stop generating</span>
          </Button>
        ) : (
          <Button
            type="submit"
            disabled={!prompt.trim() || isLoading}
            className={cn(
              "h-9 w-9 shrink-0 rounded-lg",
              "bg-primary text-primary-foreground hover:bg-primary/90 active:scale-95",
              "disabled:bg-muted disabled:text-muted-foreground/80 disabled:cursor-not-allowed",
              "transition-all duration-200 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            )}
            size="icon"
            title="Send message"
          >
            <SendIcon className="h-4 w-4" />
            <span className="sr-only">Send message</span>
          </Button>
        )}
      </div>
    </form>
  );
}