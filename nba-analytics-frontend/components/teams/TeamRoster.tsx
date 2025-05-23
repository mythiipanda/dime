"use client";

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

interface TeamRosterProps {
  teamId: string;
  season: string;
}

export function TeamRoster({ teamId, season }: TeamRosterProps) {
  const [searchQuery, setSearchQuery] = useState("");
  
  // This would be fetched from an API in a real implementation
  const players = [
    {
      id: "1",
      name: "Stephen Curry",
      number: "30",
      position: "PG",
      height: "6'2\"",
      weight: "185",
      age: 35,
      experience: "14 years",
      college: "Davidson",
      stats: {
        ppg: 26.8,
        rpg: 4.2,
        apg: 6.5,
        spg: 1.2,
        bpg: 0.4,
        fg: 0.487,
        fg3: 0.412,
        ft: 0.925,
        mpg: 32.5,
        efg: 0.587,
        per: 25.1,
        ts: 0.624,
        usg: 30.5
      }
    },
    {
      id: "2",
      name: "Klay Thompson",
      number: "11",
      position: "SG",
      height: "6'6\"",
      weight: "215",
      age: 33,
      experience: "11 years",
      college: "Washington State",
      stats: {
        ppg: 17.9,
        rpg: 3.3,
        apg: 2.3,
        spg: 0.7,
        bpg: 0.4,
        fg: 0.434,
        fg3: 0.385,
        ft: 0.875,
        mpg: 30.2,
        efg: 0.535,
        per: 15.2,
        ts: 0.568,
        usg: 24.8
      }
    },
    {
      id: "3",
      name: "Andrew Wiggins",
      number: "22",
      position: "SF",
      height: "6'7\"",
      weight: "197",
      age: 28,
      experience: "9 years",
      college: "Kansas",
      stats: {
        ppg: 12.7,
        rpg: 4.3,
        apg: 1.7,
        spg: 0.8,
        bpg: 0.6,
        fg: 0.454,
        fg3: 0.365,
        ft: 0.705,
        mpg: 28.5,
        efg: 0.502,
        per: 13.5,
        ts: 0.532,
        usg: 21.2
      }
    },
    {
      id: "4",
      name: "Draymond Green",
      number: "23",
      position: "PF",
      height: "6'6\"",
      weight: "230",
      age: 33,
      experience: "11 years",
      college: "Michigan State",
      stats: {
        ppg: 8.8,
        rpg: 7.2,
        apg: 6.0,
        spg: 1.1,
        bpg: 0.8,
        fg: 0.526,
        fg3: 0.305,
        ft: 0.712,
        mpg: 31.5,
        efg: 0.521,
        per: 15.8,
        ts: 0.548,
        usg: 15.6
      }
    },
    {
      id: "5",
      name: "Kevon Looney",
      number: "5",
      position: "C",
      height: "6'9\"",
      weight: "222",
      age: 27,
      experience: "8 years",
      college: "UCLA",
      stats: {
        ppg: 5.5,
        rpg: 6.8,
        apg: 2.5,
        spg: 0.5,
        bpg: 0.5,
        fg: 0.625,
        fg3: 0.000,
        ft: 0.605,
        mpg: 20.5,
        efg: 0.583,
        per: 12.8,
        ts: 0.592,
        usg: 10.2
      }
    },
    {
      id: "6",
      name: "Jordan Poole",
      number: "3",
      position: "SG",
      height: "6'4\"",
      weight: "194",
      age: 24,
      experience: "4 years",
      college: "Michigan",
      stats: {
        ppg: 15.8,
        rpg: 2.5,
        apg: 4.5,
        spg: 0.7,
        bpg: 0.2,
        fg: 0.432,
        fg3: 0.375,
        ft: 0.872,
        mpg: 27.5,
        efg: 0.522,
        per: 14.5,
        ts: 0.562,
        usg: 25.1
      }
    },
  ];
  
  const filteredPlayers = players.filter(player => 
    player.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    player.position.toLowerCase().includes(searchQuery.toLowerCase())
  );
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Team Roster</h2>
        <div className="w-[250px]">
          <Input
            placeholder="Search players..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>
      
      <Tabs defaultValue="main" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="main">Main Stats</TabsTrigger>
          <TabsTrigger value="advanced">Advanced Stats</TabsTrigger>
          <TabsTrigger value="bio">Player Info</TabsTrigger>
        </TabsList>
        
        <TabsContent value="main" className="pt-4">
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Player</TableHead>
                  <TableHead className="text-right">PPG</TableHead>
                  <TableHead className="text-right">RPG</TableHead>
                  <TableHead className="text-right">APG</TableHead>
                  <TableHead className="text-right">FG%</TableHead>
                  <TableHead className="text-right">3P%</TableHead>
                  <TableHead className="text-right">FT%</TableHead>
                  <TableHead className="text-right">MPG</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredPlayers.map((player) => (
                  <TableRow key={player.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <Avatar className="h-8 w-8">
                          <div className="bg-primary text-primary-foreground rounded-full h-full w-full flex items-center justify-center text-xs font-bold">
                            {player.number}
                          </div>
                        </Avatar>
                        <div>
                          {player.name}
                          <div className="text-xs text-muted-foreground">
                            {player.position}
                          </div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">{player.stats.ppg.toFixed(1)}</TableCell>
                    <TableCell className="text-right">{player.stats.rpg.toFixed(1)}</TableCell>
                    <TableCell className="text-right">{player.stats.apg.toFixed(1)}</TableCell>
                    <TableCell className="text-right">{(player.stats.fg * 100).toFixed(1)}%</TableCell>
                    <TableCell className="text-right">{(player.stats.fg3 * 100).toFixed(1)}%</TableCell>
                    <TableCell className="text-right">{(player.stats.ft * 100).toFixed(1)}%</TableCell>
                    <TableCell className="text-right">{player.stats.mpg.toFixed(1)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
        
        <TabsContent value="advanced" className="pt-4">
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Player</TableHead>
                  <TableHead className="text-right">eFG%</TableHead>
                  <TableHead className="text-right">TS%</TableHead>
                  <TableHead className="text-right">PER</TableHead>
                  <TableHead className="text-right">USG%</TableHead>
                  <TableHead className="text-right">STL</TableHead>
                  <TableHead className="text-right">BLK</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredPlayers.map((player) => (
                  <TableRow key={player.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <Avatar className="h-8 w-8">
                          <div className="bg-primary text-primary-foreground rounded-full h-full w-full flex items-center justify-center text-xs font-bold">
                            {player.number}
                          </div>
                        </Avatar>
                        <div>
                          {player.name}
                          <div className="text-xs text-muted-foreground">
                            {player.position}
                          </div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">{(player.stats.efg * 100).toFixed(1)}%</TableCell>
                    <TableCell className="text-right">{(player.stats.ts * 100).toFixed(1)}%</TableCell>
                    <TableCell className="text-right">{player.stats.per.toFixed(1)}</TableCell>
                    <TableCell className="text-right">{player.stats.usg.toFixed(1)}%</TableCell>
                    <TableCell className="text-right">{player.stats.spg.toFixed(1)}</TableCell>
                    <TableCell className="text-right">{player.stats.bpg.toFixed(1)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
        
        <TabsContent value="bio" className="pt-4">
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Player</TableHead>
                  <TableHead>Position</TableHead>
                  <TableHead>Height</TableHead>
                  <TableHead>Weight</TableHead>
                  <TableHead>Age</TableHead>
                  <TableHead>Experience</TableHead>
                  <TableHead>College</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredPlayers.map((player) => (
                  <TableRow key={player.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <Avatar className="h-8 w-8">
                          <div className="bg-primary text-primary-foreground rounded-full h-full w-full flex items-center justify-center text-xs font-bold">
                            {player.number}
                          </div>
                        </Avatar>
                        <div>
                          {player.name}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{player.position}</Badge>
                    </TableCell>
                    <TableCell>{player.height}</TableCell>
                    <TableCell>{player.weight} lbs</TableCell>
                    <TableCell>{player.age}</TableCell>
                    <TableCell>{player.experience}</TableCell>
                    <TableCell>{player.college}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
} 