import { Metadata } from 'next';
import { notFound } from 'next/navigation';
import TeamDashboardClient from './TeamDashboardClient';

// Force dynamic rendering for this page
export const dynamic = 'force-dynamic';

interface TeamDashboardPageProps {
  params: {
    teamId: string;
  };
  searchParams: { [key: string]: string | string[] | undefined };
}

// Generate metadata for the page
export async function generateMetadata({ params }: TeamDashboardPageProps): Promise<Metadata> {
  // In a real implementation, fetch the team name from an API
  const resolvedParams = await params;
  const teamName = await getTeamName(resolvedParams.teamId);

  return {
    title: `${teamName} Team Dashboard | NBA Analytics`,
    description: `Comprehensive analytics dashboard for ${teamName} with performance metrics, player stats, and AI-powered insights.`,
  };
}

// Fetch team name for metadata (placeholder implementation)
async function getTeamName(teamId: string): Promise<string> {
  // This would be replaced with an actual API call
  const teamNames: Record<string, string> = {
    '1610612737': 'Atlanta Hawks',
    '1610612738': 'Boston Celtics',
    '1610612739': 'Cleveland Cavaliers',
    // Add more teams as needed
  };

  return teamNames[teamId] || 'NBA Team';
}

export default async function TeamDashboardPage({ params, searchParams }: TeamDashboardPageProps) {
  const resolvedParams = await params;
  const resolvedSearchParams = await searchParams;
  const { teamId } = resolvedParams;

  // Default to current season or handle invalid/missing param
  const season = typeof resolvedSearchParams.season === 'string' ? resolvedSearchParams.season : "2024-25";

  // Validate teamId (basic validation)
  if (!teamId || !/^\d+$/.test(teamId)) {
    return notFound();
  }

  // In a production app, you would fetch team data here
  // For now, we'll pass the teamId to the client component

  return (
    <TeamDashboardClient
      teamId={teamId}
      season={season}
    />
  );
}