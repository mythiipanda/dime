import { getTeamsByConference } from "@/lib/api/teams";
import { TeamsContent } from "@/components/teams/TeamsContent";
import { Suspense } from "react";
import { PageProps } from "./types";

export const revalidate = 0; // Disable cache to ensure fresh data

export default async function TeamsPage({ searchParams = {} }: PageProps) {
  // Get season from search params
  const season = typeof searchParams.season === 'string' ? searchParams.season : "2024-25";

  try {
    const { eastern, western } = await getTeamsByConference(season);

    return (
      <div className="flex-1 space-y-4 p-4 md:p-8 pt-6">
        <Suspense fallback={<div>Loading teams...</div>}>
          <TeamsContent eastern={eastern} western={western} />
        </Suspense>
      </div>
    );
  } catch {
    // This error will be caught by the error boundary
    throw new Error("Failed to load team data. Please try again later.");
  }
}