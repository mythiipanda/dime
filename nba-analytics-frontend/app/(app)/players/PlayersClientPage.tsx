"use client";

import * as React from "react";
import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PlayerData, AdvancedMetrics, SkillGrades } from "./types";
import { PlayerProfileCard } from "@/components/players/PlayerProfileCard";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Search, Loader2 } from "lucide-react";
import { ExclamationTriangleIcon } from '@radix-ui/react-icons';
import { PlayerSearchBar } from "@/components/players/PlayerSearchBar";

interface PlayersClientPageProps {
  initialSearchTerm: string | null;
  initialPlayerData: PlayerData | null;
  initialHeadshotUrl: string | null;
  serverFetchError: string | null;
}

export default function PlayersClientPage({
  initialSearchTerm,
  initialPlayerData,
  initialHeadshotUrl,
  serverFetchError,
}: PlayersClientPageProps) {
  const router = useRouter();
  const currentSearchParams = useSearchParams(); // Keep for reading initial state if needed, but not for forced reloads

  const [playerData, setPlayerData] = useState<PlayerData | null>(initialPlayerData);
  const [headshotUrl, setHeadshotUrl] = useState<string | null>(initialHeadshotUrl);
  const [fetchError, setFetchError] = useState<string | null>(serverFetchError);
  const [isLoadingAdvanced, setIsLoadingAdvanced] = useState<boolean>(false);
  const [advancedFetchError, setAdvancedFetchError] = useState<string | null>(null);

  // Update state if initial props change (e.g., due to navigation)
  useEffect(() => {
    setPlayerData(initialPlayerData);
    setHeadshotUrl(initialHeadshotUrl);
    setFetchError(serverFetchError);
    setAdvancedFetchError(null);
  }, [initialPlayerData, initialHeadshotUrl, serverFetchError]);

  const noPlayerFoundError = fetchError?.toLowerCase().includes("not found") ? fetchError : null;
  const generalFetchError = fetchError && !noPlayerFoundError ? fetchError : null;

  const fetchAdvancedMetrics = async () => {
    if (playerData?.player_info?.DISPLAY_FIRST_LAST && !playerData.advanced_metrics) {
      try {
        setIsLoadingAdvanced(true);
        setAdvancedFetchError(null);
        const playerName = playerData.player_info.DISPLAY_FIRST_LAST;
        console.log(`Fetching advanced metrics for ${playerName}`);
        const response = await fetch(`/api/v1/analyze/player/${encodeURIComponent(playerName)}/advanced`);
        if (!response.ok) {
          const errorText = `Failed to fetch advanced metrics: ${response.status} ${response.statusText}`;
          console.error(errorText);
          setAdvancedFetchError(errorText);
          return;
        }
        const data = await response.json();
        setPlayerData(prevData => {
          if (!prevData) return null;
          return {
            ...prevData,
            advanced_metrics: data.advanced_metrics || null,
            skill_grades: data.skill_grades || null,
            similar_players: data.similar_players || null
          };
        });
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "An unknown error occurred while fetching advanced metrics.";
        console.error("Error fetching advanced metrics:", error);
        setAdvancedFetchError(errorMessage);
      } finally {
        setIsLoadingAdvanced(false);
      }
    }
  };

  // Auto-fetch advanced metrics when player data becomes available (e.g. on initial load or after a new search)
  // This needs to be careful not to re-fetch if they are already loaded or being loaded.
  useEffect(() => {
    if (playerData?.player_info?.DISPLAY_FIRST_LAST && 
        !playerData.advanced_metrics && 
        !playerData.skill_grades && 
        !isLoadingAdvanced &&
        !fetchError &&
        !advancedFetchError
    ) {
      fetchAdvancedMetrics();
    }
    // Dependencies: Trigger when playerData is newly available or changes, but not if advanced metrics are already there or loading.
  }, [playerData, isLoadingAdvanced, fetchError, advancedFetchError]); 

  const handleSearchSubmit = (term: string) => {
    const trimmedSearch = term.trim();
    if (trimmedSearch) {
      console.log(`Navigating to search: ${trimmedSearch}`);
      router.push(`/players?query=${encodeURIComponent(trimmedSearch)}`);
    }
  };

  return (
    <div className="container mx-auto p-4 space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">NBA Player Analytics</h1>

      <div className="flex flex-col md:flex-row gap-4 items-start">
        <PlayerSearchBar
          initialValue={initialSearchTerm || ""} // Use initialSearchTerm from props for consistency
          onSearchSubmit={handleSearchSubmit}
        />
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
        <>
          {isLoadingAdvanced && (
            <div className="flex items-center justify-center gap-2 py-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Loading advanced metrics...</span>
            </div>
          )}
          <PlayerProfileCard
            playerData={playerData}
            headshotUrl={headshotUrl}
            onLoadAdvancedMetrics={fetchAdvancedMetrics}
          />
        </>
      )}

      {!playerData && !fetchError && (
        <Card className="mt-6 text-center max-w-2xl mx-auto animate-in fade-in-0 slide-in-from-bottom-4 duration-500">
          <CardHeader>
            <Search className="mx-auto h-10 w-10 text-muted-foreground mb-3" />
            <CardTitle className="text-2xl">Find Your Player</CardTitle>
            <CardDescription>
              Search for an NBA player to view their detailed profile, career stats, and season performance.
            </CardDescription>
          </CardHeader>
          <CardContent className="pb-6">
            <p className="text-sm text-muted-foreground mb-3">Or try an example:</p>
            <div className="flex flex-wrap justify-center gap-2">
              {["LeBron James", "Stephen Curry", "Nikola Jokic", "Victor Wembanyama"].map(name => (
                <Button
                  key={name}
                  variant="outline"
                  size="sm"
                  onClick={() => handleSearchSubmit(name)} // Use handleSearchSubmit for examples too
                  className="transition-all hover:scale-105 hover:bg-accent/50"
                >
                  {name}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// Remove outdated TODO comments
// TODO:
// 1. Move PlayerProfileCard, StatBox, formatStat, PlayerData, Suggestion etc. to separate files (e.g., components/players/, types/players.ts)
// 2. Potentially refine loading state indication if needed beyond loading.tsx
