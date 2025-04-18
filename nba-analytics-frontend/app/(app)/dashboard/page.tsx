// "use client"; // Removed as this page itself doesn't need client hooks directly

// Import the new dashboard components
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { ProTipAlert } from "@/components/dashboard/ProTipAlert";
import { StatsOverview } from "@/components/dashboard/StatsOverview";
import { DashboardTabs } from "@/components/dashboard/DashboardTabs";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { ApiUsageAlert } from "@/components/dashboard/ApiUsageAlert";

// Remove unused imports from the original file
// import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
// import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
// import { Button } from "@/components/ui/button";
// import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
// import { Skeleton } from "@/components/ui/skeleton";
// import { ... } from "lucide-react"; // Icons are now within child components

export default function DashboardPage() {
  // This state would ideally come from data fetching logic
  const isLoading = false;

  return (
    <div className="space-y-6">
      <DashboardHeader />
      <ProTipAlert />
      <StatsOverview />
      <DashboardTabs isLoading={isLoading} />
      <RecentActivity isLoading={isLoading} />
      <ApiUsageAlert />
    </div>
  );
}