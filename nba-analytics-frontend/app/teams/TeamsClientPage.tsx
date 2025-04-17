"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { TeamStanding } from "@/lib/api/teams"; // Correct path from original file
import { TeamTable, TeamTableSkeleton } from "@/components/teams/TeamTable"; // Assuming this path is correct
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"; // Using shadcn Select

interface TeamsClientPageProps {
  initialEasternStandings: TeamStanding[];
  initialWesternStandings: TeamStanding[];
  currentSeason: string;
}

// Define available seasons (can be fetched or configured elsewhere)
const availableSeasons = ["2024-25", "2023-24", "2022-23", "2021-22", "2020-21", "2019-20", "2018-19", "2017-18", "2016-17",  "2015-16", "2014-15", "2013-14", "2012-13", "2011-12", "2010-11", "2009-10", "2008-09", "2007-08", "2006-07", "2005-06", "2004-05", "2003-04", "2002-03", "2001-02", "2000-01","1999-00"];

export default function TeamsClientPage({
  initialEasternStandings,
  initialWesternStandings,
  currentSeason,
}: TeamsClientPageProps) {
  const router = useRouter();
  const searchParams = useSearchParams(); // Keep using this to potentially read other params if needed

  // State for potentially optimistic updates or if needed later, but primarily rely on props
  // Note: The server component refetch drives the actual data update.
  // This state might not be strictly necessary unless you add optimistic UI updates.
  const [easternStandings, setEasternStandings] = useState(initialEasternStandings);
  const [westernStandings, setWesternStandings] = useState(initialWesternStandings);

  const handleSeasonChange = (newSeason: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("season", newSeason);
    // Navigate to the same page with the new season param, triggering server refetch
    router.push(`/teams?${params.toString()}`);
    // Optionally, show a loading indicator here while navigating/refetching
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex flex-col sm:flex-row items-center justify-between mb-8 gap-4">
        <h1 className="text-3xl font-bold text-center sm:text-left">NBA Standings</h1>
        <div className="flex items-center gap-2">
          <label htmlFor="season-select" className="text-sm font-medium whitespace-nowrap">Select Season:</label>
          <Select
            value={currentSeason}
            onValueChange={handleSeasonChange}
          >
            <SelectTrigger id="season-select" className="w-[180px]">
              <SelectValue placeholder="Select Season" />
            </SelectTrigger>
            <SelectContent>
              {availableSeasons.map((season) => (
                <SelectItem key={season} value={season}>
                  {season}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>


      <Tabs defaultValue="eastern" className="w-full">
        <TabsList className="grid w-full grid-cols-2 mb-6">
          <TabsTrigger value="eastern">Eastern Conference</TabsTrigger>
          <TabsTrigger value="western">Western Conference</TabsTrigger>
        </TabsList>
        <TabsContent value="eastern">
          <Suspense fallback={<TeamTableSkeleton conference="Eastern" />}>
            {/* Render table with props driven by server component */}
            <TeamTable title="Eastern Conference" teams={initialEasternStandings} />
          </Suspense>
        </TabsContent>
        <TabsContent value="western">
          <Suspense fallback={<TeamTableSkeleton conference="Western" />}>
             {/* Render table with props driven by server component */}
            <TeamTable title="Western Conference" teams={initialWesternStandings} />
          </Suspense>
        </TabsContent>
      </Tabs>
    </div>
  );
} 