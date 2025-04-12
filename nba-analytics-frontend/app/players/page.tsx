"use client"; // Need this for state and event handlers

import * as React from "react"; // Import React for state
import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button"; // Import Button
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"; // Import Avatar
import { Skeleton } from "@/components/ui/skeleton"; // Import Skeleton
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"; // Import Alert
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Search,
  Filter,
  Loader2,
  AlertCircle,
  ChevronRight,
  TrendingUp,
  BarChart2,
  Trophy,
} from "lucide-react"; // Import icons, add Loader2Icon and FilterIcon
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"; // Import Command components
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

// Define interfaces for expected data structures (can be refined)
interface PlayerInfo {
  PERSON_ID: number;
  DISPLAY_FIRST_LAST: string;
  TEAM_CITY: string;
  TEAM_ABBREVIATION: string;
  POSITION: string;
  HEIGHT: string;
  WEIGHT: string;
  JERSEY: string;
  // Add other relevant fields from commonplayerinfo
}

interface HeadlineStats {
  PLAYER_ID: number;
  PLAYER_NAME: string;
  TimeFrame: string;
  PTS: number;
  AST: number;
  REB: number;
  FG_PCT: number;
  FG3_PCT: number;
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
  const [selectedFilters, setSelectedFilters] = useState<string[]>([]);

  const filterOptions = [
    { label: "Position", options: ["Guard", "Forward", "Center"] },
    { label: "Conference", options: ["Eastern", "Western"] },
    { label: "Division", options: ["Atlantic", "Central", "Southeast", "Northwest", "Pacific", "Southwest"] },
    { label: "Experience", options: ["Rookie", "1-3 Years", "4-7 Years", "8+ Years"] },
  ];

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
      // Always use relative /api path.
      const infoUrl = `/api/fetch_data`;
      console.log(`Fetching player info from: ${infoUrl}`);
      const infoResponse = await fetch(infoUrl, {
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
      // Always use relative /api path.
      const headshotUrlPath = `/api/player/${playerId}/headshot`;
      console.log(`Fetching headshot from: ${headshotUrlPath}`);
      const headshotResponse = await fetch(headshotUrlPath);
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
        // Always use relative /api path. Next.js rewrite handles local dev.
        const suggestionsUrl = `/api/players/search?q=${encodeURIComponent(searchTerm)}&limit=5`;
        console.log(`Fetching suggestions from: ${suggestionsUrl}`);
        const response = await fetch(suggestionsUrl);
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
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Players</h1>
          <p className="text-muted-foreground">
            Search and analyze NBA player statistics and performance metrics
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Button variant="outline">
            <TrendingUp className="mr-2 h-4 w-4" />
            Compare Players
          </Button>
          <Button>
            <BarChart2 className="mr-2 h-4 w-4" />
            View Stats
          </Button>
        </div>
      </div>
      
      <div className="flex flex-col gap-4 md:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input 
            placeholder="Search players by name..." 
            className="pl-8" 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="w-full md:w-auto">
              <Filter className="mr-2 h-4 w-4" />
              Filters
              {selectedFilters.length > 0 && (
                <span className="ml-2 rounded-full bg-primary px-2 py-0.5 text-xs text-primary-foreground">
                  {selectedFilters.length}
                </span>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            {filterOptions.map((filterGroup) => (
              <React.Fragment key={filterGroup.label}>
                <DropdownMenuLabel>{filterGroup.label}</DropdownMenuLabel>
                {filterGroup.options.map((option) => (
                  <DropdownMenuItem key={option}>
                    {option}
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator />
              </React.Fragment>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {suggestions.length > 0 && (
        <Card>
          <ScrollArea className="h-72">
            <CardContent className="p-0">
              <Command>
                <CommandList>
                  <CommandGroup>
                    {suggestions.map((player) => (
                      <CommandItem
                        key={player.id}
                        onSelect={() => {
                          setSearchTerm(player.full_name);
                          handleSearch();
                        }}
                      >
                        <Avatar className="mr-2 h-8 w-8">
                          <AvatarFallback>{player.full_name[0]}</AvatarFallback>
                        </Avatar>
                        <div className="flex-1">
                          <p className="text-sm font-medium">{player.full_name}</p>
                        </div>
                        <ChevronRight className="ml-2 h-4 w-4 text-muted-foreground" />
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </CardContent>
          </ScrollArea>
        </Card>
      )}

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-24 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : playerData ? (
        <Card>
          <CardHeader className="flex flex-row items-center gap-4">
            <Avatar className="h-20 w-20">
              {headshotUrl ? (
                <AvatarImage src={headshotUrl} alt={playerData.player_info?.DISPLAY_FIRST_LAST} />
              ) : (
                <AvatarFallback>{playerData.player_info?.DISPLAY_FIRST_LAST?.split(' ').map(n => n[0]).join('')}</AvatarFallback>
              )}
            </Avatar>
            <div>
              <CardTitle className="text-2xl">{playerData.player_info?.DISPLAY_FIRST_LAST}</CardTitle>
              <CardDescription>
                {playerData.player_info?.TEAM_CITY} {playerData.player_info?.TEAM_ABBREVIATION} •{" "}
                #{playerData.player_info?.JERSEY} • {playerData.player_info?.POSITION}
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <p className="text-sm font-medium text-muted-foreground">Physical</p>
              <div className="flex justify-between">
                <span>Height</span>
                <span className="font-medium">{playerData.player_info?.HEIGHT}</span>
              </div>
              <div className="flex justify-between">
                <span>Weight</span>
                <span className="font-medium">{playerData.player_info?.WEIGHT} lbs</span>
              </div>
            </div>
            {playerData.headline_stats && (
              <>
                <div className="space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">Season Averages</p>
                  <div className="flex justify-between">
                    <span>Points</span>
                    <span className="font-medium">{playerData.headline_stats.PTS}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Assists</span>
                    <span className="font-medium">{playerData.headline_stats.AST}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Rebounds</span>
                    <span className="font-medium">{playerData.headline_stats.REB}</span>
                  </div>
                </div>
                <div className="space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">Shooting</p>
                  <div className="flex justify-between">
                    <span>FG%</span>
                    <span className="font-medium">
                      {(playerData.headline_stats.FG_PCT * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>3P%</span>
                    <span className="font-medium">
                      {(playerData.headline_stats.FG3_PCT * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>
              </>
            )}
          </CardContent>
          <CardFooter className="justify-end space-x-2">
            <Button variant="outline">View Stats</Button>
            <Button>
              <Trophy className="mr-2 h-4 w-4" />
              Compare
            </Button>
          </CardFooter>
        </Card>
      ) : null}
    </div>
  );
}