import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils"; // Import cn

interface DashboardTabsProps {
  isLoading: boolean;
}

// Placeholder component for tab content loading/data display
const TabContentPlaceholder = ({ isLoading, dataType }: { isLoading: boolean; dataType: string }) => {
  if (isLoading) {
    return (
      <>
        <Skeleton className="h-5 w-4/5 mb-2" />
        <Skeleton className="h-5 w-3/5 mb-2" />
        <Skeleton className="h-5 w-4/5" />
      </>
    );
  }
  return <p className="text-sm text-muted-foreground">{dataType} data goes here...</p>;
};

export function DashboardTabs({ isLoading }: DashboardTabsProps) {
  return (
    // Added flex-1 and flex flex-col to allow Tabs to fill vertical space
    <Tabs defaultValue="trending" className="space-y-4 flex-1 flex flex-col">
      <TabsList> {/* This will remain at the top */}
        <TabsTrigger value="trending">Trending</TabsTrigger>
        <TabsTrigger value="insights">Key Insights</TabsTrigger>
        <TabsTrigger value="favorites">Your Favorites</TabsTrigger>
      </TabsList>

      {/* Trending Tab */}
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
              !isLoading && "animate-in fade-in-0 slide-in-from-bottom-4 duration-500"
            )}
            style={{ animationDelay: !isLoading ? `${index * 100}ms` : undefined }}
          >
            <CardHeader>
              <CardTitle>{cardItem.title}</CardTitle>
              <CardDescription>{cardItem.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <TabContentPlaceholder isLoading={isLoading} dataType={cardItem.dataType} />
            </CardContent>
          </Card>
          ))}
        </div>
      </TabsContent>

      {/* Key Insights Tab */}
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
              !isLoading && "animate-in fade-in-0 slide-in-from-bottom-4 duration-500"
            )}
            style={{ animationDelay: !isLoading ? `${index * 100}ms` : undefined }}
          >
            <CardHeader>
              <CardTitle>{cardItem.title}</CardTitle>
              <CardDescription>{cardItem.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <TabContentPlaceholder isLoading={isLoading} dataType={cardItem.dataType} />
            </CardContent>
          </Card>
          ))}
        </div>
      </TabsContent>

      {/* Your Favorites Tab */}
      <TabsContent value="favorites" className="space-y-4">
        <Card
            className={cn(
              "transition-all duration-300 hover:scale-[1.02] hover:shadow-lg",
              !isLoading && "animate-in fade-in-0 slide-in-from-bottom-4 duration-500"
            )}
            // No index for animationDelay as it's a single card
        >
          <CardHeader>
            <CardTitle>Your Tracked Items</CardTitle>
            <CardDescription>Players, teams, and stats you follow</CardDescription>
          </CardHeader>
          <CardContent>
            <TabContentPlaceholder isLoading={isLoading} dataType="Favorites" />
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  );
} 