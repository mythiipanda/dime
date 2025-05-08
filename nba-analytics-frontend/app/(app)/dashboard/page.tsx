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
      // "animate-in fade-in-0 duration-500" // Overall page entrance - Temporarily Disabled
    )}>
      {/* Header spanning full width */}
      <div> {/* Animations Temporarily Disabled */}
        <DashboardHeader />
      </div>

      {/* Main content area for Tabs - spans full width */}
      <div> {/* Animations Temporarily Disabled */}
        <DashboardTabs />
      </div>
      
      {/* Stats Overview - spans full width */}
      <div> {/* Animations Temporarily Disabled */}
        <StatsOverview />
      </div>

      {/* Pro Tip Alert - spans full width */}
      <div> {/* Animations Temporarily Disabled */}
        <ProTipAlert />
      </div>
      
      {/* Recent Activity and API Usage - in a grid below other content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6"> {/* Animations Temporarily Disabled on parent, specific animation classes were on the children's wrappers if any */}
        <RecentActivity />
        <ApiUsageAlert />
      </div>
    </div>
  );
}