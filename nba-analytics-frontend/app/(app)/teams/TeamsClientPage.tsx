"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { TeamStanding } from "@/lib/api/teams"; // Correct path from original file
import { TeamTable } from "@/components/teams/TeamTable"; // Assuming this path is correct
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"; // Using shadcn Select
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"; // Import RadioGroup
import { Label } from "@/components/ui/label"; // Import Label
import { cn } from "@/lib/utils"; // Import cn

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
  const [selectedConference, setSelectedConference] = useState('eastern'); // Add state

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
          {/* Conference Selector (Radio Group styled as Tabs) */}
          <RadioGroup 
            defaultValue="eastern" 
            value={selectedConference} // Control value with state
            onValueChange={setSelectedConference} // Update state on change
            className="flex items-center gap-1 rounded-md bg-muted p-1"
          >
             <RadioGroupItem value="eastern" id="r-east" className="sr-only" />
             <Label 
               htmlFor="r-east" 
               className={cn(
                 "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
                 selectedConference === 'eastern' ? "bg-background text-foreground shadow-sm" : "hover:bg-muted/80"
               )}
             >Eastern</Label>
             <RadioGroupItem value="western" id="r-west" className="sr-only" />
             <Label 
               htmlFor="r-west" 
               className={cn(
                  "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
                 selectedConference === 'western' ? "bg-background text-foreground shadow-sm" : "hover:bg-muted/80"
               )}
              >Western</Label>
          </RadioGroup>
        </div>
      </div>

      {/* Conditionally Rendered Content Area */}
      <div className="mt-4"> {/* Add some margin */}
        {selectedConference === 'eastern' && (
          <TeamTable title="Eastern Conference" teams={initialEasternStandings} />
        )}
        {selectedConference === 'western' && (
          <TeamTable title="Western Conference" teams={initialWesternStandings} />
        )}
      </div>
    </div>
  );
} 