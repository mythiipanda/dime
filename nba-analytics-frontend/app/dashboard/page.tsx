"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  BarChart2,
  TrendingUp,
  Users,
  Trophy,
  Calendar,
  Search,
  LineChart,
  Table,
  AlertCircle,
} from "lucide-react";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-base font-regular text-muted-foreground">
            Your central hub for NBA analytics and insights
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Button>
            <Search className="mr-2 h-4 w-4" />
            Quick Search
          </Button>
          <Button variant="outline">
            <AlertCircle className="mr-2 h-4 w-4" />
            Help
          </Button>
        </div>
      </div>

      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Pro Tip</AlertTitle>
        <AlertDescription>
          Use natural language to ask questions about any NBA player, team, or game. Our AI will help you find the insights you need.
        </AlertDescription>
      </Alert>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-regular">Total Players Analyzed</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">450+</div>
            <p className="text-sm font-regular text-muted-foreground">Active NBA players</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-regular">Games Tracked</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">1,230</div>
            <p className="text-sm font-regular text-muted-foreground">2023-24 season</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-regular">Teams Covered</CardTitle>
            <Trophy className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">30</div>
            <p className="text-sm font-regular text-muted-foreground">All NBA teams</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-regular">Data Points</CardTitle>
            <BarChart2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">1M+</div>
            <p className="text-sm font-regular text-muted-foreground">Statistical entries</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="trending" className="space-y-4">
        <TabsList>
          <TabsTrigger value="trending">Trending</TabsTrigger>
          <TabsTrigger value="insights">Key Insights</TabsTrigger>
          <TabsTrigger value="favorites">Your Favorites</TabsTrigger>
        </TabsList>
        <TabsContent value="trending" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle>Hot Players</CardTitle>
                <CardDescription>Players with notable recent performances</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {/* Add player list here */}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Team Streaks</CardTitle>
                <CardDescription>Current winning and losing streaks</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {/* Add team streaks here */}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Upcoming Games</CardTitle>
                <CardDescription>Next 24 hours of NBA action</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {/* Add upcoming games here */}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
        <TabsContent value="insights" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Statistical Leaders</CardTitle>
                <CardDescription>Top performers in key categories</CardDescription>
              </CardHeader>
              <CardContent>
                {/* Add statistical leaders here */}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Team Analysis</CardTitle>
                <CardDescription>Performance metrics and trends</CardDescription>
              </CardHeader>
              <CardContent>
                {/* Add team analysis here */}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
        <TabsContent value="favorites" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Your Tracked Items</CardTitle>
              <CardDescription>Players, teams, and stats you follow</CardDescription>
            </CardHeader>
            <CardContent>
              {/* Add favorites content here */}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card className="col-span-2">
          <CardHeader>
            <CardTitle>Recent Queries</CardTitle>
            <CardDescription>Your latest NBA analytics questions</CardDescription>
          </CardHeader>
          <CardContent>
            {/* Add recent queries list here */}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Common analytics tasks</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button variant="outline" className="w-full justify-start">
              <LineChart className="mr-2 h-4 w-4" />
              Generate Shot Chart
            </Button>
            <Button variant="outline" className="w-full justify-start">
              <TrendingUp className="mr-2 h-4 w-4" />
              Compare Players
            </Button>
            <Button variant="outline" className="w-full justify-start">
              <Table className="mr-2 h-4 w-4" />
              View Box Scores
            </Button>
          </CardContent>
        </Card>
      </div>

      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Heads up!</AlertTitle>
        <AlertDescription>
          NBA API usage limits may apply. Monitor your requests.
        </AlertDescription>
      </Alert>

    </div>
  );
}