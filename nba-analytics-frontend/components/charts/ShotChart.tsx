"use client";

import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Play, Pause, RotateCcw, Filter, Loader2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useShotChartFilters, SHOT_TYPES_FILTER, SHOT_ZONES_FILTER } from '@/lib/hooks/useShotChartFilters';
import { useAdvancedShotChartData, ChartDataType } from '@/lib/hooks/useAdvancedShotChartData';
import { ShotChartFiltersComponent } from './ShotChartFilters';
import { ShotZoneTable } from './ShotZoneTable';
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Shot, ZoneData } from './types';

interface ShotChartProps {
  playerName: string;
  shots: Shot[];
  zones: ZoneData[];
  className?: string;
  season?: string;
  seasonType?: string;
}

export function ShotChart({ playerName, shots: initialShots, zones, className, season: initialSeason, seasonType: initialSeasonType }: ShotChartProps) {
  const [activeTab, setActiveTab] = useState<'chart' | 'zones'>('chart');
  const [showFilterControls, setShowFilterControls] = useState(false);
  
  const { 
    filters,
    setters,
    maxShotDistance
  } = useShotChartFilters({ initialShots });

  const {
    isLoading: isLoadingChartData,
    error: chartDataError,
    chartImage,
    chartType: currentChartType,
    fetchAdvancedShotChart,
    clearError: clearChartDataError,
  } = useAdvancedShotChartData();

  const [selectedDisplayChartType, setSelectedDisplayChartType] = useState<ChartDataType>('scatter');

  useEffect(() => {
    if (playerName) {
      fetchAdvancedShotChart(playerName, initialSeason, initialSeasonType, 'scatter');
    }
  }, [playerName, initialSeason, initialSeasonType]);

  const handleFetchChartType = (type: ChartDataType) => {
    setSelectedDisplayChartType(type);
    fetchAdvancedShotChart(playerName, initialSeason, initialSeasonType, type);
  };

  const resetAllFilters = () => {
    setters.setSelectedShotType(SHOT_TYPES_FILTER[0]);
    setters.setSelectedZone(SHOT_ZONES_FILTER[0]);
    setters.setMinDistance(0);
    setters.setMaxDistance(maxShotDistance);
    setters.setShowMadeShots(true);
    setters.setShowMissedShots(true);
    setters.setShowTwoPointers(true);
    setters.setShowThreePointers(true);
    fetchAdvancedShotChart(playerName, initialSeason, initialSeasonType, 'scatter');
  };

  return (
    <Card className={cn("w-full", className)}>
      <CardContent className="p-0 md:p-2">
        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as 'chart' | 'zones')} className="w-full">
          <div className="flex flex-col sm:flex-row justify-between items-center p-2 md:p-4 border-b">
            <TabsList>
          <TabsTrigger value="chart">Shot Chart</TabsTrigger>
              <TabsTrigger value="zones">Zone Stats</TabsTrigger>
        </TabsList>
            <Button variant="outline" size="sm" onClick={() => setShowFilterControls(!showFilterControls)} className="mt-2 sm:mt-0">
              <Filter className="mr-2 h-4 w-4" /> {showFilterControls ? 'Hide' : 'Show'} Filters
            </Button>
          </div>

          {showFilterControls && activeTab === 'chart' && (
            <ShotChartFiltersComponent 
              filters={filters}
              setters={setters}
              maxShotDistance={maxShotDistance}
              onResetFilters={resetAllFilters}
            />
          )}

          <TabsContent value="chart" className="p-1 md:p-4">
            <div className="mb-4 flex flex-wrap gap-2 items-center">
                <Button onClick={() => handleFetchChartType('scatter')} variant={selectedDisplayChartType === 'scatter' ? 'default' : 'outline'} size="sm" disabled={isLoadingChartData}>Scatter</Button>
                <Button onClick={() => handleFetchChartType('heatmap')} variant={selectedDisplayChartType === 'heatmap' ? 'default' : 'outline'} size="sm" disabled={isLoadingChartData}>Heatmap</Button>
                <Button onClick={() => handleFetchChartType('hexbin')} variant={selectedDisplayChartType === 'hexbin' ? 'default' : 'outline'} size="sm" disabled={isLoadingChartData}>Hexbin</Button>
                  </div>

            {chartDataError && (
                <Alert variant="destructive" className="mb-4">
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>Error Loading Chart</AlertTitle>
                    <AlertDescription>
                        {chartDataError} 
                        <Button variant="link" onClick={clearChartDataError} className="p-0 h-auto ml-2">Dismiss</Button>
                    </AlertDescription>
                </Alert>
            )}
            
            {isLoadingChartData && (
                <div className="flex flex-col items-center justify-center h-96 bg-muted/50 rounded-md">
                    <Loader2 className="h-12 w-12 animate-spin text-primary" />
                    <p className="mt-4 text-muted-foreground">Loading {selectedDisplayChartType} chart...</p>
                </div>
            )}

            {!isLoadingChartData && chartImage && (
                <img src={`data:image/png;base64,${chartImage}`} alt={`${playerName} ${currentChartType} shot chart`} className="w-full h-auto rounded-md border" />
            )}

            {!isLoadingChartData && !chartImage && !chartDataError && activeTab === 'chart' && (
                 <div className="flex flex-col items-center justify-center h-96 bg-muted/50 rounded-md">
                    <AlertCircle className="h-12 w-12 text-muted-foreground" />
                    <p className="mt-4 text-muted-foreground">No chart image available. Select a chart type or try again.</p>
              </div>
            )}
        </TabsContent>

          <TabsContent value="zones">
            <ShotZoneTable zones={zones} />
        </TabsContent>
      </Tabs>
      </CardContent>
    </Card>
  );
}
