'use client';

import { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import { BarChartHorizontalBig, Users, ShieldCheck, Target } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function StatComparisonTool() {
  // Mock data
  const mockPlayers = ["LeBron James", "Stephen Curry", "Kevin Durant", "Nikola Jokic"];
  const mockTeams = ["Lakers", "Warriors", "Nets", "Nuggets"];
  const mockStats = [
    { id: "pts", label: "Points Per Game" },
    { id: "reb", label: "Rebounds Per Game" },
    { id: "ast", label: "Assists Per Game" },
    { id: "fg_pct", label: "Field Goal %" },
    { id: "fg3_pct", label: "3-Point %" },
    { id: "ws", label: "Win Shares" },
    { id: "per", label: "Player Efficiency Rating" },
  ];
  const [comparisonType, setComparisonType] = useState('players');
  const [selectedEntities, setSelectedEntities] = useState<string[]>([]);
  const [selectedStats, setSelectedStats] = useState<string[]>(["pts", "reb", "ast"]);

  const entities = comparisonType === 'players' ? mockPlayers : mockTeams;

  const handleEntityAdd = (entity: string) => {
      if (entity && !selectedEntities.includes(entity)) {
          setSelectedEntities([...selectedEntities, entity]);
      }
  };

  const handleStatToggle = (statId: string, checked: boolean) => {
      setSelectedStats(prev => 
          checked ? [...prev, statId] : prev.filter(id => id !== statId)
      );
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center">
          <BarChartHorizontalBig className="mr-2 h-5 w-5" />
          Stat Comparison Tool (Mock)
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
                <Label htmlFor="comp-type">Compare</Label>
                <Select value={comparisonType} onValueChange={(value) => {setComparisonType(value); setSelectedEntities([]);}}>
                    <SelectTrigger id="comp-type">
                        <SelectValue placeholder="Select type..." />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="players"><Users className="inline-block mr-2 h-4 w-4"/> Players</SelectItem>
                        <SelectItem value="teams"><ShieldCheck className="inline-block mr-2 h-4 w-4"/> Teams</SelectItem>
                    </SelectContent>
                </Select>
            </div>
            <div className="space-y-2 md:col-span-2">
                 <Label htmlFor="entity-select">Add {comparisonType === 'players' ? 'Player' : 'Team'} to Comparison</Label>
                 <div className="flex gap-2">
                    <Select onValueChange={handleEntityAdd}>
                        <SelectTrigger id="entity-select">
                            <SelectValue placeholder={`Select ${comparisonType === 'players' ? 'Player' : 'Team'}...`} />
                        </SelectTrigger>
                        <SelectContent>
                            {entities.filter(e => !selectedEntities.includes(e)).map(entity => (
                                <SelectItem key={entity} value={entity}>{entity}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                 </div>
                 <div className="flex flex-wrap gap-2 pt-2">
                    {selectedEntities.map(entity => (
                        <Badge key={entity} variant="secondary" className="cursor-pointer" onClick={() => setSelectedEntities(prev => prev.filter(e => e !== entity))}>
                            {entity} &times;
                        </Badge>
                    ))}
                </div>
            </div>
        </div>

        <div className="space-y-3">
            <Label>Select Stats to Compare</Label>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                {mockStats.map(stat => (
                    <div key={stat.id} className="flex items-center space-x-2 p-2 border rounded-md">
                        <Checkbox 
                            id={`stat-${stat.id}`} 
                            checked={selectedStats.includes(stat.id)}
                            onCheckedChange={(checked) => handleStatToggle(stat.id, !!checked)}
                        />
                        <Label htmlFor={`stat-${stat.id}`} className="text-sm font-normal cursor-pointer">
                            {stat.label}
                        </Label>
                    </div>
                ))}
            </div>
        </div>

        {/* Mock Table Output */}
        <div className="overflow-x-auto border rounded-md">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead>{comparisonType === 'players' ? 'Player' : 'Team'}</TableHead>
                        {selectedStats.map(statId => (
                            <TableHead key={statId} className="text-right">
                                {mockStats.find(s => s.id === statId)?.label || statId}
                            </TableHead>
                        ))}
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {selectedEntities.map(entity => (
                        <TableRow key={entity}>
                            <TableCell className="font-medium">{entity}</TableCell>
                            {selectedStats.map(statId => (
                                <TableCell key={statId} className="text-right">
                                    {/* Mock data value */}
                                    {(Math.random() * (statId.includes('pct') ? 1 : 30)).toFixed(statId.includes('pct') ? 1 : 0)}
                                    {statId.includes('pct') ? '%' : ''}
                                </TableCell>
                            ))}
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </div>

      </CardContent>
       {/* Optional Footer for actions like Export? */}
    </Card>
  );
} 