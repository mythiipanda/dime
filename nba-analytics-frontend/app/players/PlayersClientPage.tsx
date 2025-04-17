"use client";

import * as React from "react";
import { useState, useEffect, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PlayerData, Suggestion } from "./types"; // Import types from the new types file
import { PlayerProfileCard } from "@/components/players/PlayerProfileCard"; // Import component from its new file
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/config";
import { Search } from "lucide-react"; // Only need Search from lucide
import { ExclamationTriangleIcon } from '@radix-ui/react-icons'; // Correct import for this icon

interface PlayersClientPageProps {
  initialSearchTerm: string | null;
  initialPlayerData: PlayerData | null;
  initialHeadshotUrl: string | null;
  serverFetchError: string | null; // Error from initial server fetch
}

export default function PlayersClientPage({
  initialSearchTerm,
  initialPlayerData,
  initialHeadshotUrl,
  serverFetchError,
}: PlayersClientPageProps) {
  const router = useRouter();
  const currentSearchParams = useSearchParams();

  const [searchTerm, setSearchTerm] = useState(initialSearchTerm || "");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [isFetchingSuggestions, setIsFetchingSuggestions] = useState(false);
  const [suggestionError, setSuggestionError] = useState<string | null>(null);

  const playerData = initialPlayerData;
  const headshotUrl = initialHeadshotUrl;
  const fetchError = serverFetchError;
  const noPlayerFoundError = fetchError?.toLowerCase().includes("not found") ? fetchError : null;
  const generalFetchError = fetchError && !noPlayerFoundError ? fetchError : null;

  const debounceTimer = React.useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const trimmedSearch = searchTerm.trim();
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    if (trimmedSearch.length < 2) {
      setSuggestions([]);
      setSuggestionError(null);
      setIsFetchingSuggestions(false);
      return;
    }
    if (initialSearchTerm === trimmedSearch && initialPlayerData) {
        setSuggestions([]);
        return;
    }

    setIsFetchingSuggestions(true);
    setSuggestionError(null);

    debounceTimer.current = setTimeout(async () => {
      console.log(`Debounced suggestion search for: ${trimmedSearch}`);
      try {
        const suggestionsUrl = `${API_BASE_URL}/players/search?q=${encodeURIComponent(trimmedSearch)}&limit=7`;
        const response = await fetch(suggestionsUrl);
        if (!response.ok) {
          throw new Error(`Failed to fetch suggestions (${response.status})`);
        }
        const data: Suggestion[] = await response.json();
        setSuggestions(data);
      } catch (err) {
        console.error("Failed to fetch suggestions:", err);
        setSuggestionError(err instanceof Error ? err.message : "Could not fetch suggestions.");
        setSuggestions([]);
      } finally {
        setIsFetchingSuggestions(false);
      }
    }, 300);

    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, [searchTerm, initialSearchTerm, initialPlayerData]); // Added initialPlayerData dependency

  const handleSearchTermChange = (event: React.ChangeEvent<HTMLInputElement>) => {
      setSearchTerm(event.target.value);
  };

  const handleSuggestionClick = (suggestion: Suggestion) => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    setSearchTerm(suggestion.full_name);
    setSuggestions([]);
    setIsFetchingSuggestions(false);
    const params = new URLSearchParams(currentSearchParams.toString());
    params.set("query", suggestion.full_name);
    router.push(`/players?${params.toString()}`);
  };

  const handleSearchSubmit = (event?: React.FormEvent<HTMLFormElement>) => {
    if (event) event.preventDefault();
    const trimmedSearch = searchTerm.trim();
    if (trimmedSearch) {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
      setSuggestions([]);
      setIsFetchingSuggestions(false);
      const params = new URLSearchParams(currentSearchParams.toString());
      params.set("query", trimmedSearch);
      router.push(`/players?${params.toString()}`);
    }
  };

  return (
    <div className="container mx-auto p-4 space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">NBA Player Analytics</h1>

      <div className="flex flex-col md:flex-row gap-4 items-start">
        <div className="relative flex-grow w-full md:w-auto">
          <form onSubmit={handleSearchSubmit} className="w-full">
            <div className="flex items-center w-full">
              <Input
                id="player-search"
                type="search"
                placeholder="Search players (e.g., LeBron James)..."
                value={searchTerm}
                onChange={handleSearchTermChange}
                className="pr-10 w-full"
                aria-label="Search players"
                autoComplete="off"
              />
              <Button type="submit" size="icon" variant="ghost" className="absolute right-1 h-9 w-9" aria-label="Search">
                <Search className="h-4 w-4 text-muted-foreground" />
              </Button>
            </div>
          </form>
          {(isFetchingSuggestions || suggestions.length > 0 || suggestionError) && (
             <Card className="absolute z-20 mt-1 w-full border bg-popover text-popover-foreground shadow-md max-h-60 overflow-y-auto">
               <CardContent className="p-2">
                 {isFetchingSuggestions && <p className="text-sm text-muted-foreground px-2 py-1">Loading...</p>}
                 {suggestionError && <p className="text-sm text-destructive px-2 py-1">Error: {suggestionError}</p>}
                 {!isFetchingSuggestions && suggestions.length === 0 && !suggestionError && searchTerm.length >= 2 && (
                    <p className="text-sm text-muted-foreground px-2 py-1">No suggestions found.</p>
                 )}
                 {suggestions.length > 0 && (
                   <ul className="divide-y divide-border">
                     {suggestions.map((suggestion) => (
                       <li key={suggestion.id}>
                         <Button
                           variant="ghost"
                           className="w-full justify-start h-auto px-3 py-2 text-sm font-normal hover:bg-accent"
                           onClick={() => handleSuggestionClick(suggestion)}
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
      </div>

      {generalFetchError && (
        <Alert variant="destructive" className="mt-4 max-w-4xl mx-auto">
          <ExclamationTriangleIcon className="h-4 w-4" />
          <AlertTitle>Error Loading Player</AlertTitle>
          <AlertDescription>{generalFetchError}</AlertDescription>
        </Alert>
      )}
      {noPlayerFoundError && (
        <Alert variant="default" className="mt-4 max-w-4xl mx-auto">
          <Search className="h-4 w-4" />
          <AlertTitle>Player Not Found</AlertTitle>
          <AlertDescription>{noPlayerFoundError}</AlertDescription>
        </Alert>
      )}

      {playerData && !fetchError && (
        <PlayerProfileCard playerData={playerData} headshotUrl={headshotUrl} />
      )}

      {!playerData && !fetchError && (
        <div className="text-center py-10 text-muted-foreground">
          <Search className="mx-auto h-12 w-12 mb-4" />
          <p>Search for an NBA player to view their detailed profile and statistics.</p>
        </div>
      )}
    </div>
  );
}

// TODO:
// 1. Move PlayerProfileCard, StatBox, formatStat, PlayerData, Suggestion etc. to separate files (e.g., components/players/, types/players.ts)
// 2. Potentially refine loading state indication if needed beyond loading.tsx
