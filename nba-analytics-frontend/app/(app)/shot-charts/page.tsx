"use client";

import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import Image from "next/image"; // For placeholder

export default function ShotChartsPage() {
  // Placeholder data - in a real app, this would come from state or API
  const players = [
    { id: "1", name: "LeBron James" },
    { id: "2", name: "Stephen Curry" },
    { id: "3", name: "Kevin Durant" },
    { id: "4", name: "Jayson Tatum" },
    { id: "5", name: "Nikola Jokic" },
  ];
  const seasons = ["2024-25", "2023-24", "2022-23", "2021-22"];

  const [selectedPlayer, setSelectedPlayer] = React.useState(players[0].id);
  const [selectedSeason, setSelectedSeason] = React.useState(seasons[0]);

  return (
    <div className="space-y-8 py-2"> {/* Added py-2 for a bit of breathing room from AppLayout's padding */}
      <header className="animate-in fade-in-0 slide-in-from-top-4 duration-500">
        <h1 className="text-3xl font-bold tracking-tight">Player Shot Charts</h1>
        <p className="text-muted-foreground mt-1">
          Visualize player shooting patterns and performance across seasons.
        </p>
      </header>
      <Separator />

      <Card className="animate-in fade-in-0 slide-in-from-bottom-4 duration-500 delay-100">
        <CardHeader>
          <CardTitle>Filters</CardTitle>
          <CardDescription>Select a player and season to view their shot chart.</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          <div className="space-y-1.5 animate-in fade-in-0 slide-in-from-bottom-2 duration-300 delay-200">
            <Label htmlFor="player-select">Player</Label>
            <Select value={selectedPlayer} onValueChange={setSelectedPlayer}>
              <SelectTrigger id="player-select" className="w-full">
                <SelectValue placeholder="Select player" />
              </SelectTrigger>
              <SelectContent>
                {players.map(player => (
                  <SelectItem key={player.id} value={player.id}>{player.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5 animate-in fade-in-0 slide-in-from-bottom-2 duration-300 delay-250">
            <Label htmlFor="season-select">Season</Label>
            <Select value={selectedSeason} onValueChange={setSelectedSeason}>
              <SelectTrigger id="season-select" className="w-full">
                <SelectValue placeholder="Select season" />
              </SelectTrigger>
              <SelectContent>
                {seasons.map(season => (
                  <SelectItem key={season} value={season}>{season}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5 animate-in fade-in-0 slide-in-from-bottom-2 duration-300 delay-300">
            <Label htmlFor="shot-type">Shot Type (Example)</Label>
            <Select disabled>
              <SelectTrigger id="shot-type" className="w-full">
                <SelectValue placeholder="All Shots" />
              </SelectTrigger>
              <SelectContent><SelectItem value="all">All</SelectItem></SelectContent>
            </Select>
          </div>
          <div className="flex items-end animate-in fade-in-0 slide-in-from-bottom-2 duration-300 delay-350">
            <Button className="w-full sm:w-auto">
              {/* Icon can be added here e.g. <FilterIcon className="mr-2 h-4 w-4" /> */}
              Apply Filters
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="animate-in fade-in-0 slide-in-from-bottom-4 duration-500 delay-200">
        <CardHeader>
          <CardTitle>
            Shot Chart: {players.find(p => p.id === selectedPlayer)?.name} - {selectedSeason}
          </CardTitle>
          <CardDescription>Visualization of shots taken during the selected period.</CardDescription>
        </CardHeader>
        <CardContent className="aspect-[16/10] bg-muted/30 rounded-lg flex items-center justify-center border-2 border-dashed border-border/50 p-4">
          <div className="text-center text-muted-foreground space-y-2">
            <Image 
              src="/nba-court.svg" 
              alt="NBA Court Outline for Shot Chart" 
              width={600} 
              height={375} 
              className="opacity-100 dark:opacity-70 max-w-full h-auto mx-auto" 
              priority
            />
            <p className="text-lg font-semibold">Shot Chart Visualization Area</p>
            <p className="text-sm">An interactive shot chart will be rendered here based on selections.</p>
          </div>
        </CardContent>
      </Card>

      <Card className="animate-in fade-in-0 slide-in-from-bottom-4 duration-500 delay-300">
        <CardHeader>
          <CardTitle>Key Shooting Statistics</CardTitle>
          <CardDescription>Summary for {players.find(p => p.id === selectedPlayer)?.name} in {selectedSeason}.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {['Overall FG%', '3PT FG%', 'Effective FG%', 'Points Per Shot', 'Shot Attempts', 'Made Shots', 'Free Throw %', 'True Shooting %'].map((statName, i) => (
              <div key={i} className="p-4 bg-muted/50 rounded-lg animate-in fade-in-0 zoom-in-95 duration-300" style={{animationDelay: `${i * 50 + 400}ms`}}>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{statName}</p>
                <p className="text-2xl font-bold mt-1">XX.X%</p> {/* Placeholder value */}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
