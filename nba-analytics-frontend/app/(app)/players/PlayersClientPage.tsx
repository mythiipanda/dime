"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PlayerData } from "./types";
import { PlayerProfileCard } from "@/components/players/PlayerProfileCard";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"; // Added Card components
import { Button } from "@/components/ui/button"; // Added Button
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Search } from "lucide-react";
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
  const currentSearchParams = useSearchParams();

  const playerData = initialPlayerData;
  const headshotUrl = initialHeadshotUrl;
  const fetchError = serverFetchError;
  const noPlayerFoundError = fetchError?.toLowerCase().includes("not found") ? fetchError : null;
  const generalFetchError = fetchError && !noPlayerFoundError ? fetchError : null;

  const handleSearchSubmit = (term: string) => {
    const trimmedSearch = term.trim();
    if (trimmedSearch) {
      const params = new URLSearchParams(currentSearchParams.toString());
      params.set("query", trimmedSearch);
      router.push(`/players?${params.toString()}`);
    }
  };

  return (
    <div className="container mx-auto p-4 space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">NBA Player Analytics</h1>

      <div className="flex flex-col md:flex-row gap-4 items-start">
        <PlayerSearchBar
          initialValue={initialSearchTerm || ""}
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
        <PlayerProfileCard playerData={playerData} headshotUrl={headshotUrl} />
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
                  onClick={() => handleSearchSubmit(name)}
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
