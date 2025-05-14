"use client";

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, Loader2, Filter } from "lucide-react";
import { ExclamationTriangleIcon } from '@radix-ui/react-icons';
import { ShotChart } from '@/components/charts/ShotChart';
import { PlayerSearchBar } from "@/components/players/PlayerSearchBar";

// Import types from the ShotChart component
interface Shot {
  x: number;
  y: number;
  made: boolean;
  value: number;
  shot_type?: string;
  shot_zone?: string;
  distance?: number;
  game_date?: string;
  period?: number;
}

interface ZoneData {
  zone: string;
  attempts: number;
  made: number;
  percentage: number;
  leaguePercentage: number;
  relativePercentage: number;
}

// Sample empty data for initial state

// Season options
const SEASONS = [
  "2023-24",
  "2022-23",
  "2021-22",
  "2020-21",
  "2019-20",
  "2018-19",
  "2017-18",
  "2016-17",
  "2015-16",
];

// Season type options
const SEASON_TYPES = [
  "Regular Season",
  "Playoffs",
  "Pre Season",
  "All Star"
];

export default function ShotChartsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [playerName, setPlayerName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shotData, setShotData] = useState<Shot[]>([]);
  const [zoneData, setZoneData] = useState<ZoneData[]>([]);

  // Filter states
  const [selectedSeason, setSelectedSeason] = useState<string>("2023-24");
  const [selectedSeasonType, setSelectedSeasonType] = useState<string>("Regular Season");
  const [showFilters, setShowFilters] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!searchTerm.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      // Build query parameters
      const params = new URLSearchParams();
      if (selectedSeason) params.append('season', selectedSeason);
      if (selectedSeasonType) params.append('season_type', selectedSeasonType);

      // Fetch shot data from the API
      const url = `/api/v1/analyze/player/${encodeURIComponent(searchTerm)}/shots${params.toString() ? `?${params.toString()}` : ''}`;
      const response = await fetch(url);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Failed to fetch shot data: ${response.statusText}`);
      }

      const data = await response.json();

      setPlayerName(data.player_name);
      setShotData(data.shots);
      setZoneData(data.zones);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred while fetching shot data');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle filter changes
  const applyFilters = () => {
    if (playerName) {
      // Create a synthetic event that can be prevented
      const syntheticEvent = { preventDefault: () => {} } as React.FormEvent;
      handleSearch(syntheticEvent);
    }
  };

  // Effect to apply filters when they change
  useEffect(() => {
    if (playerName) {
      applyFilters();
    }
  }, [selectedSeason, selectedSeasonType]);

  return (
    <div className="container mx-auto p-4 space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">NBA Shot Charts</h1>

      <Card>
        <CardHeader>
          <CardTitle>Shot Chart Analysis</CardTitle>
          <CardDescription>
            Search for a player to view their shot chart and shooting efficiency by zone.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex gap-2">
              <PlayerSearchBar
                initialValue={searchTerm}
                onSearchSubmit={(term: string) => {
                  setSearchTerm(term);
                  // Create a synthetic event that can be prevented
                  const syntheticEvent = { preventDefault: () => {} } as React.FormEvent;
                  handleSearch(syntheticEvent);
                }}
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowFilters(!showFilters)}
                className="flex items-center gap-1"
              >
                <Filter className="h-4 w-4" />
                Filters
              </Button>
              {isLoading && (
                <div className="flex items-center">
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  <span className="text-sm">Loading...</span>
                </div>
              )}
            </div>

            {showFilters && (
              <div className="p-4 border rounded-md bg-slate-50 dark:bg-slate-900">
                <h3 className="text-sm font-medium mb-3">Filter Options</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium mb-1 block">Season</label>
                    <Select
                      value={selectedSeason}
                      onValueChange={setSelectedSeason}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select season" />
                      </SelectTrigger>
                      <SelectContent>
                        {SEASONS.map(season => (
                          <SelectItem key={season} value={season}>{season}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <label className="text-sm font-medium mb-1 block">Season Type</label>
                    <Select
                      value={selectedSeasonType}
                      onValueChange={setSelectedSeasonType}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select season type" />
                      </SelectTrigger>
                      <SelectContent>
                        {SEASON_TYPES.map(type => (
                          <SelectItem key={type} value={type}>{type}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
            )}
          </div>

          {error && (
            <Alert variant="destructive" className="mb-4">
              <ExclamationTriangleIcon className="h-4 w-4" />
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {!playerName && !isLoading && !error && (
            <div className="text-center py-12">
              <Search className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">Search for a Player</h3>
              <p className="text-muted-foreground mb-4">
                Enter a player name to view their shot chart and shooting efficiency.
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {["Stephen Curry", "LeBron James", "Kevin Durant", "Luka Doncic"].map(name => (
                  <Button
                    key={name}
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setSearchTerm(name);
                      // Create a synthetic event that can be prevented
                      const syntheticEvent = { preventDefault: () => {} } as React.FormEvent;
                      handleSearch(syntheticEvent);
                    }}
                  >
                    {name}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {playerName && !isLoading && !error && (
            <ShotChart
              playerName={playerName}
              shots={shotData}
              zones={zoneData}
              className="mt-4"
              season={selectedSeason}
              seasonType={selectedSeasonType}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
