import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { BarChart3Icon, TrendingUpIcon } from "lucide-react";
import { TeamStatsTab } from "@/components/statistics/TeamStatsTab";
import { PlayerStatsTab } from "@/components/statistics/PlayerStatsTab";
import { GameStatsTab } from "@/components/statistics/GameStatsTab";
import { AdvancedStatsTab } from "@/components/statistics/AdvancedStatsTab";
import { cn } from "@/lib/utils"; // Import cn

export default function StatisticsPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">Statistics</h1>
        <div className="flex gap-2">
          <Button variant="outline" disabled>
            <BarChart3Icon className="w-4 h-4 mr-2" />
            Export Data
          </Button>
          <Button disabled>
            <TrendingUpIcon className="w-4 h-4 mr-2" />
            Generate Report
          </Button>
        </div>
      </div>

      <Tabs defaultValue="team" className="space-y-4">
        <TabsList>
          <TabsTrigger value="team">Team Statistics</TabsTrigger>
          <TabsTrigger value="player">Player Statistics</TabsTrigger>
          <TabsTrigger value="game">Game Statistics</TabsTrigger>
          <TabsTrigger value="advanced">Advanced Metrics</TabsTrigger>
        </TabsList>

        <TabsContent value="team">
          <TeamStatsTab />
        </TabsContent>

        <TabsContent value="player">
          <PlayerStatsTab />
        </TabsContent>

        <TabsContent value="game">
          <GameStatsTab />
        </TabsContent>

        <TabsContent value="advanced">
          <AdvancedStatsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
} 