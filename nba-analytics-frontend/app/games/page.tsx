"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { CalendarIcon, ClockIcon, TrendingUpIcon } from "lucide-react";

export default function GamesPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">Games</h1>
        <div className="flex gap-2">
          <Button variant="outline">
            <CalendarIcon className="w-4 h-4 mr-2" />
            Calendar View
          </Button>
          <Button>
            <TrendingUpIcon className="w-4 h-4 mr-2" />
            Live Games
          </Button>
        </div>
      </div>

      <Tabs defaultValue="schedule" className="space-y-4">
        <TabsList>
          <TabsTrigger value="schedule">Schedule</TabsTrigger>
          <TabsTrigger value="live">Live Games</TabsTrigger>
          <TabsTrigger value="completed">Completed</TabsTrigger>
          <TabsTrigger value="analysis">Analysis</TabsTrigger>
        </TabsList>

        <TabsContent value="schedule" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {/* Game Cards - Will be populated with real data */}
            {[1, 2, 3].map((game) => (
              <Card key={game}>
                <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                  <CardTitle className="text-sm font-medium">Upcoming Game {game}</CardTitle>
                  <ClockIcon className="w-4 h-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="flex justify-between items-center py-4">
                    <div className="text-center">
                      <div className="font-bold">Team A</div>
                      <div className="text-sm text-muted-foreground">Home</div>
                    </div>
                    <div className="text-xl font-bold">VS</div>
                    <div className="text-center">
                      <div className="font-bold">Team B</div>
                      <div className="text-sm text-muted-foreground">Away</div>
                    </div>
                  </div>
                  <div className="text-sm text-center text-muted-foreground">
                    <CalendarIcon className="inline-block w-4 h-4 mr-1" />
                    March 15, 2024 - 7:30 PM EST
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="live" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Live Games Dashboard</CardTitle>
              <CardDescription>
                Real-time scores and statistics
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-4">
                  <div className="h-[200px] flex items-center justify-center border-2 border-dashed rounded-lg">
                    Live Score Board Placeholder
                  </div>
                  <div className="h-[200px] flex items-center justify-center border-2 border-dashed rounded-lg">
                    Live Statistics Placeholder
                  </div>
                </div>
                <div className="h-[416px] flex items-center justify-center border-2 border-dashed rounded-lg">
                  Live Game Feed Placeholder
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="completed" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Completed Games</CardTitle>
              <CardDescription>
                Recent game results and highlights
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[400px] flex items-center justify-center border-2 border-dashed rounded-lg">
                Completed Games List Placeholder
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="analysis" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Game Predictions</CardTitle>
                <CardDescription>
                  AI-powered game predictions and analysis
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-[300px] flex items-center justify-center border-2 border-dashed rounded-lg">
                  Predictions Dashboard Placeholder
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Historical Analysis</CardTitle>
                <CardDescription>
                  Team matchup history and trends
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-[300px] flex items-center justify-center border-2 border-dashed rounded-lg">
                  Historical Analysis Dashboard Placeholder
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}