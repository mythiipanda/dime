import { Metadata } from 'next';
import { PlayerData, Suggestion } from "./types"; // Corrected import
import { API_BASE_URL } from "@/lib/config";
import PlayersClientPage from "./PlayersClientPage";
import { PlayerProfileCard } from "@/components/players/PlayerProfileCard"; // Keep this import for type usage below

// --- Server-side Data Fetching Functions ---

// Function to fetch player profile data (mimics client-side logic but on server)
async function fetchPlayerData(playerName: string): Promise<{ data: PlayerData | null, error: string | null }> {
  console.log(`Fetching server-side profile for: ${playerName}`);
  const profileUrl = `${API_BASE_URL}/players/profile?player_name=${encodeURIComponent(playerName)}`;
  try {
    const profileResponse = await fetch(profileUrl, { cache: 'no-store' }); // Consider caching strategy

    if (!profileResponse.ok) {
      const errorData = await profileResponse.json().catch(() => ({ detail: `HTTP error ${profileResponse.status}` }));
      console.error(`Server Profile fetch failed (${profileResponse.status}):`, errorData);
      return { data: null, error: errorData.detail || `Failed to fetch player profile (${profileResponse.status})` };
    }

    const rawData = await profileResponse.json();
    if (!rawData || !rawData.player_info) {
        console.error("Server Validation Failed - Missing player_info.");
        return { data: null, error: "Incomplete profile data received."};
    }

    // Map rawData to PlayerData structure (adjust if backend structure differs)
    const mappedData: PlayerData = {
        player_info: rawData.player_info,
        career_totals_regular_season: rawData.career_totals?.regular_season ?? null,
        season_totals_regular_season: rawData.season_totals?.regular_season ?? null,
        career_totals_post_season: rawData.career_totals?.post_season ?? null,
        season_totals_post_season: rawData.season_totals?.post_season ?? null,
        career_highs: rawData.career_highs ?? null,
    };
    return { data: mappedData, error: null };

  } catch (err: unknown) {
    console.error("Server Fetch Error (fetchPlayerData):", err);
    return { data: null, error: err instanceof Error ? err.message : "An unknown error occurred."};
  }
}

// Function to fetch headshot URL
async function fetchHeadshotUrl(playerId: number): Promise<string | null> {
    const headshotUrlPath = `${API_BASE_URL}/players/player/${playerId}/headshot`;
    console.log(`Fetching server-side headshot from: ${headshotUrlPath}`);
    try {
        const headshotResponse = await fetch(headshotUrlPath, { cache: 'no-store' }); // Consider caching
        if (!headshotResponse.ok) {
            console.warn(`Server Headshot fetch failed (${headshotResponse.status})`);
            return null;
        } else {
            const headshotData = await headshotResponse.json();
            return headshotData?.headshot_url || null;
        }
    } catch (headshotErr) {
        console.warn("Server Headshot Fetch Error:", headshotErr);
        return null;
    }
}


// --- Page Component (Server Component) ---

export const metadata: Metadata = {
  title: 'NBA Player Analytics',
  description: 'Search and view detailed statistics for NBA players.',
};

interface PlayersPageProps {
  searchParams: { [key: string]: string | string[] | undefined };
}

export default async function PlayersPage({ searchParams }: PlayersPageProps) {
  const searchTerm = typeof searchParams.query === 'string' ? searchParams.query : null;

  let playerData: PlayerData | null = null;
  let headshotUrl: string | null = null;
  let serverFetchError: string | null = null;

  if (searchTerm) {
    const { data, error } = await fetchPlayerData(searchTerm);
    if (error) {
      serverFetchError = error;
    } else if (data && data.player_info) {
      playerData = data;
      // Fetch headshot only if player data was successful
      headshotUrl = await fetchHeadshotUrl(data.player_info.PERSON_ID);
    }
  }

  // Render the Client Component, passing server-fetched data or nulls
  return (
    <PlayersClientPage
      initialSearchTerm={searchTerm}
      initialPlayerData={playerData}
      initialHeadshotUrl={headshotUrl}
      serverFetchError={serverFetchError}
    />
  );
}

// --- Export necessary types/components IF they were NOT moved ---
// (We moved them, so these exports are commented out or removed)
/*
export { PlayerProfileCard }; // Export if kept here
export type { PlayerData, Suggestion }; // Export types if kept here
*/