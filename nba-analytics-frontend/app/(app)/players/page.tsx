import { Metadata } from 'next';
import { PlayerData } from "./types"; // Use this imported type
import { API_BASE_URL } from "@/lib/config";
import PlayersClientPage from "./PlayersClientPage";

// --- Server-Side Data Fetching ---

// Update function signature to use imported PlayerData type
async function fetchPlayerData(playerName: string): Promise<{ data: PlayerData | null, error: string | null }> {
  console.log(`Fetching server-side profile for: ${playerName}`);
  const profileUrl = `${API_BASE_URL}/player/profile?player_name=${encodeURIComponent(playerName)}`; // Corrected: /player instead of /players
  try {
    const profileResponse = await fetch(profileUrl, { cache: 'no-store' }); // Consider caching strategy

    if (!profileResponse.ok) {
      const errorData = await profileResponse.json().catch(() => ({ detail: `HTTP error ${profileResponse.status}` }));
      console.error(`Server Profile fetch failed (${profileResponse.status}):`, errorData);
      return { data: null, error: errorData.detail || `Failed to fetch player profile (${profileResponse.status})` };
    }

    const rawData = await profileResponse.json();
    // Log the raw data structure to help with debugging
    console.log("Raw player profile data structure:", {
      has_player_id: !!rawData.player_id,
      player_id_type: typeof rawData.player_id,
      player_id_value: rawData.player_id,
      has_player_info: !!rawData.player_info,
      has_player_name: !!rawData.player_name
    });

    // Basic validation - ensure player_info exists
    if (!rawData || !rawData.player_info) {
        console.error("Server Validation Failed - Missing player_info.");
        return { data: null, error: "Incomplete profile data received."};
    }

    // Validate player_id exists
    if (!rawData.player_id) {
        console.error("Server Validation Failed - Missing player_id.");
        return { data: null, error: "Incomplete profile data received: missing player_id."};
    }

    // Map rawData to imported PlayerData structure
    // Explicitly type mappedData with the imported PlayerData type
    const mappedData: PlayerData = {
        player_id: rawData.player_id, // Include player_id from the backend
        player_name: rawData.player_name, // Include player_name from the backend
        player_info: rawData.player_info, // Assumes rawData.player_info matches PlayerInfo type
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
    // Validate playerId
    if (!playerId) {
        console.error(`Invalid player ID for headshot: ${playerId}`);
        return null;
    }

    const headshotUrlPath = `${API_BASE_URL}/player/${playerId}/headshot`; // Corrected: /player instead of /players/player
    console.log(`Fetching server-side headshot from: ${headshotUrlPath}`);
    try {
        const headshotResponse = await fetch(headshotUrlPath, { cache: 'no-store' }); // Consider caching
        if (!headshotResponse.ok) {
            console.warn(`Server Headshot fetch failed (${headshotResponse.status})`);
            return null;
        } else {
            const headshotData = await headshotResponse.json();
            console.log("Headshot data received:", headshotData);
            return headshotData?.headshot_url || null;
        }
    } catch (headshotErr) {
        console.warn("Server Headshot Fetch Error:", headshotErr);
        return null;
    }
}

// --- Page Component (Server) ---

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

  // Fetch initial data if search term exists
  if (searchTerm) {
    console.log("[Server Page] Processing search term:", searchTerm);
    const { data, error } = await fetchPlayerData(searchTerm);
    if (error) {
      console.error("[Server Page] Error fetching player data:", error);
      serverFetchError = error;
    } else if (data && data.player_info) {
      console.log("[Server Page] Player data fetched successfully for:", data.player_info.DISPLAY_FIRST_LAST);
      playerData = data;
      // Use player_id from the top level of the response
      headshotUrl = await fetchHeadshotUrl(data.player_id);
      if (headshotUrl) {
        console.log("[Server Page] Headshot fetched successfully.");
      } else {
        console.warn("[Server Page] Headshot could not be fetched.");
      }
    } else {
      console.warn("[Server Page] No player data or error returned from fetchPlayerData");
      // Optionally set an error if data is null but no specific error was thrown
      serverFetchError = serverFetchError || "Player data not found or incomplete.";
    }
  } else {
     console.log("[Server Page] No search term provided.");
  }

  // Render the Client Component, passing down initial server-fetched state
  return (
    <PlayersClientPage
      initialSearchTerm={searchTerm}
      initialPlayerData={playerData}
      initialHeadshotUrl={headshotUrl}
      serverFetchError={serverFetchError}
    />
  );
}