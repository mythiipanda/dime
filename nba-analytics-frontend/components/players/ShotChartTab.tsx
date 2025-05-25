"use client";

import { useState, useEffect } from "react";
import { useRouter } from 'next/navigation';
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Loader2, Target } from "lucide-react";
import { seasons } from "@/lib/constants";
import ShotChart from "@/components/charts/ShotChart";
import { usePlayerShotData } from "@/hooks/usePlayerShotData";
import { usePlayerSearchSuggestions } from "@/hooks/usePlayerSearchSuggestions";
import { Suggestion } from "@/app/(app)/players/types";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

const BLUR_TIMEOUT_MS = 150;
const MIN_COMPARE_SEARCH_LENGTH = 2;

interface ShotChartTabProps {
  playerName: string;
}

export function ShotChartTab({ playerName }: ShotChartTabProps) {
  const router = useRouter();
  const [season, setSeason] = useState(seasons[0]);
  const [seasonType, setSeasonType] = useState("Regular Season");

  const {
    shotData,
    zoneData,
    isLoading,
    error,
    fetchData: refetchShotData
  } = usePlayerShotData({ playerName, season, seasonType });

  const [compareSearchQuery, setCompareSearchQuery] = useState("");
  const [isCompareSearchFocused, setIsCompareSearchFocused] = useState(false);
  const {
    suggestions: compareSearchResults,
    isLoading: isCompareSearching,
    error: compareSearchError,
    fetchSuggestions: fetchCompareSuggestions,
    clearSuggestions: clearCompareSuggestions
  } = usePlayerSearchSuggestions();

  useEffect(() => {
    if (isCompareSearchFocused && compareSearchQuery.length >= MIN_COMPARE_SEARCH_LENGTH) {
      fetchCompareSuggestions(compareSearchQuery);
    } else if (compareSearchQuery.length < MIN_COMPARE_SEARCH_LENGTH) {
      clearCompareSuggestions();
    }
  }, [compareSearchQuery, isCompareSearchFocused, fetchCompareSuggestions, clearCompareSuggestions]);

  const handleComparePlayerSelect = (selectedPlayer: Suggestion) => {
    clearCompareSuggestions();
    setCompareSearchQuery("");
    setIsCompareSearchFocused(false);

    const params = new URLSearchParams();
    params.append("player_names", playerName);
    params.append("player_names", selectedPlayer.full_name);

    router.push(`/player-comparison?${params.toString()}`);
  };

  const handleRetryShotData = () => {
    refetchShotData();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row gap-4 items-start justify-between">
        <div className="space-y-1">
          <h3 className="text-xl font-semibold">Shot Distribution Analysis</h3>
          <p className="text-sm text-muted-foreground">
            Visualize {playerName}&apos;s shooting patterns and efficiency.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-3">
          <div className="w-full sm:w-auto min-w-[150px]">
            <Label htmlFor={`${playerName}-season`} className="text-xs">Season</Label>
            <Select value={season} onValueChange={setSeason} >
              <SelectTrigger id={`${playerName}-season`} className="h-9">
                <SelectValue placeholder="Select season" />
              </SelectTrigger>
              <SelectContent>
                {seasons.map(s => (
                  <SelectItem key={s} value={s}>{s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="w-full sm:w-auto min-w-[180px]">
            <Label htmlFor={`${playerName}-season-type`} className="text-xs">Season Type</Label>
            <Select value={seasonType} onValueChange={setSeasonType}>
              <SelectTrigger id={`${playerName}-season-type`} className="h-9">
                <SelectValue placeholder="Select season type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Regular Season">Regular Season</SelectItem>
                <SelectItem value="Playoffs">Playoffs</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <Card>
        <CardContent className="pt-6">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-[400px] text-muted-foreground">
              <Loader2 className="h-10 w-10 animate-spin mb-3 text-primary" />
              <p className="text-lg font-medium">Loading Shot Data...</p>
              <p className="text-sm">Fetching details for {playerName}.</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-[400px] text-destructive">
              <p className="text-lg font-medium mb-2">Error Loading Shot Data</p>
              <p className="text-sm mb-4 text-center max-w-md">{error}</p>
              <Button variant="outline" size="sm" onClick={handleRetryShotData}>
                Retry
              </Button>
            </div>
          ) : shotData.length > 0 ? (
            <ShotChart
              playerName={playerName}
              shots={shotData}
              zones={zoneData}
              season={season}
              seasonType={seasonType}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-[400px] text-muted-foreground">
               <Target className="h-12 w-12 mb-3 text-gray-400" />
              <p className="text-lg font-medium">No Shot Data Available</p>
              <p className="text-sm text-center max-w-sm">
                No shot data found for {playerName} for the selected season ({season} - {seasonType}). Try different filters or check back later.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="pt-4 mt-6 border-t">
        <div className="flex flex-col md:flex-row gap-4 items-start justify-between mb-3">
            <div className="space-y-1">
            <h3 className="text-xl font-semibold">Compare Shot Charts</h3>
            <p className="text-sm text-muted-foreground">
                Select another player to compare with {playerName}.
            </p>
            </div>
        </div>
        <div className="w-full md:max-w-sm relative">
          <Label htmlFor={`${playerName}-compare-player`} className="text-xs">Search Player to Compare</Label>
          <div className="relative mt-1">
            <input
              id={`${playerName}-compare-player`}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 pr-10"
              placeholder="Enter player name..."
              value={compareSearchQuery}
              onChange={(e) => setCompareSearchQuery(e.target.value)}
              onFocus={() => setIsCompareSearchFocused(true)}
              onBlur={() => setTimeout(() => setIsCompareSearchFocused(false), BLUR_TIMEOUT_MS)}
              autoComplete="off"
            />
            {isCompareSearching && (
              <Loader2 className="h-4 w-4 animate-spin absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            )}
          </div>

          {isCompareSearchFocused && (isCompareSearching || compareSearchResults.length > 0 || compareSearchError) && (
            <Card className="absolute z-20 mt-1 w-full border bg-popover text-popover-foreground shadow-lg max-h-60 overflow-y-auto">
              <CardContent className="p-1">
                {isCompareSearching && <p className="text-xs text-muted-foreground px-2 py-1.5">Searching...</p>}
                {compareSearchError && <p className="text-xs text-destructive px-2 py-1.5">Error: {compareSearchError}</p>}
                {!isCompareSearching && compareSearchResults.length === 0 && !compareSearchError && compareSearchQuery.trim().length >= MIN_COMPARE_SEARCH_LENGTH && (
                  <p className="text-xs text-muted-foreground px-2 py-1.5">No players found.</p>
                )}
                {compareSearchResults.length > 0 && (
                  <ul className="divide-y divide-border">
                    {compareSearchResults.map((player) => (
                      <li key={player.id}>
                        <Button
                          variant="ghost"
                          className="w-full justify-start h-auto px-2 py-1.5 text-sm font-normal hover:bg-accent/50 rounded-sm"
                          onMouseDown={() => handleComparePlayerSelect(player)}
                        >
                          <span className={cn("truncate", { 'text-muted-foreground': !player.is_active })}>
                            {player.full_name}
                          </span>
                          {!player.is_active && (
                            <Badge variant="outline" className="ml-auto text-xs px-1.5 py-0.5">Inactive</Badge>
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
    </div>
  );
}
