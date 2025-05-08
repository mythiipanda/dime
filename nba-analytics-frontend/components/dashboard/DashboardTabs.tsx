"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

interface DashboardTabsProps {}

const TabContentPlaceholder = ({ dataType }: { dataType: string }) => {
  return <p className="text-sm text-muted-foreground">{dataType} data goes here...</p>;
};

export function DashboardTabs({}: DashboardTabsProps) {
  return (
    <Tabs defaultValue="trending" className="space-y-4 flex-1 flex flex-col">
      <TabsList>
        <TabsTrigger value="trending">Trending</TabsTrigger>
        <TabsTrigger value="insights">Key Insights</TabsTrigger>
        <TabsTrigger value="favorites">Your Favorites</TabsTrigger>
      </TabsList>

      <TabsContent value="trending" className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[
            { title: "Hot Players", description: "Players with notable recent performances", dataType: "Player" },
            { title: "Team Streaks", description: "Current winning and losing streaks", dataType: "Team streak" },
            { title: "Upcoming Games", description: "Next 24 hours of NBA action", dataType: "Upcoming games" },
          ].map((cardItem, index) => (
          <Card
            key={cardItem.title}
            className={cn(
              "transition-all duration-300 hover:scale-[1.02] hover:shadow-lg",
              // "animate-in fade-in-0 slide-in-from-bottom-4 duration-500" // Entrance animation disabled
            )}
            // style={{ animationDelay: `${index * 100}ms` }} // Animation delay disabled
          >
            <CardHeader>
              <CardTitle>{cardItem.title}</CardTitle>
              <CardDescription>{cardItem.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <TabContentPlaceholder dataType={cardItem.dataType} />
            </CardContent>
          </Card>
          ))}
        </div>
      </TabsContent>

      <TabsContent value="insights" className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          {[
            { title: "Statistical Leaders", description: "Top performers in key categories", dataType: "Stat leaders" },
            { title: "Team Analysis", description: "Performance metrics and trends", dataType: "Team analysis" },
          ].map((cardItem, index) => (
          <Card
            key={cardItem.title}
            className={cn(
              "transition-all duration-300 hover:scale-[1.02] hover:shadow-lg",
              // "animate-in fade-in-0 slide-in-from-bottom-4 duration-500" // Entrance animation disabled
            )}
            // style={{ animationDelay: `${index * 100}ms` }} // Animation delay disabled
          >
            <CardHeader>
              <CardTitle>{cardItem.title}</CardTitle>
              <CardDescription>{cardItem.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <TabContentPlaceholder dataType={cardItem.dataType} />
            </CardContent>
          </Card>
          ))}
        </div>
      </TabsContent>

      <TabsContent value="favorites" className="space-y-4">
        <Card
            className={cn(
              "transition-all duration-300 hover:scale-[1.02] hover:shadow-lg",
              // "animate-in fade-in-0 slide-in-from-bottom-4 duration-500" // Entrance animation disabled
            )}
            // No animationDelay here as it's a single card
        >
          <CardHeader>
            <CardTitle>Your Tracked Items</CardTitle>
            <CardDescription>Players, teams, and stats you follow</CardDescription>
          </CardHeader>
          <CardContent>
            <TabContentPlaceholder dataType="Favorites" />
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  );
} 