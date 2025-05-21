"use client";

import React from 'react';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Loader2, Lightbulb } from 'lucide-react';

interface ResearchInputFormProps {
  topic: string;
  onTopicChange: (value: string) => void;
  onFetchPromptSuggestions: () => void;
  promptSuggestions: string[];
  onPromptSuggestionClick: (suggestion: string) => void;
  isLoading: boolean; // For main report generation
  isSuggesting: boolean; // For prompt suggestion loading
  textareaRef?: React.RefObject<HTMLTextAreaElement | null>;
}

export function ResearchInputForm({
  topic,
  onTopicChange,
  onFetchPromptSuggestions,
  promptSuggestions,
  onPromptSuggestionClick,
  isLoading,
  isSuggesting,
  textareaRef,
}: ResearchInputFormProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor="research-topic" className="text-lg font-semibold">
        Research Topic
      </Label>
      <p className="text-sm text-muted-foreground">
        Enter a player name (e.g., "LeBron James"), team (e.g., "Los Angeles Lakers analysis"), 
        or a specific concept (e.g., "evolution of the three-point shot in the NBA playoffs").
        Highlight text to get targeted suggestions.
      </p>
      <div className="relative">
        <Textarea
          id="research-topic"
          ref={textareaRef}
          value={topic}
          onChange={(e) => onTopicChange(e.target.value)}
          placeholder="e.g., Nikola Jokic offensive impact and passing skills"
          className="min-h-[100px] pr-28"
          disabled={isLoading || isSuggesting}
        />
        <Button
          variant="ghost"
          size="sm"
          onClick={onFetchPromptSuggestions}
          disabled={isLoading || isSuggesting || !topic.trim()}
          className="absolute bottom-2 right-2"
          aria-label="Get prompt suggestions"
        >
          {isSuggesting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Lightbulb className="h-4 w-4" />
          )}
          <span className="ml-1 hidden sm:inline">Suggest</span>
        </Button>
      </div>
      {promptSuggestions.length > 0 && (
        <div className="mt-2 space-y-1">
          <p className="text-xs text-muted-foreground">Suggestions:</p>
          <div className="flex flex-wrap gap-1">
            {promptSuggestions.map((suggestion, index) => (
              <Button
                key={index}
                variant="outline"
                size="sm"
                onClick={() => onPromptSuggestionClick(suggestion)}
              >
                {suggestion}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
} 