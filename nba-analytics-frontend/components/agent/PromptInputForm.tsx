"use client"

// components/agent/PromptInputForm.tsx
import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { SendIcon, StopCircleIcon } from 'lucide-react';
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
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [prompt]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (prompt.trim() && !isLoading) {
      onSubmit(prompt.trim());
      setPrompt('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className={cn(
        'relative flex w-full items-center gap-2',
        className
      )}
    >
      <textarea
        ref={textareaRef}
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about NBA players, teams, games, or stats..."
        className={cn(
          "flex-1 resize-none rounded-xl border bg-background px-4 py-3",
          "min-h-[48px] max-h-[200px] text-base leading-relaxed",
          "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
          "disabled:cursor-not-allowed disabled:opacity-50"
        )}
        disabled={isLoading}
        rows={1}
      />
      {isLoading && onStop ? (
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={onStop}
          className={cn(
            "h-12 w-12 shrink-0 rounded-xl",
            "border-2 border-red-500 hover:bg-red-500/10",
            "transition-colors duration-200"
          )}
        >
          <StopCircleIcon className="h-5 w-5 text-red-500" />
          <span className="sr-only">Stop generating</span>
        </Button>
      ) : (
        <Button
          type="submit"
          disabled={!prompt.trim() || isLoading}
          className={cn(
            "h-12 w-12 shrink-0 rounded-xl",
            "bg-primary hover:bg-primary/90",
            "transition-colors duration-200"
          )}
          size="icon"
        >
          <SendIcon className="h-5 w-5" />
          <span className="sr-only">Send message</span>
        </Button>
      )}
    </form>
  );
}