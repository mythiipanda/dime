import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { BarChart3Icon, LineChart, PieChart, TrendingUpIcon } from "lucide-react";

export function TeamStatsTab() {
  // TODO: Replace hardcoded values with fetched data props
  return (
    <div className="space-y-4">
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
            {/* TODO: Replace with actual Chart component */}
            <div className="h-[300px] flex items-center justify-center border-2 border-dashed rounded-lg text-muted-foreground">
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
             {/* TODO: Replace with actual Table component */}
            <div className="h-[300px] flex items-center justify-center border-2 border-dashed rounded-lg text-muted-foreground">
              Rankings Table Placeholder
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
} 