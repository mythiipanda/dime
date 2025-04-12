"use client"

// components/agent/PromptInputForm.tsx
import React, { useState, useRef, useEffect } from 'react';
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
        'flex flex-col space-y-2 w-full max-w-4xl mx-auto p-4',
        className
      )}
    >
      <div className="flex items-end space-x-2">
        <textarea
          ref={textareaRef}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about NBA players, teams, games, or stats..."
          className="flex-1 min-h-[40px] max-h-[200px] p-2 rounded-md border border-input bg-background resize-none" /* Spacing: rounded-md */
          disabled={isLoading}
          rows={1}
        />
        <div className="flex-shrink-0">
          {isLoading && onStop ? (
            <Button
              type="button"
              variant="destructive"
              size="icon"
              onClick={onStop}
              className="h-10 w-10"
            >
              <StopCircleIcon className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              type="submit"
              disabled={!prompt.trim() || isLoading}
              className="h-10 w-10"
              size="icon"
            >
              <SendIcon className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </form>
  );
}