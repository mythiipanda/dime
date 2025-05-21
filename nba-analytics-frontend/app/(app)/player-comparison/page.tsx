'use client';

import { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { seasons } from '@/lib/constants';
import { PlayerSelectionForm } from '@/components/player-comparison/PlayerSelectionForm';
import { ComparisonOptionsForm } from '@/components/player-comparison/ComparisonOptionsForm';
import { ComparisonResultDisplay } from '@/components/player-comparison/ComparisonResultDisplay';
import { usePlayerComparison } from '@/hooks/usePlayerComparison';
import { toast } from "sonner";
import { Loader2 } from 'lucide-react';

// Define Player type (or import from a shared location if it exists)
interface Player {
  id: number | string;
  full_name: string;
  // Add other relevant player fields if needed
}

export default function PlayerComparisonPage() {
  // State for selected players
  const [selectedPlayers, setSelectedPlayers] = useState<Player[]>([]);

  // State for comparison options
  const [season, setSeason] = useState(seasons[0]); // Default to the first season in the list
  const [seasonType, setSeasonType] = useState('Regular Season');
  const [chartType, setChartType] = useState('scatter');

  // Custom hook for comparison logic
  const {
    isLoading,
    comparisonImage,
    error,
    generateComparison,
  } = usePlayerComparison();

  const handleAddPlayer = useCallback((player: Player) => {
    setSelectedPlayers((prev) => [...prev, player]);
  }, []);

  const handleRemovePlayer = useCallback((playerId: Player['id']) => {
    setSelectedPlayers((prev) => prev.filter(p => p.id !== playerId));
  }, []);

  const handleGenerateComparison = () => {
    generateComparison({ selectedPlayers, season, seasonType, chartType });
  };

  return (
    <div className="container mx-auto py-6 lg:py-8 space-y-6 lg:space-y-8">
      <div className="flex flex-col gap-1 items-center text-center">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Player Shot Comparison</h1>
        <p className="text-muted-foreground max-w-xl">
          Select 2 to 4 players, choose a season and chart type, then generate a visual comparison of their shot charts.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8 items-start">
        {/* Left Column: Controls */}
        <div className="lg:col-span-1 space-y-6">
          <Card className="shadow-lg">
            <CardHeader>
              <CardTitle>1. Select Players</CardTitle>
              <CardDescription>
                Search and add up to 4 players.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <PlayerSelectionForm
                selectedPlayers={selectedPlayers}
                onAddPlayer={handleAddPlayer}
                onRemovePlayer={handleRemovePlayer}
                maxPlayers={4}
              />
            </CardContent>
          </Card>

          <Card className="shadow-lg">
            <CardHeader>
              <CardTitle>2. Comparison Options</CardTitle>
              <CardDescription>
                Configure season and chart details.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ComparisonOptionsForm
                season={season}
                onSeasonChange={setSeason}
                seasonType={seasonType}
                onSeasonTypeChange={setSeasonType}
                chartType={chartType}
                onChartTypeChange={setChartType}
              />
            </CardContent>
          </Card>

          <Button 
            onClick={handleGenerateComparison} 
            disabled={isLoading || selectedPlayers.length < 2}
            className="w-full py-3 text-base font-semibold shadow-md hover:shadow-lg transition-shadow duration-200"
            size="lg"
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                Generating...
              </>
            ) : (
              'Generate Comparison'
            )}
          </Button>
        </div>

        {/* Right Column: Results */}
        <div className="lg:col-span-2">
          <Card className="shadow-xl min-h-[400px] flex items-center justify-center">
            {/* <CardHeader className="w-full text-center">
              <CardTitle>Comparison Result</CardTitle>
            </CardHeader> */}
            <CardContent className="p-4 sm:p-6 w-full">
              <ComparisonResultDisplay
                isLoading={isLoading}
                comparisonImage={comparisonImage}
                error={error}
              />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
