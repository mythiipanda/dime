'use client';

import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { FileText, UserSearch } from "lucide-react";

export default function PlayerScoutingReportGenerator() {
  // Mock data
  const mockPlayers = ["LeBron James", "Stephen Curry", "Kevin Durant", "Nikola Jokic", "Victor Wembanyama"];
  const reportSections = [
    { id: "physical", label: "Physical Profile & Measurements" },
    { id: "offense", label: "Offensive Skills Breakdown (Shooting, Finishing, Playmaking)" },
    { id: "defense", label: "Defensive Skills Breakdown (Perimeter, Interior, Rebounding)" },
    { id: "strengths", label: "Key Strengths" },
    { id: "weaknesses", label: "Areas for Improvement" },
    { id: "projection", label: "NBA Role Projection & Player Comps" },
    { id: "stats", label: "Relevant Statistics (College/Pro)" },
  ];

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center">
          <UserSearch className="mr-2 h-5 w-5" />
          Player Scouting Report Generator (Mock)
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
            <Label htmlFor="scouting-player">Player to Scout</Label>
            <Select>
              <SelectTrigger id="scouting-player">
                <SelectValue placeholder="Select Player..." />
              </SelectTrigger>
              <SelectContent>
                {mockPlayers.map(player => <SelectItem key={player} value={player}>{player}</SelectItem>)}
              </SelectContent>
            </Select>
            {/* Or maybe an input for searching players */}
        </div>

        <div className="space-y-3">
            <Label>Report Sections to Include</Label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {reportSections.map(section => (
                    <div key={section.id} className="flex items-center space-x-2 p-2 border rounded-md">
                        <Checkbox id={`scout-${section.id}`} defaultChecked />
                        <Label htmlFor={`scout-${section.id}`} className="text-sm font-normal cursor-pointer">
                            {section.label}
                        </Label>
                    </div>
                ))}
            </div>
        </div>
        <div className="space-y-2">
            <Label htmlFor="report-focus">Specific Focus (Optional)</Label>
            <Input id="report-focus" placeholder="e.g., Focus on pick-and-roll defense, three-point consistency" />
        </div>
      </CardContent>
      <CardFooter>
        <Button className="w-full" disabled> {/* Disabled for mock */} 
          <FileText className="mr-2 h-4 w-4" />
          Generate Scouting Report
        </Button>
      </CardFooter>
    </Card>
  );
} 