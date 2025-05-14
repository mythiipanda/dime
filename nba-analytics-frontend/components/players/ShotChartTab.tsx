"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, Target, BarChart2, Activity, Grid, GitCompare } from "lucide-react";
import { seasons } from "@/lib/constants";
import { ShotChart } from "@/components/charts/ShotChart";

interface ShotChartTabProps {
  playerName: string;
}

export function ShotChartTab({ playerName }: ShotChartTabProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [shotData, setShotData] = useState<any[]>([]);
  const [zoneData, setZoneData] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [season, setSeason] = useState(seasons[0]);
  const [seasonType, setSeasonType] = useState("Regular Season");
  const [chartType, setChartType] = useState("scatter");
  const [comparisonPlayer, setComparisonPlayer] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch shot data when player name, season, or season type changes
  useEffect(() => {
    if (!playerName) return;
    
    const fetchShotData = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        const params = new URLSearchParams();
        if (season) params.append("season", season);
        if (seasonType) params.append("season_type", seasonType);
        
        const response = await fetch(`/api/v1/analyze/player/${encodeURIComponent(playerName)}/shots?${params.toString()}`);
        
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || `Failed to fetch shot data: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
          throw new Error(data.error);
        }
        
        // Process shot data
        const shots = data.shots.map((shot: any) => ({
          x: shot.x,
          y: shot.y,
          made: shot.made,
          value: shot.value,
          shot_type: shot.shot_type,
          shot_zone: shot.zone,
          distance: shot.distance,
          game_date: shot.game_date,
          period: shot.period
        }));
        
        // Process zone data
        const zones = Object.entries(data.zones).map(([zone, stats]: [string, any]) => ({
          zone,
          attempts: stats.attempts,
          made: stats.made,
          percentage: stats.percentage / 100,
          leaguePercentage: stats.league_percentage / 100,
          relativePercentage: stats.relative_percentage / 100
        }));
        
        setShotData(shots);
        setZoneData(zones);
      } catch (error) {
        console.error("Error fetching shot data:", error);
        setError(error instanceof Error ? error.message : "Failed to fetch shot data");
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchShotData();
  }, [playerName, season, seasonType]);

  // Handle search for comparison player
  const handleSearchChange = async (value: string) => {
    setSearchQuery(value);
    
    if (value.length < 2) {
      setSearchResults([]);
      return;
    }
    
    setIsSearching(true);
    
    try {
      const response = await fetch(`/api/v1/players/search?query=${encodeURIComponent(value)}`);
      
      if (!response.ok) {
        throw new Error("Failed to search players");
      }
      
      const data = await response.json();
      setSearchResults(data.players || []);
    } catch (error) {
      console.error("Error searching players:", error);
    } finally {
      setIsSearching(false);
    }
  };

  // Handle comparison player selection
  const handleComparePlayer = async (selectedPlayerName: string) => {
    setComparisonPlayer(selectedPlayerName);
    setSearchQuery("");
    setSearchResults([]);
    
    // Navigate to comparison page
    window.location.href = `/player-comparison?player_names=${encodeURIComponent(playerName)}&player_names=${encodeURIComponent(selectedPlayerName)}`;
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col md:flex-row gap-4 items-start justify-between">
        <div className="space-y-2">
          <h3 className="text-lg font-semibold">Shot Distribution</h3>
          <p className="text-sm text-muted-foreground">
            Visualize {playerName}'s shooting patterns and efficiency
          </p>
        </div>
        
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="w-full sm:w-40">
            <Label htmlFor="season" className="text-xs">Season</Label>
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
          
          <div className="w-full sm:w-48">
            <Label htmlFor="season-type" className="text-xs">Season Type</Label>
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
        </div>
      </div>
      
      <Card>
        <CardContent className="pt-6">
          {isLoading ? (
            <div className="flex items-center justify-center h-[400px]">
              <div className="text-center">
                <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2 text-primary" />
                <p className="text-sm text-muted-foreground">Loading shot data...</p>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-[400px]">
              <div className="text-center p-4">
                <p className="text-sm text-red-500 mb-2">{error}</p>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => window.location.reload()}
                >
                  Retry
                </Button>
              </div>
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
            <div className="flex items-center justify-center h-[400px]">
              <p className="text-muted-foreground">No shot data available for this player.</p>
            </div>
          )}
        </CardContent>
      </Card>
      
      <div className="flex flex-col md:flex-row gap-4 items-start justify-between">
        <div className="space-y-2">
          <h3 className="text-lg font-semibold">Compare with Another Player</h3>
          <p className="text-sm text-muted-foreground">
            Compare {playerName}'s shooting patterns with another player
          </p>
        </div>
        
        <div className="w-full md:w-64 relative">
          <Label htmlFor="compare-player" className="text-xs">Search Player</Label>
          <div className="relative">
            <input
              id="compare-player"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              placeholder="Enter player name..."
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
            />
            {isSearching && (
              <Loader2 className="h-4 w-4 animate-spin absolute right-3 top-3 text-muted-foreground" />
            )}
          </div>
          
          {searchResults.length > 0 && (
            <div className="absolute z-10 w-full mt-1 border rounded-md bg-background shadow-md max-h-60 overflow-y-auto">
              <div className="divide-y">
                {searchResults.map((player) => (
                  <div
                    key={player.id}
                    className="flex items-center justify-between p-2 hover:bg-accent/50 cursor-pointer"
                    onClick={() => handleComparePlayer(player.full_name)}
                  >
                    <div className="flex items-center gap-2">
                      <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center text-xs">
                        {player.full_name.split(" ").map((n: string) => n[0]).join("")}
                      </div>
                      <div>
                        <p className="text-sm font-medium">{player.full_name}</p>
                        <p className="text-xs text-muted-foreground">
                          {player.team_name || (player.is_active ? "Active" : "Inactive")}
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Compare players"
                    >
                      <GitCompare className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
