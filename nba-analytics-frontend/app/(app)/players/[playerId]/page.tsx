import { Suspense } from 'react';
import { notFound } from 'next/navigation';
import PlayerProfileClient from './PlayerProfileClient';
import { Skeleton } from "@/components/ui/skeleton";

interface PlayerProfilePageProps {
  params: {
    playerId: string;
  };
  searchParams: {
    season?: string;
    tab?: string;
  };
}

// Generate metadata for the page
export async function generateMetadata({ params }: PlayerProfilePageProps) {
  const resolvedParams = await params;
  const { playerId } = resolvedParams;

  // In a real app, you might fetch player data here for metadata
  return {
    title: `Player Profile - NBA Analytics`,
    description: `Comprehensive statistics and analysis for NBA player ${playerId}`,
  };
}

export default async function PlayerProfilePage({ params, searchParams }: PlayerProfilePageProps) {
  const resolvedParams = await params;
  const resolvedSearchParams = await searchParams;
  const { playerId } = resolvedParams;

  // Default to current season or handle invalid/missing param
  const season = typeof resolvedSearchParams.season === 'string' ? resolvedSearchParams.season : "2024-25";
  const activeTab = typeof resolvedSearchParams.tab === 'string' ? resolvedSearchParams.tab : "overview";

  // Validate playerId (basic validation)
  if (!playerId || !/^\d+$/.test(playerId)) {
    return notFound();
  }

  return (
    <Suspense fallback={<PlayerProfileSkeleton />}>
      <PlayerProfileClient
        playerId={playerId}
        season={season}
        initialTab={activeTab}
      />
    </Suspense>
  );
}

function PlayerProfileSkeleton() {
  return (
    <div className="container mx-auto px-4 py-8 space-y-6">
      {/* Header Skeleton */}
      <div className="flex items-center gap-6">
        <div className="w-24 h-24 bg-gray-200 rounded-full animate-pulse" />
        <div className="space-y-2">
          <div className="h-8 w-64 bg-gray-200 rounded animate-pulse" />
          <div className="h-4 w-48 bg-gray-200 rounded animate-pulse" />
          <div className="h-4 w-32 bg-gray-200 rounded animate-pulse" />
        </div>
      </div>

      {/* Stats Cards Skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="border rounded-lg p-4 space-y-3 animate-pulse">
            <div className="h-4 w-20 bg-gray-200 rounded" />
            <div className="h-8 w-16 bg-gray-200 rounded" />
            <div className="h-3 w-24 bg-gray-200 rounded" />
          </div>
        ))}
      </div>

      {/* Tabs Skeleton */}
      <div className="h-10 w-full bg-gray-200 rounded animate-pulse" />

      {/* Content Skeleton */}
      <div className="space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="border rounded-lg p-6 space-y-4 animate-pulse">
            <div className="h-6 w-32 bg-gray-200 rounded" />
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex justify-between">
                  <div className="h-4 w-24 bg-gray-200 rounded" />
                  <div className="h-4 w-16 bg-gray-200 rounded" />
                </div>
              ))}
            </div>
          </div>

          <div className="border rounded-lg p-6 space-y-4 animate-pulse">
            <div className="h-6 w-40 bg-gray-200 rounded" />
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="space-y-2">
                  <div className="flex justify-between">
                    <div className="h-4 w-20 bg-gray-200 rounded" />
                    <div className="h-4 w-12 bg-gray-200 rounded" />
                  </div>
                  <div className="h-2 w-full bg-gray-200 rounded" />
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Chart Skeleton */}
        <div className="border rounded-lg p-6 space-y-4 animate-pulse">
          <div className="h-6 w-48 bg-gray-200 rounded" />
          <div className="h-64 w-full bg-gray-200 rounded" />
        </div>
      </div>
    </div>
  );
}
