import { Suspense } from "react";
// Fetch raw standings data instead of transformed team stats
import { getLeagueStandings, TeamStanding } from "@/lib/api/teams"; 
import { TeamTable, TeamTableSkeleton } from "@/components/teams/TeamTable";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface PageProps {
  searchParams?: { [key: string]: string | string[] | undefined };
}

export const revalidate = 0; // Disable cache to ensure fresh data
export const dynamic = 'force-dynamic'; // Explicitly mark as dynamic

export default async function TeamsStandingsPage({ searchParams }: PageProps) {
  const season = typeof searchParams?.season === 'string' ? searchParams.season : "2024-25";
  console.log("Fetching standings for season:", season);

  try {
    const { standings } = await getLeagueStandings(season);

    const easternStandings: TeamStanding[] = standings
      .filter((team) => team.Conference === "East")
      .sort((a, b) => a.PlayoffRank - b.PlayoffRank);
      
    const westernStandings: TeamStanding[] = standings
      .filter((team) => team.Conference === "West")
      .sort((a, b) => a.PlayoffRank - b.PlayoffRank);

    return (
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-8 text-center">NBA Standings ({season})</h1>
        
        <Tabs defaultValue="eastern" className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-6">
            <TabsTrigger value="eastern">Eastern Conference</TabsTrigger>
            <TabsTrigger value="western">Western Conference</TabsTrigger>
          </TabsList>
          <TabsContent value="eastern">
             <Suspense fallback={<TeamTableSkeleton conference="Eastern" />}>
               <TeamTable title="Eastern Conference" teams={easternStandings} />
             </Suspense>
          </TabsContent>
          <TabsContent value="western">
             <Suspense fallback={<TeamTableSkeleton conference="Western" />}>
                <TeamTable title="Western Conference" teams={westernStandings} />
             </Suspense>
          </TabsContent>
        </Tabs>
        
      </div>
    );
  } catch (error) {
    console.error("Error rendering TeamsStandingsPage:", error);
    // Re-throw a user-friendly error for the error boundary
    throw new Error("Failed to load team standings. Please check connection or try again later.");
  }
}