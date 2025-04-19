"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PlayerData } from "./types";
import { PlayerProfileCard } from "@/components/players/PlayerProfileCard";

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
        <div className="text-center py-10 text-muted-foreground">
          <Search className="mx-auto h-12 w-12 mb-4" />
          <p>Search for an NBA player to view their detailed profile and statistics.</p>
        </div>
      )}
    </div>
  );
}

// Remove outdated TODO comments
// TODO:
// 1. Move PlayerProfileCard, StatBox, formatStat, PlayerData, Suggestion etc. to separate files (e.g., components/players/, types/players.ts)
// 2. Potentially refine loading state indication if needed beyond loading.tsx
