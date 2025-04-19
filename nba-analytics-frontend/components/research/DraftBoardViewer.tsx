'use client';

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { ListOrdered } from "lucide-react";

export default function DraftBoardViewer() {
  // Mock data
  const years = ["2025", "2024", "2023", "2022"];
  const mockDraftPicks = [
    { pick: 1, team: "Spurs", player: "Victor Wembanyama", pos: "C", school: "Metropolitans 92" },
    { pick: 2, team: "Hornets", player: "Brandon Miller", pos: "SF", school: "Alabama" },
    { pick: 3, team: "Trail Blazers", player: "Scoot Henderson", pos: "PG", school: "G League Ignite" },
    { pick: 4, team: "Rockets", player: "Amen Thompson", pos: "SG", school: "Overtime Elite" },
    { pick: 5, team: "Pistons", player: "Ausar Thompson", pos: "SF", school: "Overtime Elite" },
    // Add more mock picks as desired
  ];

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center">
          <ListOrdered className="mr-2 h-5 w-5" />
          NBA Draft Board (Mock)
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1 space-y-2">
                <Label htmlFor="draft-year">Draft Year</Label>
                <Select defaultValue="2023">
                <SelectTrigger id="draft-year">
                    <SelectValue placeholder="Select Year..." />
                </SelectTrigger>
                <SelectContent>
                    {years.map(year => <SelectItem key={year} value={year}>{year}</SelectItem>)}
                </SelectContent>
                </Select>
            </div>
            <div className="flex-1 space-y-2">
                <Label htmlFor="draft-filter">Filter Players</Label>
                <Input id="draft-filter" placeholder="Search player or team..." />
            </div>
        </div>
        
        <div className="overflow-x-auto border rounded-md">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[60px]">Pick</TableHead>
                <TableHead>Team</TableHead>
                <TableHead>Player</TableHead>
                <TableHead className="w-[80px]">Pos</TableHead>
                <TableHead>College/Team</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mockDraftPicks.map((pick) => (
                <TableRow key={pick.pick}>
                  <TableCell className="font-medium">{pick.pick}</TableCell>
                  <TableCell>{pick.team}</TableCell>
                  <TableCell>{pick.player}</TableCell>
                  <TableCell>{pick.pos}</TableCell>
                  <TableCell>{pick.school}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
      {/* No CardFooter needed for this view */}
    </Card>
  );
} 