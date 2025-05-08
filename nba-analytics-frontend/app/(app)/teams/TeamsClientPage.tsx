"use client";

// import { useState } from "react"; // No longer needed for selectedConference
import { useRouter, useSearchParams } from "next/navigation";
import { TeamStanding } from "@/lib/api/teams";
import { TeamTable } from "@/components/teams/TeamTable";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"; // Import Tabs components
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"; // Import Alert components
import { AlertCircle } from "lucide-react"; // Icon for error alert

interface TeamsClientPageProps {
  initialEasternStandings: TeamStanding[];
  initialWesternStandings: TeamStanding[];
  currentSeason: string;
  fetchError: string | null; // Add fetchError prop
}

// Define available seasons (can be fetched or configured elsewhere)
const availableSeasons = ["2024-25", "2023-24", "2022-23", "2021-22", "2020-21", "2019-20", "2018-19", "2017-18", "2016-17",  "2015-16", "2014-15", "2013-14", "2012-13", "2011-12", "2010-11", "2009-10", "2008-09", "2007-08", "2006-07", "2005-06", "2004-05", "2003-04", "2002-03", "2001-02", "2000-01","1999-00"];

export default function TeamsClientPage({
  initialEasternStandings,
  initialWesternStandings,
  currentSeason,
  fetchError, // Receive fetchError
}: TeamsClientPageProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  // const [selectedConference, setSelectedConference] = useState('eastern'); // Removed state

  const handleSeasonChange = (newSeason: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("season", newSeason);
    // Navigate to the same page with the new season param, triggering server refetch
    router.push(`/teams?${params.toString()}`);
    // Optionally, show a loading indicator here while navigating/refetching
  };

  return (
    <div className="container mx-auto px-4 py-8 space-y-6"> {/* Add spacing */}
      {/* Combined Header/Controls Area */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <h1 className="text-3xl font-bold text-center sm:text-left">NBA Standings</h1>
        {/* Controls Wrapper */}
        <div className="flex flex-wrap items-center justify-center sm:justify-end gap-4">
          {/* Season Selector */}
          <div className="flex items-center gap-2">
            <Label htmlFor="season-select" className="text-sm font-medium">Season:</Label>
            <Select value={currentSeason} onValueChange={handleSeasonChange}>
              <SelectTrigger id="season-select" className="w-[180px]">
                <SelectValue placeholder="Select Season" />
              </SelectTrigger>
              <SelectContent>
                {availableSeasons.map((season) => (
                  <SelectItem key={season} value={season}>{season}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {/* Conference Selector Removed */}
        </div>
      </div>

      {fetchError && (
        <Alert variant="destructive" className="my-4">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>
            {fetchError}
          </AlertDescription>
        </Alert>
      )}

      {/* Conference Tabs */}
      <Tabs defaultValue="eastern" className="w-full mt-2"> {/* Removed animation from Tabs for focusing on centering */}
        <div className="flex justify-center mb-4"> {/* Parent for centering */}
          {/* Changed TabsList to be inline-grid for shrink-wrapping and centering */}
          <TabsList className="inline-grid grid-cols-2 gap-2 p-1 rounded-lg bg-muted"> {/* Added common shadcn styling for TabsList too */}
            <TabsTrigger value="eastern" className="data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm px-3 py-1.5">Eastern Conference</TabsTrigger>
            <TabsTrigger value="western" className="data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm px-3 py-1.5">Western Conference</TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="eastern">
          <TeamTable title="Eastern Conference" teams={initialEasternStandings} />
        </TabsContent>
        <TabsContent value="western">
          <TeamTable title="Western Conference" teams={initialWesternStandings} />
        </TabsContent>
      </Tabs>
    </div>
  );
}