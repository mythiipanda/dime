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

  // Auto-resize textarea height based on content
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'; // Reset height to shrink if needed
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`; // Set to scroll height
    }
  }, [prompt]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedPrompt = prompt.trim();
    if (trimmedPrompt && !isLoading) {
      onSubmit(trimmedPrompt);
      setPrompt(''); // Clear prompt, which will trigger useEffect for resize
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !isLoading) { // Also check !isLoading here
      e.preventDefault();
      handleSubmit(e); // handleSubmit already contains the trim and isLoading check
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className={cn(
        'relative flex w-full items-end gap-2 rounded-xl border bg-card p-2 shadow-sm', // Input bar container
        'focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-background transition-shadow',
        className
      )}
    >
      <textarea
        ref={textareaRef}
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Send a message..." // More generic placeholder
        className={cn(
          "flex-1 resize-none appearance-none bg-transparent px-2 py-2.5 text-base leading-relaxed", // Adjusted padding, bg-transparent
          "min-h-[24px] max-h-[160px]", // Adjusted min/max height for textarea within bar
          "focus:outline-none focus-visible:ring-0 focus-visible:border-transparent border-0", // Remove internal border/ring
          "disabled:cursor-not-allowed disabled:opacity-50 placeholder:text-muted-foreground/80"
        )}
        disabled={isLoading}
        rows={1}
      />
      <div className="flex items-center gap-2 self-end"> {/* Button container */}
        {isLoading && onStop ? (
          <Button
            type="button"
            variant="ghost" // Changed to ghost for a less intrusive stop button
            size="icon"
            onClick={onStop}
            className={cn(
              "h-9 w-9 shrink-0 rounded-lg text-red-500 hover:bg-red-500/10 hover:text-red-600",
              "transition-colors duration-200"
            )}
            title="Stop generating"
          >
            <StopCircleIcon className="h-5 w-5" />
            <span className="sr-only">Stop generating</span>
          </Button>
        ) : (
          <Button
            type="submit"
            disabled={!prompt.trim() || isLoading}
            className={cn(
              "h-9 w-9 shrink-0 rounded-lg", // Adjusted size and rounding
              "bg-primary text-primary-foreground hover:bg-primary/90",
              "disabled:bg-primary/50",
              "transition-all duration-200 active:scale-95"
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