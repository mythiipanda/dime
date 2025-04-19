'use client';

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

import { ScrollText, BarChart2, Percent } from "lucide-react";

export default function GameAnalysisViewer() {
  // Mock data
  const mockGame = {
      id: "0022300001",
      date: "2023-10-24",
      homeTeam: "Nuggets",
      awayTeam: "Lakers",
      homeScore: 119,
      awayScore: 107,
      boxScore: [
          { player: "Nikola Jokic", pts: 29, reb: 13, ast: 11 },
          { player: "LeBron James", pts: 21, reb: 8, ast: 5 },
          // Add more mock box score entries
      ],
      playByPlayHighlights: [
          "Q1 08:30 - Jokic makes layup (Assist: Murray)",
          "Q2 05:15 - LeBron James blocks Porter Jr.",
          "Q3 02:00 - Murray hits 3-pointer",
          "Q4 01:00 - Davis makes free throw",
      ],
      winProbability: [
          { time: "Q1 00:00", homeProb: 55 },
          { time: "Q2 00:00", homeProb: 60 },
          { time: "Q3 00:00", homeProb: 75 },
          { time: "Q4 00:00", homeProb: 90 },
      ]
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center">
          <ScrollText className="mr-2 h-5 w-5" />
          Game Analysis Viewer (Mock)
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex flex-col sm:flex-row gap-4 items-end">
            <div className="flex-1 space-y-2">
                <Label htmlFor="game-id-input">Game ID</Label>
                <Input id="game-id-input" placeholder="Enter Game ID (e.g., 0022300001)" defaultValue={mockGame.id} />
            </div>
            <Button disabled>Load Game Data</Button>
        </div>

        {/* Mock Game Info Display */}
        <Card>
          <CardHeader>
            <CardTitle className="text-center text-xl">
                {mockGame.awayTeam} @ {mockGame.homeTeam} - {mockGame.date}
            </CardTitle>
            <div className="text-center text-3xl font-bold mt-2">
                <span>{mockGame.awayScore}</span>
                <span className="mx-4 text-muted-foreground">-</span>
                <span>{mockGame.homeScore}</span>
            </div>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4">
             {/* Box Score Snippet */}
            <div>
                <h4 className="font-semibold mb-2 flex items-center"><BarChart2 className="mr-1 h-4 w-4"/> Box Score</h4>
                <div className="text-sm border rounded-md p-2 max-h-40 overflow-y-auto scrollbar-thin">
                    {mockGame.boxScore.map(p => (
                        <div key={p.player}>{p.player}: {p.pts} PTS, {p.reb} REB, {p.ast} AST</div>
                    ))}
                    <div className="mt-1 text-muted-foreground">... more players</div>
                </div>
            </div>
             {/* Play-by-Play Highlights */}
             <div>
                <h4 className="font-semibold mb-2 flex items-center"><ScrollText className="mr-1 h-4 w-4"/> Highlights</h4>
                <div className="text-sm border rounded-md p-2 max-h-40 overflow-y-auto scrollbar-thin">
                    {mockGame.playByPlayHighlights.map((play, i) => (
                        <div key={i}>{play}</div>
                    ))}
                </div>
             </div>
            {/* Win Probability Snippet */}
            <div>
                <h4 className="font-semibold mb-2 flex items-center"><Percent className="mr-1 h-4 w-4"/> Win % ({mockGame.homeTeam})</h4>
                 <div className="text-sm border rounded-md p-2 max-h-40 overflow-y-auto scrollbar-thin">
                    {mockGame.winProbability.map((wp) => (
                        <div key={wp.time}>{wp.time}: {wp.homeProb}%</div>
                    ))}
                </div>
            </div>
          </CardContent>
        </Card>

      </CardContent>
    </Card>
  );
} 