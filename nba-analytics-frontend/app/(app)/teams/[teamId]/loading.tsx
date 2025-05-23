import { Skeleton } from "@/components/ui/skeleton";

export default function TeamDashboardLoading() {
  return (
    <div className="flex flex-col space-y-6">
      {/* Team Header Skeleton */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Skeleton className="h-16 w-16 rounded-full" />
          <div>
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-32 mt-2" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Skeleton className="h-9 w-28" />
          <Skeleton className="h-9 w-28" />
        </div>
      </div>
      
      {/* Tabs Skeleton */}
      <Skeleton className="h-10 w-full" />
      
      {/* Content Skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array(4).fill(0).map((_, i) => (
          <div key={i} className="border rounded-lg p-4 space-y-3">
            <div className="flex justify-between items-center">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-4" />
            </div>
            <Skeleton className="h-8 w-16" />
            <Skeleton className="h-3 w-20" />
          </div>
        ))}
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="border rounded-lg p-4 space-y-3">
          <Skeleton className="h-6 w-36" />
          <Skeleton className="h-4 w-64" />
          <div className="space-y-6 pt-4">
            {Array(5).fill(0).map((_, i) => (
              <div key={i} className="space-y-2">
                <div className="flex justify-between">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-12" />
                </div>
                <Skeleton className="h-2 w-full" />
              </div>
            ))}
          </div>
        </div>
        
        <div className="border rounded-lg p-4 space-y-3">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-64" />
          <div className="space-y-6 pt-4">
            <div className="space-y-2">
              <Skeleton className="h-4 w-24" />
              <div className="space-y-1 pl-4">
                {Array(4).fill(0).map((_, i) => (
                  <Skeleton key={i} className="h-3 w-full" />
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Skeleton className="h-4 w-24" />
              <div className="space-y-1 pl-4">
                {Array(4).fill(0).map((_, i) => (
                  <Skeleton key={i} className="h-3 w-full" />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div className="border rounded-lg p-4 space-y-3">
        <Skeleton className="h-6 w-28" />
        <Skeleton className="h-4 w-48" />
        <div className="overflow-x-auto">
          <div className="min-w-full">
            <div className="border-b pb-2">
              <div className="grid grid-cols-7 gap-4">
                {Array(7).fill(0).map((_, i) => (
                  <Skeleton key={i} className="h-4 w-full" />
                ))}
              </div>
            </div>
            <div className="space-y-4 pt-2">
              {Array(5).fill(0).map((_, i) => (
                <div key={i} className="grid grid-cols-7 gap-4">
                  {Array(7).fill(0).map((_, j) => (
                    <Skeleton key={j} className="h-4 w-full" />
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 