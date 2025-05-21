"use client";

import React from 'react';
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from '@/lib/utils';
import { ZoneData } from './types'; // Import from new types file

interface ShotZoneTableProps {
  zones: ZoneData[]; // Use imported ZoneData
}

export function ShotZoneTable({ zones }: ShotZoneTableProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Zone</TableHead>
              <TableHead className="text-right">FGM</TableHead>
              <TableHead className="text-right">FGA</TableHead>
              <TableHead className="text-right">FG%</TableHead>
              <TableHead className="text-right">League FG%</TableHead>
              <TableHead className="text-right">vs League</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {zones.map((zone) => (
              <TableRow key={zone.zone}>
                <TableCell>{zone.zone}</TableCell>
                <TableCell className="text-right">{zone.made}</TableCell>
                <TableCell className="text-right">{zone.attempts}</TableCell>
                <TableCell className="text-right">{(zone.percentage * 100).toFixed(1)}%</TableCell>
                <TableCell className="text-right">{(zone.leaguePercentage * 100).toFixed(1)}%</TableCell>
                <TableCell 
                  className={cn("text-right", {
                    'text-green-600': zone.relativePercentage > 0,
                    'text-red-600': zone.relativePercentage < 0,
                  })}
                >
                  {zone.relativePercentage > 0 ? '+' : ''}{(zone.relativePercentage * 100).toFixed(1)}%
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
} 