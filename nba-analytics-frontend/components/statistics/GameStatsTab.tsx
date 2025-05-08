"use client"; // Added 'use client'

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { cn } from "@/lib/utils"; // Import cn

export function GameStatsTab() {
  return (
    <div className="space-y-4">
      <Card className={cn(
        "transition-all duration-300 hover:scale-[1.02] hover:shadow-md",
        "animate-in fade-in-0 slide-in-from-bottom-4 duration-500" // Entrance animation
      )}>
        <CardHeader>
          <CardTitle>Game Statistics Analysis</CardTitle>
          <CardDescription>
            Detailed game-by-game statistics and trends
          </CardDescription>
        </CardHeader>
        <CardContent>
           {/* TODO: Replace with actual Game Stats components/charts/tables */}
          <div className="h-[400px] flex items-center justify-center border-2 border-dashed rounded-lg text-muted-foreground">
            Game Statistics Analysis Placeholder
          </div>
        </CardContent>
      </Card>
    </div>
  );
} 