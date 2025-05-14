'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Loader2, X, Search, BarChart2, Activity, Grid } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from "sonner";
import { useDebounce } from '@/hooks/use-debounce';
import { seasons } from '@/lib/constants';
import { PlayerSearchResults } from '@/components/player-search/PlayerSearchResults';

export default function PlayerComparisonPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // State for player search
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const debouncedSearchQuery = useDebounce(searchQuery, 300);

  // State for selected players
  const [selectedPlayers, setSelectedPlayers] = useState<any[]>([]);

  // State for comparison options
  const [season, setSeason] = useState(seasons[0]);
  const [seasonType, setSeasonType] = useState('Regular Season');
  const [chartType, setChartType] = useState('scatter');

  // State for comparison results
  const [isLoading, setIsLoading] = useState(false);
  const [comparisonImage, setComparisonImage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Search for players
  useEffect(() => {
    const searchPlayers = async () => {
      if (debouncedSearchQuery.length < 2) {
        setSearchResults([]);
        return;
      }

      setIsSearching(true);

      try {
        const response = await fetch(`/api/v1/players/search?query=${encodeURIComponent(debouncedSearchQuery)}`);

        if (!response.ok) {
          throw new Error('Failed to search players');
        }

        const data = await response.json();
        setSearchResults(data.players || []);
      } catch (error) {
        console.error('Error searching players:', error);
        toast.error('Failed to search players. Please try again.');
      } finally {
        setIsSearching(false);
      }
    };

    searchPlayers();
  }, [debouncedSearchQuery, toast]);

  // Add player to comparison
  const addPlayer = (player: any) => {
    if (selectedPlayers.length >= 4) {
      toast.error('Maximum players reached. You can compare up to 4 players at a time.');
      return;
    }

    if (selectedPlayers.some(p => p.id === player.id)) {
      toast.error('Player already added. This player is already in the comparison.');
      return;
    }

    setSelectedPlayers([...selectedPlayers, player]);
    setSearchQuery('');
    setSearchResults([]);
  };

  // Remove player from comparison
  const removePlayer = (playerId: number) => {
    setSelectedPlayers(selectedPlayers.filter(p => p.id !== playerId));
  };

  // Generate comparison
  const generateComparison = async () => {
    if (selectedPlayers.length < 2) {
      toast.error('Not enough players. Please select at least 2 players to compare.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Build query parameters
      const params = new URLSearchParams();
      selectedPlayers.forEach(player => {
        params.append('player_names', player.full_name);
      });
      params.append('season', season);
      params.append('seasonType', seasonType);
      params.append('chartType', chartType);
      params.append('outputFormat', 'base64');

      // Fetch comparison from the API
      const response = await fetch(`/api/v1/analyze/players/compare-shots?${params.toString()}`);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Failed to generate comparison: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      // Set the comparison image
      if (data.image_data) {
        setComparisonImage(data.image_data);
      } else {
        throw new Error('No image data returned from the server');
      }
    } catch (error) {
      console.error('Error generating comparison:', error);
      setError(error instanceof Error ? error.message : 'Failed to generate comparison');
      toast.error(error instanceof Error ? error.message : 'Failed to generate comparison');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold">Player Shot Comparison</h1>
        <p className="text-muted-foreground">
          Compare shot charts for multiple NBA players
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-1 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Select Players</CardTitle>
              <CardDescription>
                Choose 2-4 players to compare
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="player-search">Search Players</Label>
                <div className="relative">
                  <Input
                    id="player-search"
                    placeholder="Enter player name..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  {isSearching ? (
                    <Loader2 className="h-4 w-4 animate-spin absolute right-3 top-3 text-muted-foreground" />
                  ) : (
                    <Search className="h-4 w-4 absolute right-3 top-3 text-muted-foreground" />
                  )}
                </div>

                {searchResults.length > 0 && (
                  <div className="border rounded-md max-h-60 overflow-y-auto">
                    <PlayerSearchResults
                      results={searchResults}
                      onSelect={addPlayer}
                    />
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label>Selected Players ({selectedPlayers.length}/4)</Label>
                <div className="flex flex-wrap gap-2">
                  {selectedPlayers.map(player => (
                    <Badge key={player.id} variant="secondary" className="flex items-center gap-1">
                      {player.full_name}
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-4 w-4 p-0"
                        onClick={() => removePlayer(player.id)}
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    </Badge>
                  ))}
                  {selectedPlayers.length === 0 && (
                    <p className="text-sm text-muted-foreground">No players selected</p>
                  )}
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="season">Season</Label>
                <Select value={season} onValueChange={setSeason}>
                  <SelectTrigger id="season">
                    <SelectValue placeholder="Select season" />
                  </SelectTrigger>
                  <SelectContent>
                    {seasons.map(s => (
                      <SelectItem key={s} value={s}>{s}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="season-type">Season Type</Label>
                <Select value={seasonType} onValueChange={setSeasonType}>
                  <SelectTrigger id="season-type">
                    <SelectValue placeholder="Select season type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Regular Season">Regular Season</SelectItem>
                    <SelectItem value="Playoffs">Playoffs</SelectItem>
                    <SelectItem value="Pre Season">Pre Season</SelectItem>
                    <SelectItem value="All Star">All Star</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Chart Type</Label>
                <Tabs value={chartType} onValueChange={setChartType}>
                  <TabsList className="grid grid-cols-3 w-full">
                    <TabsTrigger value="scatter" className="flex items-center gap-1">
                      <Grid className="h-4 w-4" />
                      <span className="hidden sm:inline">Scatter</span>
                    </TabsTrigger>
                    <TabsTrigger value="heatmap" className="flex items-center gap-1">
                      <Activity className="h-4 w-4" />
                      <span className="hidden sm:inline">Heatmap</span>
                    </TabsTrigger>
                    <TabsTrigger value="zones" className="flex items-center gap-1">
                      <BarChart2 className="h-4 w-4" />
                      <span className="hidden sm:inline">Zones</span>
                    </TabsTrigger>
                  </TabsList>
                </Tabs>
              </div>

              <Button
                className="w-full"
                onClick={generateComparison}
                disabled={selectedPlayers.length < 2 || isLoading}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  'Generate Comparison'
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="md:col-span-2">
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Comparison Results</CardTitle>
              <CardDescription>
                {selectedPlayers.length < 2
                  ? 'Select at least 2 players to compare'
                  : `Comparing ${selectedPlayers.map(p => p.full_name).join(', ')}`}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center justify-center h-[500px]">
                  <div className="text-center">
                    <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2 text-primary" />
                    <p className="text-sm text-muted-foreground">Generating comparison...</p>
                  </div>
                </div>
              ) : error ? (
                <div className="flex items-center justify-center h-[500px]">
                  <div className="text-center p-4">
                    <p className="text-sm text-red-500 mb-2">{error}</p>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={generateComparison}
                    >
                      Retry
                    </Button>
                  </div>
                </div>
              ) : comparisonImage ? (
                <div className="flex justify-center">
                  <img
                    src={comparisonImage}
                    alt="Player Shot Comparison"
                    className="max-w-full h-auto"
                  />
                </div>
              ) : (
                <div className="flex items-center justify-center h-[500px] border rounded-md bg-slate-50 dark:bg-slate-900">
                  <p className="text-muted-foreground">
                    Select players and generate a comparison to see results
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
