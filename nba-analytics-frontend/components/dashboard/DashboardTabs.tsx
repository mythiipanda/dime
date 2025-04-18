import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";

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
    <Tabs defaultValue="trending" className="space-y-4">
      <TabsList>
        <TabsTrigger value="trending">Trending</TabsTrigger>
        <TabsTrigger value="insights">Key Insights</TabsTrigger>
        <TabsTrigger value="favorites">Your Favorites</TabsTrigger>
      </TabsList>

      {/* Trending Tab */}
      <TabsContent value="trending" className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>Hot Players</CardTitle>
              <CardDescription>Players with notable recent performances</CardDescription>
            </CardHeader>
            <CardContent>
              <TabContentPlaceholder isLoading={isLoading} dataType="Player" />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Team Streaks</CardTitle>
              <CardDescription>Current winning and losing streaks</CardDescription>
            </CardHeader>
            <CardContent>
              <TabContentPlaceholder isLoading={isLoading} dataType="Team streak" />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Upcoming Games</CardTitle>
              <CardDescription>Next 24 hours of NBA action</CardDescription>
            </CardHeader>
            <CardContent>
              <TabContentPlaceholder isLoading={isLoading} dataType="Upcoming games" />
            </CardContent>
          </Card>
        </div>
      </TabsContent>

      {/* Key Insights Tab */}
      <TabsContent value="insights" className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Statistical Leaders</CardTitle>
              <CardDescription>Top performers in key categories</CardDescription>
            </CardHeader>
            <CardContent>
              <TabContentPlaceholder isLoading={isLoading} dataType="Stat leaders" />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Team Analysis</CardTitle>
              <CardDescription>Performance metrics and trends</CardDescription>
            </CardHeader>
            <CardContent>
              <TabContentPlaceholder isLoading={isLoading} dataType="Team analysis" />
            </CardContent>
          </Card>
        </div>
      </TabsContent>

      {/* Your Favorites Tab */}
      <TabsContent value="favorites" className="space-y-4">
        <Card>
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