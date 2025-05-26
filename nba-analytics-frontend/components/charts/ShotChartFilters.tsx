"use client";

import React from 'react';
import { Slider } from "@/components/ui/slider";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Filter } from 'lucide-react';
import { SHOT_TYPES_FILTER, SHOT_ZONES_FILTER, ShotChartFilters } from '@/lib/hooks/useShotChartFilters';

interface ShotChartFiltersComponentProps {
  filters: ShotChartFilters;
  setters: {
    setSelectedShotType: (value: string) => void;
    setSelectedZone: (value: string) => void;
    setMinDistance: (value: number) => void;
    setMaxDistance: (value: number) => void;
    setShowMadeShots: (value: boolean) => void;
    setShowMissedShots: (value: boolean) => void;
    setShowTwoPointers: (value: boolean) => void;
    setShowThreePointers: (value: boolean) => void;
  };
  maxShotDistance: number;
  onResetFilters: () => void;
}

export function ShotChartFiltersComponent({
  filters,
  setters,
  maxShotDistance,
  onResetFilters,
}: ShotChartFiltersComponentProps) {
  return (
    <div className="space-y-6 p-4 border-b">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Shot Type Select */}
        <div>
          <Label htmlFor="shot-type-filter">Shot Type</Label>
          <Select value={filters.selectedShotType} onValueChange={setters.setSelectedShotType}>
            <SelectTrigger id="shot-type-filter">
              <SelectValue placeholder="Select shot type" />
            </SelectTrigger>
            <SelectContent>
              {SHOT_TYPES_FILTER.map(type => (
                <SelectItem key={type} value={type}>{type}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Shot Zone Select */}
        <div>
          <Label htmlFor="shot-zone-filter">Shot Zone</Label>
          <Select value={filters.selectedZone} onValueChange={setters.setSelectedZone}>
            <SelectTrigger id="shot-zone-filter">
              <SelectValue placeholder="Select shot zone" />
            </SelectTrigger>
            <SelectContent>
              {SHOT_ZONES_FILTER.map(zone => (
                <SelectItem key={zone} value={zone}>{zone}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Distance Slider */}
      <div>
        <Label>Shot Distance (ft): {filters.minDistance} - {filters.maxDistance}</Label>
        <Slider
          min={0}
          max={maxShotDistance}
          step={1}
          value={[filters.minDistance, filters.maxDistance]}
          onValueChange={(value) => {
            setters.setMinDistance(value[0]);
            setters.setMaxDistance(value[1]);
          }}
          className="mt-2"
        />
      </div>

      {/* Switches for Toggles */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="flex items-center space-x-2">
          <Switch id="made-shots" checked={filters.showMadeShots} onCheckedChange={setters.setShowMadeShots} />
          <Label htmlFor="made-shots">Made</Label>
        </div>
        <div className="flex items-center space-x-2">
          <Switch id="missed-shots" checked={filters.showMissedShots} onCheckedChange={setters.setShowMissedShots} />
          <Label htmlFor="missed-shots">Missed</Label>
        </div>
        <div className="flex items-center space-x-2">
          <Switch id="two-pointers" checked={filters.showTwoPointers} onCheckedChange={setters.setShowTwoPointers} />
          <Label htmlFor="two-pointers">2 Pointers</Label>
        </div>
        <div className="flex items-center space-x-2">
          <Switch id="three-pointers" checked={filters.showThreePointers} onCheckedChange={setters.setShowThreePointers} />
          <Label htmlFor="three-pointers">3 Pointers</Label>
        </div>
      </div>
      
      <Button onClick={onResetFilters} variant="outline" size="sm" className="w-full md:w-auto">
        <Filter className="mr-2 h-4 w-4" /> Reset Filters
      </Button>
    </div>
  );
} 