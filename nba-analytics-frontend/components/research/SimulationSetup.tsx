'use client';

import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Cpu } from "lucide-react";

export default function SimulationSetup() {
  // Mock data - replace with actual data fetching/state later
  const teams = ["Lakers", "Celtics", "Warriors", "Nets", "Bucks", "Nuggets"];

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center">
          <Cpu className="mr-2 h-5 w-5" />
          Simulation Setup (Mock)
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="sim-type">Simulation Type</Label>
          <Select defaultValue="game">
            <SelectTrigger id="sim-type">
              <SelectValue placeholder="Select type..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="game">Single Game</SelectItem>
              <SelectItem value="season">Full Season</SelectItem>
              <SelectItem value="playoffs">Playoff Series</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Separator />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="team-a">Team A</Label>
            <Select>
              <SelectTrigger id="team-a">
                <SelectValue placeholder="Select Team A..." />
              </SelectTrigger>
              <SelectContent>
                {teams.map(team => <SelectItem key={team} value={team}>{team}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="team-b">Team B</Label>
            <Select>
              <SelectTrigger id="team-b">
                <SelectValue placeholder="Select Team B..." />
              </SelectTrigger>
              <SelectContent>
                {teams.map(team => <SelectItem key={team} value={team}>{team}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Add more mock inputs as needed: strategy, player adjustments etc. */}
         <div className="space-y-2">
           <Label>Key Player Adjustments (Optional)</Label>
           <Input placeholder="e.g., LeBron James minutes: 30, Curry focus: Off-ball" />
         </div>

      </CardContent>
      <CardFooter>
        <Button className="w-full" disabled> {/* Disabled for mock */} 
          Run Simulation
        </Button>
      </CardFooter>
    </Card>
  );
} 