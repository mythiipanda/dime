import { Button } from "@/components/ui/button";
import { Search, AlertCircle } from "lucide-react";

export function DashboardHeader() {
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-base font-regular text-muted-foreground">
          Your central hub for NBA analytics and insights
        </p>
      </div>
      <div className="flex items-center gap-4">
        {/* TODO: Implement Search Functionality */}
        <Button disabled>
          <Search className="mr-2 h-4 w-4" />
          Quick Search
        </Button>
        {/* TODO: Implement Help Link/Modal */}
        <Button variant="outline" disabled>
          <AlertCircle className="mr-2 h-4 w-4" />
          Help
        </Button>
      </div>
    </div>
  );
} 