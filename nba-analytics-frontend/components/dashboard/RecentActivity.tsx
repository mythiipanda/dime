"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  LineChart,
  TrendingUp,
  Table,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface RecentActivityProps {}

const ContentPlaceholder = ({ dataType }: { dataType: string }) => {
  return <p className="text-sm text-muted-foreground">{dataType} list goes here...</p>;
};

export function RecentActivity({}: RecentActivityProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      <Card className={cn(
        "col-span-2 transition-all duration-300 hover:scale-[1.02] hover:shadow-lg",
        "animate-in fade-in-0 slide-in-from-bottom-4 duration-500"
      )} style={{ animationDelay: `0ms` }}>
        <CardHeader>
          <CardTitle>Recent Queries</CardTitle>
          <CardDescription>Your latest NBA analytics questions</CardDescription>
        </CardHeader>
        <CardContent>
          <ContentPlaceholder dataType="Recent queries" />
        </CardContent>
      </Card>

      <Card className={cn(
        "transition-all duration-300 hover:scale-[1.02] hover:shadow-lg",
        "animate-in fade-in-0 slide-in-from-bottom-4 duration-500"
      )} style={{ animationDelay: `100ms` }}>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
          <CardDescription>Common analytics tasks</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col space-y-2">
          <Button variant="outline" className="w-full justify-start text-left h-auto whitespace-normal py-2">
            <LineChart className="mr-2 h-4 w-4 flex-shrink-0" />
            <span>Generate Shot Chart</span>
          </Button>
          <Button variant="outline" className="w-full justify-start text-left h-auto whitespace-normal py-2">
            <TrendingUp className="mr-2 h-4 w-4 flex-shrink-0" />
            <span>Compare Players</span>
          </Button>
          <Button variant="outline" className="w-full justify-start text-left h-auto whitespace-normal py-2">
            <Table className="mr-2 h-4 w-4 flex-shrink-0" />
            <span>View Box Scores</span>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
} 