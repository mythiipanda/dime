"use client";

import { useState, useMemo } from 'react';
import type { Shot } from '@/components/charts/types'; // Import from new types file

// Define SHOT_TYPES and SHOT_ZONES or import them if they are in a shared constants file
export const SHOT_TYPES_FILTER = [
  'All Types',
  'Jump Shot',
  'Layup',
  'Dunk',
  'Hook Shot',
  'Fadeaway',
  'Step Back Jump Shot',
  'Driving Layup',
  'Pullup Jump Shot',
  'Running Layup',
  'Alley Oop Dunk'
];

export const SHOT_ZONES_FILTER = [
  'All Zones',
  'Restricted Area',
  'In The Paint (Non-RA)',
  'Mid-Range',
  'Left Corner 3',
  'Right Corner 3',
  'Above the Break 3',
  'Backcourt'
];

export interface ShotChartFilters {
  selectedShotType: string;
  selectedZone: string;
  minDistance: number;
  maxDistance: number;
  showMadeShots: boolean;
  showMissedShots: boolean;
  showTwoPointers: boolean;
  showThreePointers: boolean;
}

interface UseShotChartFiltersProps {
  initialShots: Shot[];
  initialFilters?: Partial<ShotChartFilters>;
}

export function useShotChartFilters({
  initialShots,
  initialFilters = {},
}: UseShotChartFiltersProps) {
  const [selectedShotType, setSelectedShotType] = useState(initialFilters.selectedShotType || SHOT_TYPES_FILTER[0]);
  const [selectedZone, setSelectedZone] = useState(initialFilters.selectedZone || SHOT_ZONES_FILTER[0]);
  
  const maxShotDistance = useMemo(() => {
    if (initialShots.length === 0) return 40;
    return Math.ceil(Math.max(...initialShots.filter(shot => shot.distance !== undefined).map(shot => shot.distance as number), 0));
  }, [initialShots]);

  const [minDistance, setMinDistance] = useState(initialFilters.minDistance || 0);
  const [maxDistance, setMaxDistance] = useState(initialFilters.maxDistance || maxShotDistance);
  
  const [showMadeShots, setShowMadeShots] = useState(initialFilters.showMadeShots !== undefined ? initialFilters.showMadeShots : true);
  const [showMissedShots, setShowMissedShots] = useState(initialFilters.showMissedShots !== undefined ? initialFilters.showMissedShots : true);
  const [showTwoPointers, setShowTwoPointers] = useState(initialFilters.showTwoPointers !== undefined ? initialFilters.showTwoPointers : true);
  const [showThreePointers, setShowThreePointers] = useState(initialFilters.showThreePointers !== undefined ? initialFilters.showThreePointers : true);

  const filteredShots = useMemo(() => {
    return initialShots.filter(shot => {
      if (selectedShotType !== SHOT_TYPES_FILTER[0] && shot.shot_type !== selectedShotType) return false;
      if (selectedZone !== SHOT_ZONES_FILTER[0] && !shot.shot_zone?.includes(selectedZone)) return false;
      if (shot.distance !== undefined && (shot.distance < minDistance || shot.distance > maxDistance)) return false;
      if (!showMadeShots && shot.made) return false;
      if (!showMissedShots && !shot.made) return false;
      if (!showTwoPointers && shot.value === 2) return false;
      if (!showThreePointers && shot.value === 3) return false;
      return true;
    });
  }, [
    initialShots,
    selectedShotType,
    selectedZone,
    minDistance,
    maxDistance,
    showMadeShots,
    showMissedShots,
    showTwoPointers,
    showThreePointers,
  ]);

  return {
    filters: {
      selectedShotType,
      selectedZone,
      minDistance,
      maxDistance,
      showMadeShots,
      showMissedShots,
      showTwoPointers,
      showThreePointers,
    },
    setters: {
      setSelectedShotType,
      setSelectedZone,
      setMinDistance,
      setMaxDistance,
      setShowMadeShots,
      setShowMissedShots,
      setShowTwoPointers,
      setShowThreePointers,
    },
    filteredShots,
    maxShotDistance, // Export for slider range
  };
} 