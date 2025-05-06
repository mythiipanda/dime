"use client"; // Needed for useMemo

import * as React from "react";
import { useMemo } from "react";
import { PlayerData, CareerOrSeasonStat } from "@/app/(app)/players/types"; // Import from new types file
import {
  Card, CardContent, CardHeader, CardTitle,
} from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ExclamationTriangleIcon } from '@radix-ui/react-icons';

// --- Helper Function to format numbers ---
const formatStat = (value: number | null | undefined, decimals: number = 1): string => {
  if (value === null || value === undefined || isNaN(value)) return '-';
  return value.toFixed(decimals);
};

// --- Small Stat Box Component ---
interface StatBoxProps {
    label: string;
    value: number | null | undefined;
    decimals?: number;
    suffix?: string;
}

function StatBox({ label, value, decimals = 1, suffix = '' }: StatBoxProps) {
    const formattedValue = formatStat(value, decimals);
    return (
        <div className="p-2 rounded-md border bg-muted/50"> {/* Changed rounded to rounded-md */}
            <p className="text-xs text-muted-foreground uppercase tracking-wider">{label}</p>
            <p className="text-xl font-semibold">{formattedValue}{formattedValue !== '-' ? suffix : ''}</p>
        </div>
    )
}

// --- Player Profile Card Component ---
interface PlayerProfileCardProps {
  playerData: PlayerData;
  headshotUrl: string | null;
}

export function PlayerProfileCard({ playerData, headshotUrl }: PlayerProfileCardProps) {
  const info = playerData.player_info;
  const careerRegular = useMemo(() => playerData?.career_totals_regular_season, [playerData]);
  const seasonRegular = useMemo(() => playerData?.season_totals_regular_season, [playerData]);
  const seasonPost = useMemo(() => playerData?.season_totals_post_season, [playerData]);
  const careerPost = useMemo(() => playerData?.career_totals_post_season, [playerData]);

  const sortedRegularSeasons = useMemo(() => {
    if (!seasonRegular) return [];
    return seasonRegular.slice().sort((a: CareerOrSeasonStat, b: CareerOrSeasonStat) => (b.SEASON_ID ?? '').localeCompare(a.SEASON_ID ?? ''));
  }, [seasonRegular]);

  const sortedPostSeasons = useMemo(() => {
    if (!seasonPost) return [];
    return seasonPost.slice().sort((a: CareerOrSeasonStat, b: CareerOrSeasonStat) => (b.SEASON_ID ?? '').localeCompare(a.SEASON_ID ?? ''));
  }, [seasonPost]);

  if (!info) {
      console.error("PlayerProfileCard rendering without player_info.");
      return <Alert variant="destructive">
                  <ExclamationTriangleIcon className="h-4 w-4" />
                  <AlertTitle>Error</AlertTitle>
                  <AlertDescription>Could not load player information.</AlertDescription>
              </Alert>;
  }



  const renderSeasonTable = (seasons: CareerOrSeasonStat[], title: string) => {
    if (!seasons || seasons.length === 0) {
        return <p className="text-muted-foreground text-center py-4">No {title.toLowerCase()} data available.</p>;
    }
    return (
        <div>
            <h3 className="text-lg font-semibold mb-2">{title} by Season</h3>
             <ScrollArea className="h-[300px] w-full rounded-md border">
               <Table className="relative">
                 <TableHeader className="sticky top-0 bg-background z-10">
                   <TableRow>
                     <TableHead>Season</TableHead>
                     <TableHead>Team</TableHead>
                     <TableHead className="text-right">GP</TableHead>
                     <TableHead className="text-right">GS</TableHead>
                     <TableHead className="text-right">MIN</TableHead>
                     <TableHead className="text-right">PTS</TableHead>
                     <TableHead className="text-right">REB</TableHead>
                     <TableHead className="text-right">AST</TableHead>
                     <TableHead className="text-right">STL</TableHead>
                     <TableHead className="text-right">BLK</TableHead>
                     <TableHead className="text-right">FG%</TableHead>
                     <TableHead className="text-right">3P%</TableHead>
                     <TableHead className="text-right">FT%</TableHead>
                   </TableRow>
                 </TableHeader>
                 <TableBody>
                   {seasons.map((season) => (
                     <TableRow key={`${title}-${season.SEASON_ID}-${season.TEAM_ABBREVIATION}`}>
                       <TableCell>{season.SEASON_ID}</TableCell>
                       <TableCell>{season.TEAM_ABBREVIATION || 'N/A'}</TableCell>
                       <TableCell className="text-right">{formatStat(season.GP, 0)}</TableCell>
                       <TableCell className="text-right">{formatStat(season.GS, 0)}</TableCell>
                       <TableCell className="text-right">{formatStat(season.MIN)}</TableCell>
                       <TableCell className="text-right">{formatStat(season.PTS)}</TableCell>
                       <TableCell className="text-right">{formatStat(season.REB)}</TableCell>
                       <TableCell className="text-right">{formatStat(season.AST)}</TableCell>
                       <TableCell className="text-right">{formatStat(season.STL)}</TableCell>
                       <TableCell className="text-right">{formatStat(season.BLK)}</TableCell>
                       <TableCell className="text-right">{formatStat((season.FG_PCT ?? 0) * 100)}%</TableCell>
                       <TableCell className="text-right">{formatStat((season.FG3_PCT ?? 0) * 100)}%</TableCell>
                       <TableCell className="text-right">{formatStat((season.FT_PCT ?? 0) * 100)}%</TableCell>
                     </TableRow>
                   ))}
                 </TableBody>
               </Table>
             </ScrollArea>
           </div>
    );
  };

  return (
    <Card className="mt-4 w-full max-w-4xl mx-auto">
      <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center gap-4 border-b pb-4">
        <Avatar className="h-24 w-24 sm:h-32 sm:w-32 border-2 shadow-sm">
          {headshotUrl ? (
            <AvatarImage src={headshotUrl} alt={info.DISPLAY_FIRST_LAST} className="object-cover"/>
          ) : (
            <AvatarFallback className="text-4xl">
                {info.DISPLAY_FIRST_LAST?.split(' ').map((n: string) => n[0]).join('')}
            </AvatarFallback>
          )}
        </Avatar>
        <div className="flex-1 space-y-1">
          <CardTitle className="text-3xl sm:text-4xl font-bold">{info.DISPLAY_FIRST_LAST}</CardTitle>
           <div className="flex flex-wrap items-center gap-2 text-muted-foreground text-sm sm:text-base">
               {info.POSITION && <Badge variant="secondary">{info.POSITION}</Badge>}
               {info.HEIGHT && <span>{info.HEIGHT}</span>}
               {info.WEIGHT && <span>{info.WEIGHT} lbs</span>}
               {info.JERSEY && <Badge variant="outline">#{info.JERSEY}</Badge>}
               {info.TEAM_ABBREVIATION && <span>{info.TEAM_CITY} {info.TEAM_ABBREVIATION}</span>}
            </div>
             <div className="text-xs sm:text-sm text-muted-foreground space-y-0.5">
               {info.SEASON_EXP !== undefined && <p>Experience: {info.SEASON_EXP} years</p>}
               {info.BIRTHDATE && <p>Born: {new Date(info.BIRTHDATE).toLocaleDateString()} {info.COUNTRY && `(${info.COUNTRY})`}</p>}
               {info.SCHOOL && <p>College: {info.SCHOOL}</p>}
               {(info.FROM_YEAR !== undefined && info.TO_YEAR !== undefined) && <p>Career: {info.FROM_YEAR} - {info.TO_YEAR}</p>}
             </div>
        </div>
      </CardHeader>

      <CardContent className="pt-6 space-y-6">
         <Tabs defaultValue="regular" className="w-full">
            <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="regular">Regular Season</TabsTrigger>
                <TabsTrigger value="postseason">Postseason</TabsTrigger>
            </TabsList>

            {/* Regular Season Content */}
            <TabsContent value="regular" className="space-y-4 pt-4">
                {/* Career Regular Season Averages */}
                {careerRegular && (
                   <div>
                        <h3 className="text-lg font-semibold mb-2">Career Averages</h3>
                        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3 text-center">
                            <StatBox label="GP" value={careerRegular.GP} decimals={0} />
                            <StatBox label="PTS" value={careerRegular.PTS} />
                            <StatBox label="REB" value={careerRegular.REB} />
                            <StatBox label="AST" value={careerRegular.AST} />
                            <StatBox label="FG%" value={(careerRegular.FG_PCT ?? 0) * 100} suffix="%" />
                            <StatBox label="3P%" value={(careerRegular.FG3_PCT ?? 0) * 100} suffix="%" />
                            <StatBox label="FT%" value={(careerRegular.FT_PCT ?? 0) * 100} suffix="%" />
                            <StatBox label="STL" value={careerRegular.STL} />
                            <StatBox label="BLK" value={careerRegular.BLK} />
                            <StatBox label="MIN" value={careerRegular.MIN} />
                        </div>
                   </div>
                )}
                {/* Per-Season Regular Stats Table */}
                {renderSeasonTable(sortedRegularSeasons, "Regular Season Stats")}
            </TabsContent>

            {/* Postseason Content */}
            <TabsContent value="postseason" className="space-y-4 pt-4">
                {/* Career Postseason Averages */}
                {careerPost && (
                   <div>
                        <h3 className="text-lg font-semibold mb-2">Career Averages</h3>
                        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3 text-center">
                            <StatBox label="GP" value={careerPost.GP} decimals={0} />
                            <StatBox label="PTS" value={careerPost.PTS} />
                            <StatBox label="REB" value={careerPost.REB} />
                            <StatBox label="AST" value={careerPost.AST} />
                            <StatBox label="FG%" value={(careerPost.FG_PCT ?? 0) * 100} suffix="%" />
                            <StatBox label="3P%" value={(careerPost.FG3_PCT ?? 0) * 100} suffix="%" />
                            <StatBox label="FT%" value={(careerPost.FT_PCT ?? 0) * 100} suffix="%" />
                            <StatBox label="STL" value={careerPost.STL} />
                            <StatBox label="BLK" value={careerPost.BLK} />
                            <StatBox label="MIN" value={careerPost.MIN} />
                        </div>
                   </div>
                 )}
                {/* Per-Season Postseason Stats Table */}
                 {renderSeasonTable(sortedPostSeasons, "Postseason Stats")}
            </TabsContent>
         </Tabs>

      </CardContent>
    </Card>
  );
} 