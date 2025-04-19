import { getLeagueStandings, TeamStanding } from "@/lib/api/teams";
import TeamsClientPage from "./TeamsClientPage";
import { Metadata } from 'next';

// Add metadata for the page
export const metadata: Metadata = {
  title: 'NBA Team Standings',
  description: 'View the latest NBA team standings by conference and season.',
};

interface TeamsPageProps {
  searchParams: { [key: string]: string | string[] | undefined };
}

// Make the component async to fetch data
export default async function TeamsStandingsPage({ searchParams }: TeamsPageProps) {
  // Default to current year or handle invalid/missing param
  const season = typeof searchParams.season === 'string' ? searchParams.season : "2024-25";

  let easternStandings: TeamStanding[] = [];
  let westernStandings: TeamStanding[] = [];
  

  console.log("Fetching standings for season (Server Component):", season);
  try {
    // Fetch data directly on the server
    const { standings } = await getLeagueStandings(season);

    easternStandings = standings
      .filter((team) => team.Conference === "East")
      .sort((a, b) => a.PlayoffRank - b.PlayoffRank);

    westernStandings = standings
      .filter((team) => team.Conference === "West")
      .sort((a, b) => a.PlayoffRank - b.PlayoffRank);

  } catch (error) {
    console.error("Error fetching standings in Server Component:", error);
    // Set an error message to potentially display to the user
    // The actual error boundary (error.tsx) should handle fatal errors
    fetchError = "Failed to load team standings. Please check connection or try again later.";
    // Optionally, you could return a specific error UI here instead of rendering the client page
    // For now, we'll pass empty arrays and let the client page potentially show a message if needed,
    // or rely on the error.tsx boundary.
  }

  // Render the client component, passing the fetched data as props
  return (
    <TeamsClientPage
      initialEasternStandings={easternStandings}
      initialWesternStandings={westernStandings}
      currentSeason={season}
      // Optionally pass fetchError if the client needs to display it
    />
  );
}