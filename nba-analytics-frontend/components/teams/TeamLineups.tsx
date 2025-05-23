"use client";

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

interface TeamLineupsProps {
  teamId: string;
  season: string;
}

export function TeamLineups({ teamId, season }: TeamLineupsProps) {
  const [filter, setFilter] = useState("all");
  
  // This would be fetched from an API in a real implementation
  const lineups = [
    {
      id: "1",
      players: ["Stephen Curry", "Klay Thompson", "Andrew Wiggins", "Draymond Green", "Kevon Looney"],
      minutes: 150,
      gamesPlayed: 12,
      offRtg: 115.2,
      defRtg: 106.7,
      netRtg: 8.5,
      pace: 101.2,
      plusMinus: 68,
      type: "starters"
    },
    {
      id: "2",
      players: ["Stephen Curry", "Jordan Poole", "Klay Thompson", "Andrew Wiggins", "Draymond Green"],
      minutes: 120,
      gamesPlayed: 15,
      offRtg: 112.8,
      defRtg: 107.6,
      netRtg: 5.2,
      pace: 104.5,
      plusMinus: 42,
      type: "small"
    },
    {
      id: "3",
      players: ["Stephen Curry", "Gary Payton II", "Andrew Wiggins", "Draymond Green", "Kevon Looney"],
      minutes: 100,
      gamesPlayed: 10,
      offRtg: 108.5,
      defRtg: 101.4,
      netRtg: 7.1,
      pace: 99.8,
      plusMinus: 38,
      type: "defensive"
    },
    {
      id: "4",
      players: ["Jordan Poole", "Moses Moody", "Jonathan Kuminga", "JaMychal Green", "James Wiseman"],
      minutes: 85,
      gamesPlayed: 18,
      offRtg: 107.2,
      defRtg: 110.5,
      netRtg: -3.3,
      pace: 103.2,
      plusMinus: -15,
      type: "bench"
    },
    {
      id: "5",
      players: ["Stephen Curry", "Donte DiVincenzo", "Klay Thompson", "Jonathan Kuminga", "Draymond Green"],
      minutes: 75,
      gamesPlayed: 8,
      offRtg: 114.6,
      defRtg: 109.2,
      netRtg: 5.4,
      pace: 102.8,
      plusMinus: 22,
      type: "closing"
    },
  ];
  
  const filteredLineups = filter === "all" 
    ? lineups 
    : lineups.filter(lineup => lineup.type === filter);
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Team Lineups</h2>
        <Select value={filter} onValueChange={setFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filter lineups" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Lineups</SelectItem>
            <SelectItem value="starters">Starters</SelectItem>
            <SelectItem value="closing">Closing</SelectItem>
            <SelectItem value="small">Small Ball</SelectItem>
            <SelectItem value="defensive">Defensive</SelectItem>
            <SelectItem value="bench">Bench</SelectItem>
          </SelectContent>
        </Select>
      </div>
      
      <Tabs defaultValue="table" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="table">Table View</TabsTrigger>
          <TabsTrigger value="cards">Card View</TabsTrigger>
        </TabsList>
        
        <TabsContent value="table" className="pt-4">
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Lineup</TableHead>
                  <TableHead className="text-right">MIN</TableHead>
                  <TableHead className="text-right">GP</TableHead>
                  <TableHead className="text-right">OFF RTG</TableHead>
                  <TableHead className="text-right">DEF RTG</TableHead>
                  <TableHead className="text-right">NET RTG</TableHead>
                  <TableHead className="text-right">PACE</TableHead>
                  <TableHead className="text-right">+/-</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredLineups.map((lineup) => (
                  <TableRow key={lineup.id}>
                    <TableCell className="font-medium">
                      <div>
                        {lineup.players.join(", ")}
                      </div>
                      <div className="mt-1">
                        <Badge variant="outline" className="text-xs">
                          {lineup.type.charAt(0).toUpperCase() + lineup.type.slice(1)}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">{lineup.minutes}</TableCell>
                    <TableCell className="text-right">{lineup.gamesPlayed}</TableCell>
                    <TableCell className="text-right">{lineup.offRtg.toFixed(1)}</TableCell>
                    <TableCell className="text-right">{lineup.defRtg.toFixed(1)}</TableCell>
                    <TableCell className={cn(
                      "text-right font-medium",
                      lineup.netRtg > 0 ? "text-green-600" : "text-red-600"
                    )}>
                      {lineup.netRtg > 0 ? "+" : ""}{lineup.netRtg.toFixed(1)}
                    </TableCell>
                    <TableCell className="text-right">{lineup.pace.toFixed(1)}</TableCell>
                    <TableCell className={cn(
                      "text-right font-medium",
                      lineup.plusMinus > 0 ? "text-green-600" : "text-red-600"
                    )}>
                      {lineup.plusMinus > 0 ? "+" : ""}{lineup.plusMinus}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
        
        <TabsContent value="cards" className="pt-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredLineups.map((lineup) => (
              <Card key={lineup.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <Badge variant="outline">
                      {lineup.type.charAt(0).toUpperCase() + lineup.type.slice(1)}
                    </Badge>
                    <div className={cn(
                      "text-sm font-medium",
                      lineup.netRtg > 0 ? "text-green-600" : "text-red-600"
                    )}>
                      Net Rating: {lineup.netRtg > 0 ? "+" : ""}{lineup.netRtg.toFixed(1)}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex flex-wrap gap-1">
                      {lineup.players.map((player, i) => (
                        <Badge key={i} variant="secondary">{player}</Badge>
                      ))}
                    </div>
                    <div className="grid grid-cols-4 gap-2 pt-2">
                      <div className="text-center">
                        <p className="text-xs text-muted-foreground">Minutes</p>
                        <p className="font-medium">{lineup.minutes}</p>
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-muted-foreground">OFF</p>
                        <p className="font-medium">{lineup.offRtg.toFixed(1)}</p>
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-muted-foreground">DEF</p>
                        <p className="font-medium">{lineup.defRtg.toFixed(1)}</p>
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-muted-foreground">+/-</p>
                        <p className={cn(
                          "font-medium",
                          lineup.plusMinus > 0 ? "text-green-600" : "text-red-600"
                        )}>
                          {lineup.plusMinus > 0 ? "+" : ""}{lineup.plusMinus}
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
} 