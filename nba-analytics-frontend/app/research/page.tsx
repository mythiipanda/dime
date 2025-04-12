"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Search,
  Filter,
  BookOpen,
  TrendingUp,
  BarChart2,
  LineChart,
  Users,
  History,
} from "lucide-react";

export default function ResearchPage() {
  return (
    <div className="container mx-auto py-6 space-y-8">
      {/* Header Section */}
      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Research Hub</h1>
        <p className="text-muted-foreground">
          Analyze NBA data, discover insights, and explore advanced statistics
        </p>
      </div>

      {/* Search Section */}
      <Card className="p-4">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search players, teams, or specific statistics..."
              className="pl-8 w-full"
            />
          </div>
          <Button>
            <Filter className="mr-2 h-4 w-4" />
            Advanced Filters
          </Button>
        </div>
      </Card>

      {/* Main Content */}
      <div className="grid gap-6 md:grid-cols-12">
        {/* Left Sidebar - Quick Tools */}
        <Card className="md:col-span-3 p-4">
          <CardHeader className="px-0 pt-0">
            <CardTitle className="text-lg">Research Tools</CardTitle>
          </CardHeader>
          <CardContent className="px-0 space-y-2">
            <Button variant="ghost" className="w-full justify-start">
              <BookOpen className="mr-2 h-4 w-4" />
              Player Analysis
            </Button>
            <Button variant="ghost" className="w-full justify-start">
              <TrendingUp className="mr-2 h-4 w-4" />
              Team Trends
            </Button>
            <Button variant="ghost" className="w-full justify-start">
              <BarChart2 className="mr-2 h-4 w-4" />
              League Stats
            </Button>
            <Button variant="ghost" className="w-full justify-start">
              <LineChart className="mr-2 h-4 w-4" />
              Advanced Metrics
            </Button>
          </CardContent>
        </Card>

        {/* Main Content Area */}
        <div className="md:col-span-9 space-y-6">
          <Tabs defaultValue="insights" className="w-full">
            <TabsList className="w-full justify-start">
              <TabsTrigger value="insights">Key Insights</TabsTrigger>
              <TabsTrigger value="recent">Recent Research</TabsTrigger>
              <TabsTrigger value="saved">Saved Analysis</TabsTrigger>
            </TabsList>

            <TabsContent value="insights" className="space-y-4 mt-4">
              <div className="grid gap-4 md:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Trending Analysis</CardTitle>
                    <CardDescription>Most viewed research topics</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center gap-4">
                      <Users className="h-8 w-8 text-muted-foreground" />
                      <div>
                        <p className="font-medium">Player Efficiency Ratings</p>
                        <p className="text-sm text-muted-foreground">Updated 2h ago</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <BarChart2 className="h-8 w-8 text-muted-foreground" />
                      <div>
                        <p className="font-medium">Team Defense Analysis</p>
                        <p className="text-sm text-muted-foreground">Updated 4h ago</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Research Highlights</CardTitle>
                    <CardDescription>Notable findings and insights</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[200px] pr-4">
                      {[1, 2, 3, 4].map((i) => (
                        <div key={i} className="mb-4 pb-4 border-b last:border-0">
                          <h4 className="font-medium">Insight {i}</h4>
                          <p className="text-sm text-muted-foreground">
                            Key finding about NBA trends and statistics...
                          </p>
                        </div>
                      ))}
                    </ScrollArea>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="recent" className="space-y-4 mt-4">
              <Card>
                <CardHeader>
                  <CardTitle>Recent Research History</CardTitle>
                  <CardDescription>Your latest analysis and findings</CardDescription>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="h-[300px]">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <div key={i} className="flex items-center gap-4 mb-4 pb-4 border-b last:border-0">
                        <History className="h-5 w-5 text-muted-foreground" />
                        <div>
                          <p className="font-medium">Research Topic {i}</p>
                          <p className="text-sm text-muted-foreground">
                            Brief description of the research...
                          </p>
                        </div>
                      </div>
                    ))}
                  </ScrollArea>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="saved" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle>Saved Analysis</CardTitle>
                  <CardDescription>Your bookmarked research and insights</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground">No saved analysis yet.</p>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
} 