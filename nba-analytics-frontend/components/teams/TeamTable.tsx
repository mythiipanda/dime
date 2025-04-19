"use client";

import React from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TeamStanding } from "@/lib/api/teams";
import { getClinchIndicators, formatStreak } from "@/lib/utils/teams";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

interface TeamTableProps {
  title: string;
  teams: TeamStanding[];
}

export function TeamTable({ title, teams }: TeamTableProps) {
  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">{title}</h2>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-b hover:bg-transparent">
              <TableHead className="w-[50px] text-center py-3 px-2">Rank</TableHead>
              <TableHead className="py-3 px-4">Team</TableHead>
              <TableHead className="text-right py-3 px-4">W</TableHead>
              <TableHead className="text-right py-3 px-4">L</TableHead>
              <TableHead className="text-right py-3 px-4">PCT</TableHead>
              <TableHead className="text-right py-3 px-4">GB</TableHead>
              <TableHead className="text-center py-3 px-4">Home</TableHead>
              <TableHead className="text-center py-3 px-4">Away</TableHead>
              <TableHead className="text-center py-3 px-4">L10</TableHead>
              <TableHead className="text-center py-3 px-4">Streak</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {teams.map((team) => {
              const clinchBadges = getClinchIndicators(team.ClinchIndicator);
              return (
                <TableRow key={team.TeamID} className="border-b border-border/50 hover:bg-muted/50 transition-colors">
                  <TableCell className="font-medium text-center py-3 px-2">{team.PlayoffRank}</TableCell>
                  <TableCell className="py-3 px-4">
                    <div className="font-medium">{team.TeamName}</div>
                    {/* Display clinch indicators as badges */}
                    {clinchBadges.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {clinchBadges.map((badgeText, index) => (
                          <Badge key={index} variant="secondary" className="text-xs font-normal">
                            {badgeText}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="text-right py-3 px-4">{team.WINS}</TableCell>
                  <TableCell className="text-right py-3 px-4">{team.LOSSES}</TableCell>
                  <TableCell className="text-right py-3 px-4">{team.WinPct.toFixed(3)}</TableCell>
                  <TableCell className="text-right py-3 px-4">{team.GB === 0 ? '-' : team.GB.toFixed(1)}</TableCell>
                  <TableCell className="text-center whitespace-nowrap py-3 px-4">{team.HOME}</TableCell>
                  <TableCell className="text-center whitespace-nowrap py-3 px-4">{team.ROAD}</TableCell>
                  <TableCell className="text-center whitespace-nowrap py-3 px-4">{team.L10}</TableCell>
                  <TableCell 
                    className={cn(
                      "text-center whitespace-nowrap py-3 px-4",
                      team.STRK?.startsWith('W') ? "text-green-600 dark:text-green-400" : "",
                      team.STRK?.startsWith('L') ? "text-red-600 dark:text-red-400" : ""
                    )}
                  >
                    {formatStreak(team.STRK)}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

interface TeamTableSkeletonProps {
  conference: string;
  rowCount?: number;
}

const DEFAULT_SKELETON_ROW_COUNT = 10;

// Basic Skeleton component for the table
export function TeamTableSkeleton({ conference, rowCount = DEFAULT_SKELETON_ROW_COUNT }: TeamTableSkeletonProps) {
  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">{conference} Conference</h2>
      <div className="rounded-md border">
         <Table>
           <TableHeader>
             <TableRow>
              <TableHead className="w-[50px] text-center"><Skeleton className="h-5 w-8 mx-auto" /></TableHead>
              <TableHead><Skeleton className="h-5 w-24" /></TableHead>
              <TableHead className="text-right"><Skeleton className="h-5 w-6 ml-auto" /></TableHead>
              <TableHead className="text-right"><Skeleton className="h-5 w-6 ml-auto" /></TableHead>
              <TableHead className="text-right"><Skeleton className="h-5 w-10 ml-auto" /></TableHead>
              <TableHead className="text-right"><Skeleton className="h-5 w-8 ml-auto" /></TableHead>
              <TableHead className="text-center"><Skeleton className="h-5 w-12 mx-auto" /></TableHead>
              <TableHead className="text-center"><Skeleton className="h-5 w-12 mx-auto" /></TableHead>
              <TableHead className="text-center"><Skeleton className="h-5 w-12 mx-auto" /></TableHead>
              <TableHead className="text-center"><Skeleton className="h-5 w-8 mx-auto" /></TableHead>
            </TableRow>
           </TableHeader>
           <TableBody>
            {Array.from({ length: rowCount }).map((_, index) => (
               <TableRow key={index}>
                 <TableCell className="text-center"><Skeleton className="h-5 w-6 mx-auto" /></TableCell>
                 <TableCell><Skeleton className="h-5 w-32" /></TableCell>
                 <TableCell className="text-right"><Skeleton className="h-5 w-6 ml-auto" /></TableCell>
                 <TableCell className="text-right"><Skeleton className="h-5 w-6 ml-auto" /></TableCell>
                 <TableCell className="text-right"><Skeleton className="h-5 w-10 ml-auto" /></TableCell>
                 <TableCell className="text-right"><Skeleton className="h-5 w-8 ml-auto" /></TableCell>
                 <TableCell className="text-center"><Skeleton className="h-5 w-12 mx-auto" /></TableCell>
                 <TableCell className="text-center"><Skeleton className="h-5 w-12 mx-auto" /></TableCell>
                 <TableCell className="text-center"><Skeleton className="h-5 w-12 mx-auto" /></TableCell>
                 <TableCell className="text-center"><Skeleton className="h-5 w-8 mx-auto" /></TableCell>
               </TableRow>
             ))}
           </TableBody>
         </Table>
       </div>
    </div>
  );
} 