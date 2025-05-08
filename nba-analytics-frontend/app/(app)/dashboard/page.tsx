// "use client"; // Removed as this page itself doesn't need client hooks directly

import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { ProTipAlert } from "@/components/dashboard/ProTipAlert";
import { StatsOverview } from "@/components/dashboard/StatsOverview";
import { DashboardTabs } from "@/components/dashboard/DashboardTabs";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { ApiUsageAlert } from "@/components/dashboard/ApiUsageAlert";
import { cn } from "@/lib/utils";

export default function DashboardPage() {
  // isLoading placeholder removed; child components should manage their own loading if data-dependent.

  return (
    <div className={cn(
      "flex flex-col space-y-6 flex-1",
      "animate-in fade-in-0 duration-500" // Overall page entrance
    )}>
      {/* Header spanning full width */}
      <div className="animate-in fade-in-0 slide-in-from-top-3 duration-500 delay-100">
        <DashboardHeader />
      </div>

      {/* Main content area for Tabs - spans full width */}
      <div className="animate-in fade-in-0 slide-in-from-bottom-3 duration-500 delay-200">
        <DashboardTabs />
      </div>
      
      {/* Stats Overview - spans full width */}
      <div className="animate-in fade-in-0 slide-in-from-bottom-3 duration-500 delay-300">
        <StatsOverview />
      </div>

      {/* Pro Tip Alert - spans full width */}
      <div className="animate-in fade-in-0 slide-in-from-bottom-3 duration-500 delay-350">
        <ProTipAlert />
      </div>
      
      {/* Recent Activity and API Usage - in a grid below other content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-in fade-in-0 slide-in-from-bottom-3 duration-500 delay-400">
        <RecentActivity />
        <ApiUsageAlert />
      </div>
    </div>
  );
}