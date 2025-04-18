import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  LineChart,
  TrendingUp,
  Table,
} from "lucide-react";

interface RecentActivityProps {
  isLoading: boolean;
}

// Placeholder for loading/data
const ContentPlaceholder = ({ isLoading, dataType }: { isLoading: boolean; dataType: string }) => {
  if (isLoading) {
    return (
      <>
        <Skeleton className="h-5 w-full mb-2" />
        <Skeleton className="h-5 w-4/5 mb-2" />
        <Skeleton className="h-5 w-full" />
      </>
    );
  }
  return <p className="text-sm text-muted-foreground">{dataType} list goes here...</p>;
};

export function RecentActivity({ isLoading }: RecentActivityProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {/* Recent Queries Card */}
      <Card className="col-span-2">
        <CardHeader>
          <CardTitle>Recent Queries</CardTitle>
          <CardDescription>Your latest NBA analytics questions</CardDescription>
        </CardHeader>
        <CardContent>
          <ContentPlaceholder isLoading={isLoading} dataType="Recent queries" />
        </CardContent>
      </Card>

      {/* Quick Actions Card */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
          <CardDescription>Common analytics tasks</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {/* TODO: Link these buttons to actual functionality */}
          <Button variant="outline" className="w-full justify-start" disabled={isLoading}>
            <LineChart className="mr-2 h-4 w-4" />
            Generate Shot Chart
          </Button>
          <Button variant="outline" className="w-full justify-start" disabled={isLoading}>
            <TrendingUp className="mr-2 h-4 w-4" />
            Compare Players
          </Button>
          <Button variant="outline" className="w-full justify-start" disabled={isLoading}>
            <Table className="mr-2 h-4 w-4" />
            View Box Scores
          </Button>
        </CardContent>
      </Card>
    </div>
  );
} 