import { Metadata } from 'next';
import TeamsClientPage from "./TeamsClientPage";

// Force dynamic rendering for this page
export const dynamic = 'force-dynamic';

// Add metadata for the page
export const metadata: Metadata = {
  title: 'NBA Teams',
  description: 'Browse and analyze all 30 NBA teams.',
};

interface TeamsPageProps {
  searchParams: { [key: string]: string | string[] | undefined };
}

// Make the component async to fetch data
export default async function TeamsIndexPage({ searchParams }: TeamsPageProps) {
  // Default to current season or handle invalid/missing param
  const resolvedSearchParams = await searchParams;
  const season = typeof resolvedSearchParams.season === 'string' ? resolvedSearchParams.season : "2024-25";

  console.log("Fetching teams for season (Server Component):", season);

  // We'll pass the season to the client component
  // In a real implementation, we could fetch additional data here if needed
  return (
    <TeamsClientPage
      currentSeason={season}
    />
  );
}