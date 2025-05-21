"use client";

import { CareerOrSeasonStat } from "@/app/(app)/players/types"; // Adjust path as necessary
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { formatStat } from "@/lib/utils"; // Import formatStat from utils

interface SeasonStatsTableProps {
  seasons: CareerOrSeasonStat[];
  title: string;
}

export function SeasonStatsTable({ seasons, title }: SeasonStatsTableProps) {
  if (!seasons || seasons.length === 0) {
    return <p className="text-muted-foreground text-center py-4">No {title.toLowerCase()} data available.</p>;
  }

  return (
    <div>
      <h3 className="text-lg font-semibold mb-2">{title}</h3>
      <ScrollArea className="h-[300px] w-full rounded-md border">
        <Table className="relative">
          <TableHeader className="sticky top-0 bg-background z-10">
            <TableRow>
              <TableHead>Season</TableHead>
              <TableHead>Team</TableHead>
              <TableHead className="text-right">GP</TableHead>
              <TableHead className="text-right">GS</TableHead>
              <TableHead className="text-right">MIN</TableHead>
              <TableHead className="text-right">PTS</TableHead>
              <TableHead className="text-right">REB</TableHead>
              <TableHead className="text-right">AST</TableHead>
              <TableHead className="text-right">STL</TableHead>
              <TableHead className="text-right">BLK</TableHead>
              <TableHead className="text-right">FG%</TableHead>
              <TableHead className="text-right">3P%</TableHead>
              <TableHead className="text-right">FT%</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {seasons.map((season) => (
              <TableRow key={`${title}-${season.SEASON_ID}-${season.TEAM_ABBREVIATION}`}>
                <TableCell>{season.SEASON_ID}</TableCell>
                <TableCell>{season.TEAM_ABBREVIATION || 'N/A'}</TableCell>
                <TableCell className="text-right">{formatStat(season.GP, 0)}</TableCell>
                <TableCell className="text-right">{formatStat(season.GS, 0)}</TableCell>
                <TableCell className="text-right">{formatStat(season.MIN)}</TableCell>
                <TableCell className="text-right">{formatStat(season.PTS)}</TableCell>
                <TableCell className="text-right">{formatStat(season.REB)}</TableCell>
                <TableCell className="text-right">{formatStat(season.AST)}</TableCell>
                <TableCell className="text-right">{formatStat(season.STL)}</TableCell>
                <TableCell className="text-right">{formatStat(season.BLK)}</TableCell>
                <TableCell className="text-right">{formatStat((season.FG_PCT ?? 0) * 100)}%</TableCell>
                <TableCell className="text-right">{formatStat((season.FG3_PCT ?? 0) * 100)}%</TableCell>
                <TableCell className="text-right">{formatStat((season.FT_PCT ?? 0) * 100)}%</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ScrollArea>
    </div>
  );
} 