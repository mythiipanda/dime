"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { BarChart3Icon, LineChart, PieChart, TrendingUpIcon } from "lucide-react";

export default function StatisticsPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">Statistics</h1>
        <div className="flex gap-2">
          <Button variant="outline">
            <BarChart3Icon className="w-4 h-4 mr-2" />
            Export Data
          </Button>
          <Button>
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

        <TabsContent value="team" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-sm font-medium">Offensive Rating</CardTitle>
                <BarChart3Icon className="w-4 h-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">114.5</div>
                <p className="text-xs text-muted-foreground">League Average</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-sm font-medium">Defensive Rating</CardTitle>
                <LineChart className="w-4 h-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">112.8</div>
                <p className="text-xs text-muted-foreground">League Average</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-sm font-medium">Pace</CardTitle>
                <TrendingUpIcon className="w-4 h-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">98.8</div>
                <p className="text-xs text-muted-foreground">League Average</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-sm font-medium">Net Rating</CardTitle>
                <PieChart className="w-4 h-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">+1.7</div>
                <p className="text-xs text-muted-foreground">League Average</p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Card className="col-span-1">
              <CardHeader>
                <CardTitle>Team Performance Comparison</CardTitle>
                <CardDescription>
                  Compare key metrics across teams
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-[300px] flex items-center justify-center border-2 border-dashed rounded-lg">
                  Team Comparison Chart Placeholder
                </div>
              </CardContent>
            </Card>

            <Card className="col-span-1">
              <CardHeader>
                <CardTitle>League Rankings</CardTitle>
                <CardDescription>
                  Team rankings by various metrics
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-[300px] flex items-center justify-center border-2 border-dashed rounded-lg">
                  Rankings Table Placeholder
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="player" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Player Statistics Dashboard</CardTitle>
              <CardDescription>
                Detailed player statistics and comparisons
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[400px] flex items-center justify-center border-2 border-dashed rounded-lg">
                Player Statistics Dashboard Placeholder
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="game" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Game Statistics Analysis</CardTitle>
              <CardDescription>
                Detailed game-by-game statistics and trends
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[400px] flex items-center justify-center border-2 border-dashed rounded-lg">
                Game Statistics Analysis Placeholder
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="advanced" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Advanced Analytics</CardTitle>
              <CardDescription>
                Deep dive into advanced basketball metrics
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[400px] flex items-center justify-center border-2 border-dashed rounded-lg">
                Advanced Analytics Dashboard Placeholder
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
} 