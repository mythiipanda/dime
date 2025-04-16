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
import { TeamStanding, getClinchIndicators, formatStreak, formatRecord } from "@/lib/api/teams";
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
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[50px] text-center">Rank</TableHead>
              <TableHead>Team</TableHead>
              <TableHead className="text-right">W</TableHead>
              <TableHead className="text-right">L</TableHead>
              <TableHead className="text-right">PCT</TableHead>
              <TableHead className="text-right">GB</TableHead>
              <TableHead className="text-center">Home</TableHead>
              <TableHead className="text-center">Away</TableHead>
              <TableHead className="text-center">L10</TableHead>
              <TableHead className="text-center">Streak</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {teams.map((team) => {
              const clinchBadges = getClinchIndicators(team.ClinchIndicator);
              return (
                <TableRow key={team.TeamID}>
                  <TableCell className="font-medium text-center">{team.PlayoffRank}</TableCell>
                  <TableCell>
                    <div className="font-medium">{team.TeamName}</div>
                    {/* Display clinch indicators as badges */}
                    {clinchBadges.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {clinchBadges.map((badgeText, index) => (
                          <Badge key={index} variant="secondary" className="text-xs">
                            {badgeText}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="text-right">{team.WINS}</TableCell>
                  <TableCell className="text-right">{team.LOSSES}</TableCell>
                  <TableCell className="text-right">{team.WinPct.toFixed(3)}</TableCell>
                  <TableCell className="text-right">{team.GB === 0 ? '-' : team.GB.toFixed(1)}</TableCell>
                  <TableCell className="text-center whitespace-nowrap">{team.HOME}</TableCell>
                  <TableCell className="text-center whitespace-nowrap">{team.ROAD}</TableCell>
                  <TableCell className="text-center whitespace-nowrap">{team.L10}</TableCell>
                  <TableCell 
                    className={cn(
                      "text-center whitespace-nowrap",
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

// Basic Skeleton component for the table
export function TeamTableSkeleton({ conference, rowCount = 10 }: TeamTableSkeletonProps) {
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