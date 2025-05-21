"use client";

import * as React from "react";
import { useState, useEffect } from "react";
import { Suggestion } from "@/app/(app)/players/types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Search } from "lucide-react";
import { usePlayerSearchSuggestions } from "@/hooks/usePlayerSearchSuggestions";

// Constants
const BLUR_TIMEOUT_MS = 150; // Delay to allow clicks on suggestions before blur hides them
const MIN_SEARCH_LENGTH = 2; // Still needed for conditional rendering of "No suggestions found."

interface PlayerSearchBarProps {
  initialValue?: string;
  onSearchSubmit: (searchTerm: string) => void;
}

export function PlayerSearchBar({ initialValue = "", onSearchSubmit }: PlayerSearchBarProps) {
  const [searchTerm, setSearchTerm] = useState(initialValue);
  const [isFocused, setIsFocused] = useState(false);

  const {
    suggestions,
    isLoading: isFetchingSuggestions, // Renaming for consistency with old variable names if preferred
    error: suggestionError,
    fetchSuggestions,
    clearSuggestions
  } = usePlayerSearchSuggestions();

  // Effect for triggering suggestion fetching when searchTerm changes
  useEffect(() => {
    const trimmedSearch = searchTerm.trim();
    // Do not fetch if it's the initial value being set, unless initialValue itself is long enough
    if (trimmedSearch === initialValue && initialValue.length < MIN_SEARCH_LENGTH) {
        if (trimmedSearch.length < MIN_SEARCH_LENGTH) {
             clearSuggestions();
             return;
        }
    }
    fetchSuggestions(searchTerm);
  }, [searchTerm, fetchSuggestions, clearSuggestions, initialValue]);

  // Sync with initialValue prop changes
  useEffect(() => {
    setSearchTerm(initialValue);
    // When initialValue changes (e.g. parent page reloads with new search term in URL),
    // clear old suggestions to avoid showing stale ones briefly.
    clearSuggestions(); 
  }, [initialValue, clearSuggestions]);

  const handleSearchTermChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(event.target.value);
  };

  const handleSuggestionClick = (suggestion: Suggestion) => {
    const termToSubmit = suggestion.full_name;
    setSearchTerm(termToSubmit); // Update input field
    clearSuggestions();
    setIsFocused(false);
    onSearchSubmit(termToSubmit);
  };

  const handleFormSubmit = (event?: React.FormEvent<HTMLFormElement>) => {
    if (event) event.preventDefault();
    const trimmedSearch = searchTerm.trim();
    if (trimmedSearch) {
      clearSuggestions();
      setIsFocused(false);
      onSearchSubmit(trimmedSearch);
    }
  };

  return (
    <div className="relative flex-grow w-full md:w-auto">
      <form onSubmit={handleFormSubmit} className="w-full">
        <div className="flex items-center w-full">
          <Input
            id="player-search"
            type="search"
            placeholder="Search players (e.g., LeBron James)..."
            value={searchTerm}
            onChange={handleSearchTermChange}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setTimeout(() => setIsFocused(false), BLUR_TIMEOUT_MS)}
            className="pr-10 w-full"
            aria-label="Search players"
            autoComplete="off"
          />
          <Button type="submit" size="icon" variant="ghost" className="absolute right-1 h-9 w-9" aria-label="Search">
            <Search className="h-4 w-4 text-muted-foreground" />
          </Button>
        </div>
      </form>
      {isFocused && (isFetchingSuggestions || suggestions.length > 0 || suggestionError) && (
        <Card className="absolute z-20 mt-1 w-full border bg-popover text-popover-foreground shadow-md max-h-60 overflow-y-auto">
          <CardContent className="p-2">
            {isFetchingSuggestions && <p className="text-sm text-muted-foreground px-2 py-1">Loading...</p>}
            {suggestionError && <p className="text-sm text-destructive px-2 py-1">Error: {suggestionError}</p>}
            {!isFetchingSuggestions && suggestions.length === 0 && !suggestionError && searchTerm.trim().length >= MIN_SEARCH_LENGTH && (
              <p className="text-sm text-muted-foreground px-2 py-1">No suggestions found.</p>
            )}
            {suggestions.length > 0 && (
              <ul className="divide-y divide-border">
                {suggestions.map((suggestion) => (
                  <li key={suggestion.id}>
                    <Button
                      variant="ghost"
                      className="w-full justify-start h-auto px-3 py-2 text-sm font-normal hover:bg-accent"
                      onMouseDown={() => handleSuggestionClick(suggestion)} // Use onMouseDown for click before blur
                    >
                      <span className={cn({ 'text-muted-foreground': !suggestion.is_active })}>
                        {suggestion.full_name}
                      </span>
                      {!suggestion.is_active && (
                        <Badge variant="outline" className="ml-auto text-xs">Inactive</Badge>
                      )}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}