"use client"; // Need this for state and event handlers

import * as React from "react"; // Import React for state
import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
// Removed unused ScrollArea
import { Input } from "@/components/ui/input"; // Import Input
import { Button } from "@/components/ui/button"; // Import Button
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"; // Import Avatar
import { Skeleton } from "@/components/ui/skeleton"; // Import Skeleton
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"; // Import Alert
import { TerminalIcon, SearchIcon, Loader2Icon } from "lucide-react"; // Import icons, add Loader2Icon
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"; // Import Command components

// Define interfaces for expected data structures (can be refined)
interface PlayerInfo {
  PERSON_ID: number;
  DISPLAY_FIRST_LAST: string;
  TEAM_CITY: string;
  TEAM_ABBREVIATION: string;
  POSITION: string;
  HEIGHT: string;
  WEIGHT: string;
  // Add other relevant fields from commonplayerinfo
}

interface HeadlineStats {
  PLAYER_ID: number;
  PLAYER_NAME: string;
  TimeFrame: string;
  PTS: number;
  AST: number;
  REB: number;
  // Add other relevant fields from playerheadlinestats
}

interface PlayerData {
  player_info: PlayerInfo | null;
  headline_stats: HeadlineStats | null;
}


export default function PlayersPage() {
  // State variables
  const [searchTerm, setSearchTerm] = useState("");
  const [playerData, setPlayerData] = useState<PlayerData | null>(null);
  const [headshotUrl, setHeadshotUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<{ id: number; full_name: string }[]>([]);
  const [isSuggestionLoading, setIsSuggestionLoading] = useState(false);

  const handleSearch = async () => {
    if (!searchTerm.trim()) return;
    setIsLoading(true);
    setError(null);
    setPlayerData(null);
    setHeadshotUrl(null);
    console.log(`Searching for player: ${searchTerm}`);

    try {
      // --- Fetch Player Info ---
      // Use relative path for API calls, Vercel will route correctly
      const infoResponse = await fetch(`/api/fetch_data`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target: "player_info",
          params: { player_name: searchTerm }
        }),
      });

      if (!infoResponse.ok) {
        const errorData = await infoResponse.json().catch(() => ({ detail: `HTTP error ${infoResponse.status}` }));
        throw new Error(errorData.detail || `Failed to fetch player info (${infoResponse.status})`);
      }

      const infoData: PlayerData = await infoResponse.json(); // Assuming backend returns structure matching PlayerData
      console.log("Player Info Data:", infoData);

      if (!infoData || !infoData.player_info || !infoData.player_info.PERSON_ID) {
         throw new Error(`Player '${searchTerm}' not found or data incomplete.`);
      }
      setPlayerData(infoData);
      const playerId = infoData.player_info.PERSON_ID;

      // --- Fetch Headshot URL ---
      const headshotResponse = await fetch(`/api/player/${playerId}/headshot`);
      if (!headshotResponse.ok) {
         // Don't throw error for missing headshot, just log and continue
         console.warn(`Failed to fetch headshot for player ID ${playerId} (${headshotResponse.status})`);
         setHeadshotUrl(null); // Explicitly set to null if fetch fails
      } else {
         const headshotData = await headshotResponse.json();
         console.log("Headshot Data:", headshotData);
         setHeadshotUrl(headshotData.headshot_url);
      }

    } catch (err: unknown) {
      console.error("Search failed:", err);
      // Type check before accessing message property
      const errorMessage = err instanceof Error ? err.message : String(err);
      setError(errorMessage || "An unknown error occurred during search.");
      setPlayerData(null); // Clear data on error
      setHeadshotUrl(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFormSubmit = (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      handleSearch();
  }

  // Debounce timer ref
  const debounceTimer = React.useRef<NodeJS.Timeout | null>(null);

  // Effect to fetch suggestions on searchTerm change (debounced)
  React.useEffect(() => {
    // Clear previous results when search term is short
    if (searchTerm.trim().length < 2) {
      setSuggestions([]);
      return;
    }

    // Clear existing timer
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    // Set loading state for suggestions
    setIsSuggestionLoading(true);

    // Set new timer
    debounceTimer.current = setTimeout(async () => {
      try {
        console.log(`Fetching suggestions for: ${searchTerm}`);
        const response = await fetch(`/api/players/search?q=${encodeURIComponent(searchTerm)}&limit=5`); // Limit suggestions
        if (!response.ok) {
          throw new Error(`Failed to fetch suggestions (${response.status})`);
        }
        const data = await response.json();
        setSuggestions(data || []);
      } catch (error) {
        console.error("Failed to fetch suggestions:", error);
        setSuggestions([]); // Clear suggestions on error
      } finally {
        setIsSuggestionLoading(false);
      }
    }, 300); // 300ms debounce

    // Cleanup function to clear timer on unmount or searchTerm change
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
    };
  }, [searchTerm]); // Dependency array includes searchTerm
  // Removed extra closing brace here

  return (
    <main className="flex flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
      <div className="flex items-center">
        <h1 className="text-lg font-semibold md:text-2xl">Players</h1>
      </div>
      <div className="grid gap-4 md:grid-cols-3"> {/* Adjust grid layout */}
        {/* Search Card */}
        <Card className="md:col-span-1">
          <CardHeader>
            <CardTitle>Player Search</CardTitle>
            <CardDescription>Enter a player&apos;s name to find their info.</CardDescription> {/* Escaped quote */}
          </CardHeader>
          <CardContent>
            {/* Use Command component for input and suggestions */}
            <Command className="rounded-lg border shadow-md">
              <div className="flex items-center border-b px-3"> {/* Wrapper for input and button */}
                <SearchIcon className="mr-2 h-4 w-4 shrink-0 opacity-50" />
                <CommandInput
                  placeholder="e.g., LeBron James"
                  value={searchTerm}
                  onValueChange={setSearchTerm} // Use CommandInput's handler
                  disabled={isLoading}
                  className="flex-1 border-0 shadow-none focus-visible:ring-0 pl-0 h-10" // Adjust styling
                />
                 <Button
                    type="button" // Change type to button as Command handles selection/submission
                    onClick={handleSearch} // Trigger search directly
                    disabled={isLoading || !searchTerm.trim()}
                    size="sm"
                    className="ml-2"
                  >
                    {isLoading ? <Loader2Icon className="h-4 w-4 animate-spin" /> : "Search"}
                  </Button>
              </div>
              <CommandList>
                {isSuggestionLoading && <CommandItem>Loading suggestions...</CommandItem>}
                {!isSuggestionLoading && suggestions.length === 0 && searchTerm.trim().length >= 2 && (
                  <CommandEmpty>No players found.</CommandEmpty>
                )}
                {!isSuggestionLoading && suggestions.length > 0 && (
                  <CommandGroup heading="Suggestions">
                    {suggestions.map((player) => (
                      <CommandItem
                        key={player.id}
                        value={player.full_name} // Value used for filtering/selection
                        onSelect={(currentValue) => {
                          setSearchTerm(currentValue); // Set search term on selection
                          setSuggestions([]); // Clear suggestions
                          handleSearch(); // Trigger search immediately on selection
                        }}
                      >
                        {player.full_name}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}
              </CommandList>
            </Command>
          </CardContent>
        </Card>

        {/* Results Area */}
        <div className="md:col-span-2"> {/* Make results area wider */}
          {/* Loading State */}
          {isLoading && (
            <Card>
              <CardHeader>
                <Skeleton className="h-6 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
              </CardHeader>
              <CardContent className="flex items-center space-x-4">
                 <Skeleton className="h-20 w-20 rounded-full" />
                 <div className="space-y-2">
                   <Skeleton className="h-4 w-[200px]" />
                   <Skeleton className="h-4 w-[150px]" />
                   <Skeleton className="h-4 w-[180px]" />
                 </div>
              </CardContent>
            </Card>
          )}

          {/* Error State */}
          {!isLoading && error && (
            <Alert variant="destructive">
              <TerminalIcon className="h-4 w-4" />
              <AlertTitle>Search Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Player Info Display */}
          {!isLoading && !error && playerData && playerData.player_info && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                   <Avatar className="h-8 w-8">
                     <AvatarImage src={headshotUrl ?? undefined} alt={playerData.player_info.DISPLAY_FIRST_LAST} />
                     <AvatarFallback>{playerData.player_info.DISPLAY_FIRST_LAST.split(' ').map(n => n[0]).join('')}</AvatarFallback>
                   </Avatar>
                   {playerData.player_info.DISPLAY_FIRST_LAST}
                </CardTitle>
                <CardDescription>
                    {playerData.player_info.TEAM_CITY} {playerData.player_info.TEAM_ABBREVIATION} | {playerData.player_info.POSITION} | {playerData.player_info.HEIGHT} | {playerData.player_info.WEIGHT} lbs
                </CardDescription>
              </CardHeader>
              <CardContent>
                <h4 className="mb-2 font-semibold">Headline Stats ({playerData.headline_stats?.TimeFrame || 'N/A'})</h4>
                <div className="grid grid-cols-3 gap-2 text-sm">
                   <div><span className="font-medium">PTS:</span> {playerData.headline_stats?.PTS ?? 'N/A'}</div>
                   <div><span className="font-medium">AST:</span> {playerData.headline_stats?.AST ?? 'N/A'}</div>
                   <div><span className="font-medium">REB:</span> {playerData.headline_stats?.REB ?? 'N/A'}</div>
                   {/* Add more headline stats as needed */}
                </div>
                 {/* Add more detailed info sections later (e.g., game logs, career stats tables) */}
              </CardContent>
            </Card>
          )}

           {/* Initial Placeholder */}
           {!isLoading && !error && !playerData && (
             <div className="flex h-40 items-center justify-center rounded-lg border border-dashed shadow-sm">
               <p className="text-muted-foreground">Search for a player to see their details.</p>
             </div>
           )}
        </div>
      </div>
    </main>
  );
}