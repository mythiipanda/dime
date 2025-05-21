"use client";

import { CareerOrSeasonStat } from "@/app/(app)/players/types"; // Adjust path as necessary
import { StatBox } from "./StatBox"; // Import StatBox from the new file
import { formatStat } from "@/lib/utils"; // Import formatStat from utils

interface CareerAveragesProps {
  careerStats: CareerOrSeasonStat | null | undefined;
  title: string;
}

export function CareerAverages({ careerStats, title }: CareerAveragesProps) {
  if (!careerStats) {
    return <p className="text-muted-foreground text-center py-4">No {title.toLowerCase()} available.</p>;
  }

  return (
    <div>
      <h3 className="text-lg font-semibold mb-2">{title}</h3>
      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3 text-center">
        <StatBox label="GP" value={careerStats.GP} decimals={0} />
        <StatBox label="PTS" value={careerStats.PTS} />
        <StatBox label="REB" value={careerStats.REB} />
        <StatBox label="AST" value={careerStats.AST} />
        <StatBox label="FG%" value={(careerStats.FG_PCT ?? 0) * 100} suffix="%" />
        <StatBox label="3P%" value={(careerStats.FG3_PCT ?? 0) * 100} suffix="%" />
        <StatBox label="FT%" value={(careerStats.FT_PCT ?? 0) * 100} suffix="%" />
        <StatBox label="STL" value={careerStats.STL} />
        <StatBox label="BLK" value={careerStats.BLK} />
        <StatBox label="MIN" value={careerStats.MIN} />
      </div>
    </div>
  );
} 