'use client';

import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Settings } from "lucide-react";

export default function CustomAgentConfigurator() {
  // Mock data
  const teams = ["Lakers", "Celtics", "Warriors", "Nets", "Bucks", "Nuggets"];
  const focusAreas = [
    { id: "offense", label: "Offensive Schemes & Play Types" },
    { id: "defense", label: "Defensive Matchups & Rotations" },
    { id: "player_dev", label: "Player Development Tracking" },
    { id: "scouting", label: "Draft Scouting Targets" },
    { id: "trade", label: "Trade/FA Opportunity Analysis" },
  ];

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center">
           <Settings className="mr-2 h-5 w-5" />
           Custom Agent Configurator (Mock)
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
            <Label htmlFor="agent-team">Target Team</Label>
            <Select>
              <SelectTrigger id="agent-team">
                <SelectValue placeholder="Select Team..." />
              </SelectTrigger>
              <SelectContent>
                {teams.map(team => <SelectItem key={team} value={team}>{team}</SelectItem>)}
              </SelectContent>
            </Select>
        </div>
        <div className="space-y-2">
            <Label htmlFor="agent-name">Agent Nickname (Optional)</Label>
            <Input id="agent-name" placeholder="e.g., LakerLens" />
        </div>
        <div className="space-y-3">
            <Label>Focus Areas</Label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3">
                {focusAreas.map(area => (
                    <div key={area.id} className="flex items-center justify-between space-x-2 p-2 border rounded-md bg-background">
                        <Label htmlFor={`focus-${area.id}`} className="text-sm font-normal">
                            {area.label}
                        </Label>
                        <Switch id={`focus-${area.id}`} defaultChecked={area.id === 'offense' || area.id === 'defense'} />
                    </div>
                ))}
            </div>
        </div>
      </CardContent>
      <CardFooter>
        <Button className="w-full" disabled> {/* Disabled for mock */} 
          Save Agent Configuration
        </Button>
      </CardFooter>
    </Card>
  );
} 