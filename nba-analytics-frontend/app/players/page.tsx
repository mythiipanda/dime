"use client";

import * as React from "react";
import { useState, useEffect, useCallback, useMemo } from "react";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Search, Filter, AlertCircle, ChevronRight, TrendingUp, BarChart2, Trophy, UserRoundX, Info,
} from "lucide-react";
import {
  Command, CommandGroup, CommandItem, CommandList,
} from "@/components/ui/command";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { API_BASE_URL } from "@/lib/config";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ExclamationTriangleIcon } from '@radix-ui/react-icons';

// --- Expanded Interfaces based on PlayerProfileV2 structure ---
interface PlayerInfo {
  PERSON_ID: number;
  DISPLAY_FIRST_LAST: string;
  TEAM_ABBREVIATION?: string;
  TEAM_CITY?: string;
  POSITION?: string;
  HEIGHT?: string;
  WEIGHT?: string;
  JERSEY?: string;
  FROM_YEAR?: number;
  TO_YEAR?: number;
  PLAYER_SLUG?: string;
  COUNTRY?: string;
  SCHOOL?: string;
  BIRTHDATE?: string;
  SEASON_EXP?: number;
}

interface CareerOrSeasonStat {
  PLAYER_ID: number;
  SEASON_ID?: string; // Only for season stats
  LEAGUE_ID?: string; // Optional
  TEAM_ID?: number; // Optional
  TEAM_ABBREVIATION?: string;
  PLAYER_AGE?: number;
  GP?: number;
  GS?: number;
  MIN?: number;
  FGM?: number;
  FGA?: number;
  FG_PCT?: number;
  FG3M?: number;
  FG3A?: number;
  FG3_PCT?: number;
  FTM?: number;
  FTA?: number;
  FT_PCT?: number;
  OREB?: number;
  DREB?: number;
  REB?: number;
  AST?: number;
  STL?: number;
  BLK?: number;
  TOV?: number;
  PF?: number;
  PTS?: number;
}

interface CareerHighs {
    PLAYER_ID?: number;
    PLAYER_NAME?: string;
    TimeFrame?: string;
    PTS_HIGH?: number;
    REB_HIGH?: number;
    AST_HIGH?: number;
    STL_HIGH?: number;
    BLK_HIGH?: number;
}

// Interface for the nested season_totals object
interface SeasonTotals {
    regular_season: CareerOrSeasonStat[] | null;
    post_season: CareerOrSeasonStat[] | null;
    all_star?: CareerOrSeasonStat[] | null; // Optional based on API response
    preseason?: CareerOrSeasonStat[] | null; // Optional based on API response
    college?: CareerOrSeasonStat[] | null;   // Optional based on API response
}

// Interface for the nested career_totals object
interface CareerTotals {
    regular_season: CareerOrSeasonStat | null;
    post_season: CareerOrSeasonStat | null;
    all_star?: CareerOrSeasonStat | null; // Optional based on API response
    preseason?: CareerOrSeasonStat | null; // Optional based on API response
    college?: CareerOrSeasonStat | null;   // Optional based on API response
}

interface PlayerData {
  player_info: PlayerInfo | null; 
  career_totals: CareerTotals | null; // Use the nested CareerTotals interface
  season_totals: SeasonTotals | null; // Use the nested SeasonTotals interface
  career_highs: CareerHighs | null; 
  // Add other datasets like season_highs, next_game if needed by the component
  season_highs?: CareerHighs | null; // Make optional or define fully if used
  next_game?: any | null; // Use specific type if next_game structure is stable and used
}

interface Suggestion {
    id: number;
    full_name: string;
    is_active: boolean;
}

// --- Helper Function to format numbers ---
const formatStat = (value: number | null | undefined, decimals: number = 1): string => {
  if (value === null || value === undefined || isNaN(value)) return '-';
  return value.toFixed(decimals);
};

// --- Player Profile Card Component ---
interface PlayerProfileCardProps {
  playerData: PlayerData;
  headshotUrl: string | null;
}

function PlayerProfileCard({ playerData, headshotUrl }: PlayerProfileCardProps) {
  const info = playerData.player_info;
  // Access nested properties safely
  const careerRegular = playerData.career_totals?.regular_season;
  const seasonRegular = playerData.season_totals?.regular_season;
  const careerPost = playerData.career_totals?.post_season;
  const seasonPost = playerData.season_totals?.post_season;
  const careerHighs = playerData.career_highs;

  // Log the raw season data received by the component
  console.log("PlayerProfileCard received seasonRegular:", seasonRegular);
  console.log("PlayerProfileCard received seasonPost:", seasonPost);

  if (!info) {
      console.error("PlayerProfileCard rendering without player_info.");
      return <Alert variant="destructive">
                  <ExclamationTriangleIcon className="h-4 w-4" />
                  <AlertTitle>Error</AlertTitle>
                  <AlertDescription>Could not load player information.</AlertDescription>
              </Alert>;
  }

  // Sort seasons descending for display
  const sortedRegularSeasons = useMemo(() => {
      const sorted = seasonRegular?.slice().sort((a, b) => (b.SEASON_ID ?? '').localeCompare(a.SEASON_ID ?? '')) || [];
      // Log the result of sorting
      console.log("PlayerProfileCard sortedRegularSeasons:", sorted);
      return sorted;
    },
      [seasonRegular]
  );
  const sortedPostSeasons = useMemo(() => {
      const sorted = seasonPost?.slice().sort((a, b) => (b.SEASON_ID ?? '').localeCompare(a.SEASON_ID ?? '')) || [];
      // Log the result of sorting
      console.log("PlayerProfileCard sortedPostSeasons:", sorted);
      return sorted;
    },
      [seasonPost]
  );

  const renderSeasonTable = (seasons: CareerOrSeasonStat[], title: string) => {
    // Log when the function is called and the data it receives
    console.log(`renderSeasonTable called for ${title} with ${seasons?.length ?? 0} seasons.`);

    if (!seasons || seasons.length === 0) {
        console.log(`renderSeasonTable (${title}): Condition matched, rendering 'No data'.`);
        return <p className="text-muted-foreground text-center py-4">No {title.toLowerCase()} data available.</p>;
    }
    console.log(`renderSeasonTable (${title}): Rendering table.`);
    return (
        <div>
            <h3 className="text-lg font-semibold mb-2">{title} by Season</h3>
             <ScrollArea className="h-[300px] w-full rounded-md border">
               <Table className="relative">
                 <TableHeader className="sticky top-0 bg-background z-10">
                   <TableRow>
                     <TableHead>Season</TableHead>
                     <TableHead>Team</TableHead>
                     <TableHead className="text-right">GP</TableHead>
                     <TableHead className="text-right">GS</TableHead>
                     <TableHead className="text-right">MIN</TableHead>
                     <TableHead className="text-right">PTS</TableHead>
                     <TableHead className="text-right">REB</TableHead>
                     <TableHead className="text-right">AST</TableHead>
                     <TableHead className="text-right">STL</TableHead>
                     <TableHead className="text-right">BLK</TableHead>
                     <TableHead className="text-right">FG%</TableHead>
                     <TableHead className="text-right">3P%</TableHead>
                     <TableHead className="text-right">FT%</TableHead>
                   </TableRow>
                 </TableHeader>
                 <TableBody>
                   {seasons.map((season) => (
                     <TableRow key={`${title}-${season.SEASON_ID}-${season.TEAM_ABBREVIATION}`}>
                       <TableCell>{season.SEASON_ID}</TableCell>
                       <TableCell>{season.TEAM_ABBREVIATION || 'N/A'}</TableCell>
                       <TableCell className="text-right">{formatStat(season.GP, 0)}</TableCell>
                       <TableCell className="text-right">{formatStat(season.GS, 0)}</TableCell>
                       <TableCell className="text-right">{formatStat(season.MIN)}</TableCell>
                       <TableCell className="text-right">{formatStat(season.PTS)}</TableCell>
                       <TableCell className="text-right">{formatStat(season.REB)}</TableCell>
                       <TableCell className="text-right">{formatStat(season.AST)}</TableCell>
                       <TableCell className="text-right">{formatStat(season.STL)}</TableCell>
                       <TableCell className="text-right">{formatStat(season.BLK)}</TableCell>
                       <TableCell className="text-right">{formatStat((season.FG_PCT ?? 0) * 100)}%</TableCell>
                       <TableCell className="text-right">{formatStat((season.FG3_PCT ?? 0) * 100)}%</TableCell>
                       <TableCell className="text-right">{formatStat((season.FT_PCT ?? 0) * 100)}%</TableCell>
                     </TableRow>
                   ))}
                 </TableBody>
               </Table>
             </ScrollArea>
           </div>
    );
  };

  return (
    <Card className="mt-4 w-full max-w-4xl mx-auto">
      <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center gap-4 border-b pb-4">
        <Avatar className="h-24 w-24 sm:h-32 sm:w-32 border-2 shadow-sm">
          {headshotUrl ? (
            <AvatarImage src={headshotUrl} alt={info.DISPLAY_FIRST_LAST} className="object-cover"/>
          ) : (
            <AvatarFallback className="text-4xl">
                {info.DISPLAY_FIRST_LAST?.split(' ').map(n => n[0]).join('')}
            </AvatarFallback>
          )}
        </Avatar>
        <div className="flex-1 space-y-1">
          <CardTitle className="text-3xl sm:text-4xl font-bold">{info.DISPLAY_FIRST_LAST}</CardTitle>
           <div className="flex flex-wrap items-center gap-2 text-muted-foreground text-sm sm:text-base">
               {info.POSITION && <Badge variant="secondary">{info.POSITION}</Badge>}
               {info.HEIGHT && <span>{info.HEIGHT}</span>}
               {info.WEIGHT && <span>{info.WEIGHT} lbs</span>}
               {info.JERSEY && <Badge variant="outline">#{info.JERSEY}</Badge>}
               {info.TEAM_ABBREVIATION && <span>{info.TEAM_CITY} {info.TEAM_ABBREVIATION}</span>}
            </div>
             <div className="text-xs sm:text-sm text-muted-foreground space-y-0.5">
               {info.SEASON_EXP !== undefined && <p>Experience: {info.SEASON_EXP} years</p>}
               {info.BIRTHDATE && <p>Born: {new Date(info.BIRTHDATE).toLocaleDateString()} {info.COUNTRY && `(${info.COUNTRY})`}</p>}
               {info.SCHOOL && <p>College: {info.SCHOOL}</p>}
               {(info.FROM_YEAR !== undefined && info.TO_YEAR !== undefined) && <p>Career: {info.FROM_YEAR} - {info.TO_YEAR}</p>}
             </div>
        </div>
      </CardHeader>

      <CardContent className="pt-6 space-y-6">
         <Tabs defaultValue="regular" className="w-full">
            <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="regular">Regular Season</TabsTrigger>
                <TabsTrigger value="postseason">Postseason</TabsTrigger>
            </TabsList>

            {/* Regular Season Content */}
            <TabsContent value="regular" className="space-y-4 pt-4">
                {/* Career Regular Season Averages */}
                {careerRegular && (
                   <div>
                        <h3 className="text-lg font-semibold mb-2">Career Averages</h3>
                        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3 text-center">
                            <StatBox label="GP" value={careerRegular.GP} decimals={0} />
                            <StatBox label="PTS" value={careerRegular.PTS} />
                            <StatBox label="REB" value={careerRegular.REB} />
                            <StatBox label="AST" value={careerRegular.AST} />
                            <StatBox label="FG%" value={(careerRegular.FG_PCT ?? 0) * 100} suffix="%" />
                            <StatBox label="3P%" value={(careerRegular.FG3_PCT ?? 0) * 100} suffix="%" />
                            <StatBox label="FT%" value={(careerRegular.FT_PCT ?? 0) * 100} suffix="%" />
                            <StatBox label="STL" value={careerRegular.STL} />
                            <StatBox label="BLK" value={careerRegular.BLK} />
                            <StatBox label="MIN" value={careerRegular.MIN} />
                        </div>
                   </div>
                )}
                {/* Per-Season Regular Stats Table */}
                {renderSeasonTable(sortedRegularSeasons, "Regular Season Stats")}
            </TabsContent>

            {/* Postseason Content */}
            <TabsContent value="postseason" className="space-y-4 pt-4">
                {/* Career Postseason Averages */}
                {careerPost && (
                   <div>
                        <h3 className="text-lg font-semibold mb-2">Career Averages</h3>
                        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3 text-center">
                            <StatBox label="GP" value={careerPost.GP} decimals={0} />
                            <StatBox label="PTS" value={careerPost.PTS} />
                            <StatBox label="REB" value={careerPost.REB} />
                            <StatBox label="AST" value={careerPost.AST} />
                            <StatBox label="FG%" value={(careerPost.FG_PCT ?? 0) * 100} suffix="%" />
                            <StatBox label="3P%" value={(careerPost.FG3_PCT ?? 0) * 100} suffix="%" />
                            <StatBox label="FT%" value={(careerPost.FT_PCT ?? 0) * 100} suffix="%" />
                            <StatBox label="STL" value={careerPost.STL} />
                            <StatBox label="BLK" value={careerPost.BLK} />
                            <StatBox label="MIN" value={careerPost.MIN} />
                        </div>
                   </div>
                 )}
                {/* Per-Season Postseason Stats Table */}
                 {renderSeasonTable(sortedPostSeasons, "Postseason Stats")}
            </TabsContent>
         </Tabs>

      </CardContent>
       {/* Footer can be added back if needed */}
       {/* <CardFooter className="justify-end space-x-2">
         <Button variant=\"outline\">Full Stats</Button>
         <Button>Compare</Button>
       </CardFooter> */}
    </Card>
  );
}

// --- Small Stat Box Component ---
interface StatBoxProps {
    label: string;
    value: number | null | undefined;
    decimals?: number;
    suffix?: string;
}

function StatBox({ label, value, decimals = 1, suffix = '' }: StatBoxProps) {
    const formattedValue = formatStat(value, decimals);
    return (
        <div className="p-2 rounded border bg-muted/50">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">{label}</p>
            <p className="text-xl font-semibold">{formattedValue}{formattedValue !== '-' ? suffix : ''}</p>
        </div>
    )
}


// --- Main Page Component ---
export default function PlayersPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [playerData, setPlayerData] = useState<PlayerData | null>(null);
  const [headshotUrl, setHeadshotUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [noPlayerFoundError, setNoPlayerFoundError] = useState<string | null>(null);

  const filterOptions = [
    { label: "Position", options: ["Guard", "Forward", "Center"] },
    { label: "Conference", options: ["Eastern", "Western"] },
    { label: "Division", options: ["Atlantic", "Central", "Southeast", "Northwest", "Pacific", "Southwest"] },
  ];

  const fetchPlayerDetails = useCallback(async (playerName: string | null) => {
    if (!playerName || !playerName.trim()) {
        setSearchTerm("");
        setPlayerData(null);
        setHeadshotUrl(null);
        setError(null);
        setNoPlayerFoundError(null);
        setSuggestions([]);
        return;
    }

    setIsLoading(true);
    setError(null);
    setNoPlayerFoundError(null);
    setPlayerData(null); // Clear previous data
    setHeadshotUrl(null);
    setSuggestions([]); // Clear suggestions after selection
    console.log(`Fetching details for player: ${playerName}`);

    try {
      // --- Fetch Player Profile (Uses /profile endpoint) ---
      const profileUrl = `${API_BASE_URL}/players/profile?player_name=${encodeURIComponent(playerName)}`;
      console.log(`Fetching player profile from: ${profileUrl}`);
      const profileResponse = await fetch(profileUrl);

      if (!profileResponse.ok) {
        const errorData = await profileResponse.json().catch(() => ({ detail: `HTTP error ${profileResponse.status}` }));
        console.error(`Profile fetch failed (${profileResponse.status}):`, errorData);
        if (profileResponse.status === 404) {
            setNoPlayerFoundError(errorData.detail || `Player '${playerName}' not found.`);
            setError(null);
        } else {
            setError(errorData.detail || `Failed to fetch player profile (${profileResponse.status})`);
            setNoPlayerFoundError(null);
        }
        // Don't throw here, let finally block handle loading state
        return;
      }

      const rawData = await profileResponse.json();
      console.log("Player Profile Data Received:", rawData);

      // --- Basic Validation ---
      if (!rawData || !rawData.player_info) {
          console.error("Validation Failed - Missing essential player_info in response.");
          setError(`Incomplete profile data received for player '${playerName}'. Player info missing.`);
          setPlayerData(null); // Ensure data is null on error
          return;
      }

      const mappedPlayerData: PlayerData = {
          player_info: rawData.player_info,
          career_totals: {
              regular_season: rawData.career_totals?.regular_season ?? null,
              post_season: rawData.career_totals?.post_season ?? null,
          },
          season_totals: {
              regular_season: rawData.season_totals?.regular_season ?? null,
              post_season: rawData.season_totals?.post_season ?? null,
          },
          career_highs: rawData.career_highs ?? null,
      };
      setPlayerData(mappedPlayerData);
      const playerId = mappedPlayerData.player_info.PERSON_ID;
      console.log(`Successfully fetched profile data for ID: ${playerId}`);

      // --- Fetch Headshot URL ---
      const headshotUrlPath = `${API_BASE_URL}/players/player/${playerId}/headshot`;
      console.log(`Fetching headshot from: ${headshotUrlPath}`);
      try {
          const headshotResponse = await fetch(headshotUrlPath);
          if (!headshotResponse.ok) {
            console.warn(`Failed to fetch headshot for player ID ${playerId} (${headshotResponse.status})`);
            setHeadshotUrl(null); // Explicitly set to null on failure
          } else {
            const headshotData = await headshotResponse.json();
            console.log("Headshot Data:", headshotData);
            setHeadshotUrl(headshotData?.headshot_url || null);
          }
      } catch (headshotErr) {
          console.warn("Error fetching headshot:", headshotErr);
          setHeadshotUrl(null); // Ensure null on fetch error
      }


    } catch (err: unknown) {
      // Catch unexpected errors during profile fetch/processing
       if (!noPlayerFoundError) { // Avoid double logging 404s
           console.error("Failed to fetch player details (outer catch):", err);
           const errorMessage = err instanceof Error ? err.message : String(err);
           setError(errorMessage || "An unknown error occurred while fetching player details.");
       }
      setPlayerData(null);
      setHeadshotUrl(null);
    } finally {
      setIsLoading(false);
      console.log("Fetching finished. Loading state:", isLoading);
    }
  }, []); // Add empty dependency array for useCallback


  // --- Debounced Suggestions Fetch ---
  const debounceTimer = React.useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const trimmedSearch = searchTerm.trim();

    // Clear previous timer if search term becomes too short or changes
    if (debounceTimer.current) clearTimeout(debounceTimer.current);

    if (trimmedSearch.length < 2) {
      setSuggestions([]);
      return; // Exit if search term is too short
    }

    // Don't fetch suggestions if player details are already loaded or actively loading
    // This prevents re-fetching suggestions after a player is selected
    if (playerData || isLoading) {
        setSuggestions([]); // Clear suggestions when details are shown/loading
        return;
    }

    debounceTimer.current = setTimeout(async () => {
      console.log(`Debounced search for: ${trimmedSearch}`);
      // No setIsLoading here - fetchPlayerDetails handles main loading
      try {
        const suggestionsUrl = `${API_BASE_URL}/players/search?q=${encodeURIComponent(trimmedSearch)}&limit=7`;
        const response = await fetch(suggestionsUrl);
        if (!response.ok) {
          throw new Error(`Failed to fetch suggestions (${response.status})`);
        }
        const data: Suggestion[] = await response.json();
        setSuggestions(data);
        // Clear general error if suggestions load, but keep noPlayerFoundError if it exists
        setError(null);
      } catch (err) {
        console.error("Failed to fetch suggestions:", err);
        // Avoid setting a generic error if a 'not found' error is already present from fetchPlayerDetails
        if (!noPlayerFoundError) {
            setError(err instanceof Error ? err.message : "Could not fetch suggestions.");
        }
        setSuggestions([]); // Clear suggestions on error
      }
    }, 300); // 300ms debounce

    // Cleanup function
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  // Only depend on searchTerm. isLoading/playerData added check inside effect.
  }, [searchTerm, isLoading, playerData, noPlayerFoundError]); // Keep isLoading/playerData here to *cancel* fetch


  // Handle suggestion selection
  const handleSuggestionClick = (suggestion: Suggestion) => {
      // Clear any pending suggestion fetch immediately
      if (debounceTimer.current) clearTimeout(debounceTimer.current);

      setSearchTerm(suggestion.full_name); // Update input field
      setSuggestions([]); // Hide suggestions immediately
      fetchPlayerDetails(suggestion.full_name); // Fetch details for the selected player
  };

   // Handle search submission (e.g., pressing Enter)
   const handleSearchSubmit = (event?: React.FormEvent<HTMLFormElement>) => {
       if (event) event.preventDefault(); // Prevent default form submission
       if (searchTerm.trim()) {
           fetchPlayerDetails(searchTerm.trim());
       }
   };

  return (
    <div className="container mx-auto p-4 space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">NBA Player Analytics</h1>

      {/* Search and Filters */}
      <div className="flex flex-col md:flex-row gap-4 items-start">
           {/* Search Bar with Suggestions */}
         <div className="relative flex-grow w-full md:w-auto">
           <form onSubmit={handleSearchSubmit} className="flex gap-2">
             <Input
               type="search"
               placeholder="Search for a player (e.g., LeBron James)"
               value={searchTerm}
               onChange={(e) => setSearchTerm(e.target.value)}
               className="pr-10 w-full" // Adjust padding for potential button/icon
             />
             <Button type="submit" disabled={isLoading}>
               {isLoading ? 'Searching...' : 'Search'}
             </Button>
           </form>
           {suggestions.length > 0 && (
             <Card className="absolute z-20 mt-1 w-full border shadow-lg max-h-60 overflow-y-auto">
               <CardContent className="p-0">
                 {suggestions.map((s) => (
                   <button
                     key={s.id}
                     onClick={() => handleSuggestionClick(s)}
                     className="flex items-center justify-between w-full px-4 py-2 text-left hover:bg-accent focus:outline-none focus:bg-accent"
                   >
                     <span>{s.full_name}</span>
                     {s.is_active && <Badge variant="secondary">Active</Badge>}
                   </button>
                 ))}
               </CardContent>
             </Card>
           )}
         </div>


        {/* Filters */}
        {/* <div className="flex flex-wrap gap-2">
          {filterOptions.map((filter) => (
            <Select key={filter.label}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder={filter.label} />
              </SelectTrigger>
              <SelectContent>
                {filter.options.map((option) => (
                  <SelectItem key={option} value={option.toLowerCase()}>
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ))}
          <Button variant="outline">Apply Filters</Button>
        </div> */}
      </div>


      {/* Loading State */}
      {isLoading && !playerData && ( // Show skeleton only when loading initial data
          <div className="mt-4 w-full max-w-4xl mx-auto">
              <Skeleton className="h-40 w-full mb-4" /> {/* Header Skeleton */}
              <Skeleton className="h-20 w-full mb-4" /> {/* Career Averages Skeleton */}
              <Skeleton className="h-60 w-full" /> {/* Table Skeleton */}
          </div>
      )}

      {/* Error Display */}
       {error && !isLoading && (
         <Alert variant="destructive" className="mt-4 max-w-4xl mx-auto">
           <ExclamationTriangleIcon className="h-4 w-4" />
           <AlertTitle>Error</AlertTitle>
           <AlertDescription>{error}</AlertDescription>
         </Alert>
       )}
       {noPlayerFoundError && !isLoading && (
         <Alert variant="default" className="mt-4 max-w-4xl mx-auto">
              <AlertTitle>Not Found</AlertTitle>
              <AlertDescription>{noPlayerFoundError}</AlertDescription>
          </Alert>
       )}


      {/* Player Profile Display */}
      {!isLoading && playerData && (
        <PlayerProfileCard playerData={playerData} headshotUrl={headshotUrl} />
      )}

      {/* Placeholder when no player is searched */}
      {!isLoading && !playerData && !error && !noPlayerFoundError && (
        <div className="text-center text-muted-foreground mt-10">
          <p>Search for a player to see their statistics.</p>
        </div>
      )}

    </div>
  );
}