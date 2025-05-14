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
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ExclamationTriangleIcon } from '@radix-ui/react-icons';
import { ShotChartTab } from "@/components/players/ShotChartTab";

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
        <div className="p-2 rounded-md border bg-muted/50">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">{label}</p>
            <p className="text-xl font-semibold">{formattedValue}{formattedValue !== '-' ? suffix : ''}</p>
        </div>
    )
}

// --- Player Profile Card Component ---
interface PlayerProfileCardProps {
  playerData: PlayerData;
  headshotUrl: string | null;
  onLoadAdvancedMetrics?: () => void;
}

export function PlayerProfileCard({ playerData, headshotUrl, onLoadAdvancedMetrics }: PlayerProfileCardProps) {
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
            <TabsList className="grid w-full grid-cols-5">
                <TabsTrigger value="regular">Regular Season</TabsTrigger>
                <TabsTrigger value="postseason">Postseason</TabsTrigger>
                <TabsTrigger value="advanced">Advanced</TabsTrigger>
                <TabsTrigger value="analysis">Analysis</TabsTrigger>
                <TabsTrigger value="shotchart">Shot Charts</TabsTrigger>
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

            {/* Advanced Metrics Content */}
            <TabsContent value="advanced" className="space-y-4 pt-4">
                {playerData.advanced_metrics ? (
                    <div>
                        <h3 className="text-lg font-semibold mb-2">Advanced Metrics</h3>
                        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                            <div className="p-4 rounded-lg border bg-card shadow-sm">
                                <h4 className="text-md font-medium mb-2">RAPTOR Rating</h4>
                                <div className="grid grid-cols-3 gap-2">
                                    <StatBox
                                        label="TOTAL"
                                        value={
                                            playerData.advanced_metrics?.RAPTOR_TOTAL !== undefined ? playerData.advanced_metrics.RAPTOR_TOTAL :
                                            playerData.advanced_metrics?.RAPTOR !== undefined ? playerData.advanced_metrics.RAPTOR :
                                            null
                                        }
                                    />
                                    <StatBox
                                        label="OFF"
                                        value={
                                            playerData.advanced_metrics?.RAPTOR_OFFENSE !== undefined ? playerData.advanced_metrics.RAPTOR_OFFENSE :
                                            playerData.advanced_metrics?.RAPTOR_OFF !== undefined ? playerData.advanced_metrics.RAPTOR_OFF :
                                            null
                                        }
                                    />
                                    <StatBox
                                        label="DEF"
                                        value={
                                            playerData.advanced_metrics?.RAPTOR_DEFENSE !== undefined ? playerData.advanced_metrics.RAPTOR_DEFENSE :
                                            playerData.advanced_metrics?.RAPTOR_DEF !== undefined ? playerData.advanced_metrics.RAPTOR_DEF :
                                            null
                                        }
                                    />
                                </div>
                                <p className="text-xs text-muted-foreground mt-2">Source: NBA Analytics (RAPTOR-style)</p>
                            </div>

                            <div className="p-4 rounded-lg border bg-card shadow-sm">
                                <h4 className="text-md font-medium mb-2">ELO Rating</h4>
                                <div className="grid grid-cols-3 gap-2">
                                    <StatBox label="TOTAL" value={playerData.advanced_metrics.ELO_RATING} decimals={0} />
                                    <StatBox label="CURRENT" value={playerData.advanced_metrics.ELO_CURRENT} decimals={0} />
                                    <StatBox label="LEGACY" value={playerData.advanced_metrics.ELO_HISTORICAL} decimals={0} />
                                </div>
                                <p className="text-xs text-muted-foreground mt-2">Source: NBA Analytics (1500 = Average)</p>
                                <p className="text-xs text-muted-foreground">Factors in career achievements & longevity</p>
                            </div>

                            <div className="p-4 rounded-lg border bg-card shadow-sm">
                                <h4 className="text-md font-medium mb-2">Wins Above Replacement</h4>
                                <div className="grid grid-cols-1 gap-2">
                                    <StatBox
                                        label="WAR"
                                        value={
                                            playerData.advanced_metrics?.WAR !== undefined ? playerData.advanced_metrics.WAR :
                                            playerData.advanced_metrics?.PLAYER_VALUE !== undefined ? playerData.advanced_metrics.PLAYER_VALUE :
                                            null
                                        }
                                    />
                                </div>
                                <p className="text-xs text-muted-foreground mt-2">Source: NBA Analytics (RAPTOR-style)</p>
                            </div>

                            <div className="p-4 rounded-lg border bg-card shadow-sm">
                                <h4 className="text-md font-medium mb-2">Efficiency</h4>
                                <div className="grid grid-cols-2 gap-2">
                                    <StatBox label="ORTG" value={playerData.advanced_metrics.ORTG} decimals={1} />
                                    <StatBox label="DRTG" value={playerData.advanced_metrics.DRTG} decimals={1} />
                                </div>
                                <p className="text-xs text-muted-foreground mt-2">Source: NBA Stats</p>
                            </div>
                        </div>

                        <div className="mt-6">
                            <h3 className="text-lg font-semibold mb-2">Traditional Advanced Metrics</h3>
                            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3 text-center">
                                <StatBox label="PER" value={playerData.advanced_metrics.PER} />
                                <StatBox label="TS%" value={playerData.advanced_metrics.TS_PCT} suffix="%" />
                                <StatBox label="USG%" value={playerData.advanced_metrics.USG_PCT} suffix="%" />
                                <StatBox label="PIE" value={playerData.advanced_metrics.PIE ? playerData.advanced_metrics.PIE * 100 : null} suffix="%" />
                                <StatBox label="VORP" value={playerData.advanced_metrics.VORP} />
                                <StatBox label="WS" value={playerData.advanced_metrics.WS} />
                                <StatBox label="NET RTG" value={playerData.advanced_metrics.NETRTG} />
                                <StatBox label="AST%" value={playerData.advanced_metrics.AST_PCT} suffix="%" />
                                <StatBox label="REB%" value={playerData.advanced_metrics.REB_PCT} suffix="%" />
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center py-12">
                        <p className="text-muted-foreground text-center mb-4">Advanced metrics not loaded yet.</p>
                        {onLoadAdvancedMetrics && (
                            <Button
                                onClick={onLoadAdvancedMetrics}
                                className="mb-4"
                            >
                                Load Advanced Metrics
                            </Button>
                        )}
                        <p className="text-sm text-muted-foreground mt-2">Data sources: NBA Stats, NBA Analytics</p>
                    </div>
                )}
            </TabsContent>

            {/* Player Analysis Content */}
            <TabsContent value="analysis" className="space-y-4 pt-4">
                {playerData.skill_grades ? (
                    <div>
                        <h3 className="text-lg font-semibold mb-2">Skill Assessment</h3>
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                            <div className="p-3 rounded-lg border bg-card">
                                <p className="text-sm font-medium">Perimeter Shooting</p>
                                <div className="flex items-center mt-1">
                                    <div className={`text-lg font-bold w-8 h-8 rounded-full flex items-center justify-center
                                        ${playerData.skill_grades?.perimeter_shooting?.startsWith('A+') ? 'bg-green-200 text-green-800' :
                                          playerData.skill_grades?.perimeter_shooting?.startsWith('A') ? 'bg-green-100 text-green-700' :
                                          playerData.skill_grades?.perimeter_shooting?.startsWith('B') ? 'bg-green-50 text-green-600' :
                                          playerData.skill_grades?.perimeter_shooting?.startsWith('C') ? 'bg-yellow-50 text-yellow-600' :
                                          playerData.skill_grades?.perimeter_shooting?.startsWith('D') ? 'bg-orange-50 text-orange-600' :
                                          'bg-red-50 text-red-600'}`}>
                                        {playerData.skill_grades?.perimeter_shooting || 'C'}
                                    </div>
                                    <div className="ml-2 flex-1 h-2 bg-muted rounded-full overflow-hidden">
                                        <div className={`h-full ${
                                            playerData.skill_grades?.perimeter_shooting?.startsWith('A+') ? 'bg-green-600 w-[95%]' :
                                            playerData.skill_grades?.perimeter_shooting?.startsWith('A-') ? 'bg-green-500 w-[85%]' :
                                            playerData.skill_grades?.perimeter_shooting?.startsWith('A') ? 'bg-green-500 w-[90%]' :
                                            playerData.skill_grades?.perimeter_shooting?.startsWith('B+') ? 'bg-green-400 w-[80%]' :
                                            playerData.skill_grades?.perimeter_shooting?.startsWith('B-') ? 'bg-green-400 w-[70%]' :
                                            playerData.skill_grades?.perimeter_shooting?.startsWith('B') ? 'bg-green-400 w-[75%]' :
                                            playerData.skill_grades?.perimeter_shooting?.startsWith('C+') ? 'bg-yellow-400 w-[65%]' :
                                            playerData.skill_grades?.perimeter_shooting?.startsWith('C-') ? 'bg-yellow-400 w-[55%]' :
                                            playerData.skill_grades?.perimeter_shooting?.startsWith('C') ? 'bg-yellow-400 w-[60%]' :
                                            playerData.skill_grades?.perimeter_shooting?.startsWith('D+') ? 'bg-orange-400 w-[50%]' :
                                            playerData.skill_grades?.perimeter_shooting?.startsWith('D-') ? 'bg-orange-400 w-[30%]' :
                                            playerData.skill_grades?.perimeter_shooting?.startsWith('D') ? 'bg-orange-400 w-[40%]' :
                                            'bg-red-400 w-[20%]'
                                        }`}></div>
                                    </div>
                                </div>
                            </div>

                            <div className="p-3 rounded-lg border bg-card">
                                <p className="text-sm font-medium">Interior Scoring</p>
                                <div className="flex items-center mt-1">
                                    <div className={`text-lg font-bold w-8 h-8 rounded-full flex items-center justify-center
                                        ${playerData.skill_grades?.interior_scoring?.startsWith('A+') ? 'bg-green-200 text-green-800' :
                                          playerData.skill_grades?.interior_scoring?.startsWith('A') ? 'bg-green-100 text-green-700' :
                                          playerData.skill_grades?.interior_scoring?.startsWith('B') ? 'bg-green-50 text-green-600' :
                                          playerData.skill_grades?.interior_scoring?.startsWith('C') ? 'bg-yellow-50 text-yellow-600' :
                                          playerData.skill_grades?.interior_scoring?.startsWith('D') ? 'bg-orange-50 text-orange-600' :
                                          'bg-red-50 text-red-600'}`}>
                                        {playerData.skill_grades?.interior_scoring || 'C'}
                                    </div>
                                    <div className="ml-2 flex-1 h-2 bg-muted rounded-full overflow-hidden">
                                        <div className={`h-full ${
                                            playerData.skill_grades?.interior_scoring?.startsWith('A+') ? 'bg-green-600 w-[95%]' :
                                            playerData.skill_grades?.interior_scoring?.startsWith('A-') ? 'bg-green-500 w-[85%]' :
                                            playerData.skill_grades?.interior_scoring?.startsWith('A') ? 'bg-green-500 w-[90%]' :
                                            playerData.skill_grades?.interior_scoring?.startsWith('B+') ? 'bg-green-400 w-[80%]' :
                                            playerData.skill_grades?.interior_scoring?.startsWith('B-') ? 'bg-green-400 w-[70%]' :
                                            playerData.skill_grades?.interior_scoring?.startsWith('B') ? 'bg-green-400 w-[75%]' :
                                            playerData.skill_grades?.interior_scoring?.startsWith('C+') ? 'bg-yellow-400 w-[65%]' :
                                            playerData.skill_grades?.interior_scoring?.startsWith('C-') ? 'bg-yellow-400 w-[55%]' :
                                            playerData.skill_grades?.interior_scoring?.startsWith('C') ? 'bg-yellow-400 w-[60%]' :
                                            playerData.skill_grades?.interior_scoring?.startsWith('D+') ? 'bg-orange-400 w-[50%]' :
                                            playerData.skill_grades?.interior_scoring?.startsWith('D-') ? 'bg-orange-400 w-[30%]' :
                                            playerData.skill_grades?.interior_scoring?.startsWith('D') ? 'bg-orange-400 w-[40%]' :
                                            'bg-red-400 w-[20%]'
                                        }`}></div>
                                    </div>
                                </div>
                            </div>

                            <div className="p-3 rounded-lg border bg-card">
                                <p className="text-sm font-medium">Playmaking</p>
                                <div className="flex items-center mt-1">
                                    <div className={`text-lg font-bold w-8 h-8 rounded-full flex items-center justify-center
                                        ${playerData.skill_grades?.playmaking?.startsWith('A+') ? 'bg-green-200 text-green-800' :
                                          playerData.skill_grades?.playmaking?.startsWith('A') ? 'bg-green-100 text-green-700' :
                                          playerData.skill_grades?.playmaking?.startsWith('B') ? 'bg-green-50 text-green-600' :
                                          playerData.skill_grades?.playmaking?.startsWith('C') ? 'bg-yellow-50 text-yellow-600' :
                                          playerData.skill_grades?.playmaking?.startsWith('D') ? 'bg-orange-50 text-orange-600' :
                                          'bg-red-50 text-red-600'}`}>
                                        {playerData.skill_grades?.playmaking || 'C'}
                                    </div>
                                    <div className="ml-2 flex-1 h-2 bg-muted rounded-full overflow-hidden">
                                        <div className={`h-full ${
                                            playerData.skill_grades?.playmaking?.startsWith('A+') ? 'bg-green-600 w-[95%]' :
                                            playerData.skill_grades?.playmaking?.startsWith('A-') ? 'bg-green-500 w-[85%]' :
                                            playerData.skill_grades?.playmaking?.startsWith('A') ? 'bg-green-500 w-[90%]' :
                                            playerData.skill_grades?.playmaking?.startsWith('B+') ? 'bg-green-400 w-[80%]' :
                                            playerData.skill_grades?.playmaking?.startsWith('B-') ? 'bg-green-400 w-[70%]' :
                                            playerData.skill_grades?.playmaking?.startsWith('B') ? 'bg-green-400 w-[75%]' :
                                            playerData.skill_grades?.playmaking?.startsWith('C+') ? 'bg-yellow-400 w-[65%]' :
                                            playerData.skill_grades?.playmaking?.startsWith('C-') ? 'bg-yellow-400 w-[55%]' :
                                            playerData.skill_grades?.playmaking?.startsWith('C') ? 'bg-yellow-400 w-[60%]' :
                                            playerData.skill_grades?.playmaking?.startsWith('D+') ? 'bg-orange-400 w-[50%]' :
                                            playerData.skill_grades?.playmaking?.startsWith('D-') ? 'bg-orange-400 w-[30%]' :
                                            playerData.skill_grades?.playmaking?.startsWith('D') ? 'bg-orange-400 w-[40%]' :
                                            'bg-red-400 w-[20%]'
                                        }`}></div>
                                    </div>
                                </div>
                            </div>

                            <div className="p-3 rounded-lg border bg-card">
                                <p className="text-sm font-medium">Perimeter Defense</p>
                                <div className="flex items-center mt-1">
                                    <div className={`text-lg font-bold w-8 h-8 rounded-full flex items-center justify-center
                                        ${playerData.skill_grades?.perimeter_defense?.startsWith('A+') ? 'bg-green-200 text-green-800' :
                                          playerData.skill_grades?.perimeter_defense?.startsWith('A') ? 'bg-green-100 text-green-700' :
                                          playerData.skill_grades?.perimeter_defense?.startsWith('B') ? 'bg-green-50 text-green-600' :
                                          playerData.skill_grades?.perimeter_defense?.startsWith('C') ? 'bg-yellow-50 text-yellow-600' :
                                          playerData.skill_grades?.perimeter_defense?.startsWith('D') ? 'bg-orange-50 text-orange-600' :
                                          'bg-red-50 text-red-600'}`}>
                                        {playerData.skill_grades?.perimeter_defense || 'C'}
                                    </div>
                                    <div className="ml-2 flex-1 h-2 bg-muted rounded-full overflow-hidden">
                                        <div className={`h-full ${
                                            playerData.skill_grades?.perimeter_defense?.startsWith('A+') ? 'bg-green-600 w-[95%]' :
                                            playerData.skill_grades?.perimeter_defense?.startsWith('A-') ? 'bg-green-500 w-[85%]' :
                                            playerData.skill_grades?.perimeter_defense?.startsWith('A') ? 'bg-green-500 w-[90%]' :
                                            playerData.skill_grades?.perimeter_defense?.startsWith('B+') ? 'bg-green-400 w-[80%]' :
                                            playerData.skill_grades?.perimeter_defense?.startsWith('B-') ? 'bg-green-400 w-[70%]' :
                                            playerData.skill_grades?.perimeter_defense?.startsWith('B') ? 'bg-green-400 w-[75%]' :
                                            playerData.skill_grades?.perimeter_defense?.startsWith('C+') ? 'bg-yellow-400 w-[65%]' :
                                            playerData.skill_grades?.perimeter_defense?.startsWith('C-') ? 'bg-yellow-400 w-[55%]' :
                                            playerData.skill_grades?.perimeter_defense?.startsWith('C') ? 'bg-yellow-400 w-[60%]' :
                                            playerData.skill_grades?.perimeter_defense?.startsWith('D+') ? 'bg-orange-400 w-[50%]' :
                                            playerData.skill_grades?.perimeter_defense?.startsWith('D-') ? 'bg-orange-400 w-[30%]' :
                                            playerData.skill_grades?.perimeter_defense?.startsWith('D') ? 'bg-orange-400 w-[40%]' :
                                            'bg-red-400 w-[20%]'
                                        }`}></div>
                                    </div>
                                </div>
                            </div>

                            <div className="p-3 rounded-lg border bg-card">
                                <p className="text-sm font-medium">Interior Defense</p>
                                <div className="flex items-center mt-1">
                                    <div className={`text-lg font-bold w-8 h-8 rounded-full flex items-center justify-center
                                        ${playerData.skill_grades?.interior_defense?.startsWith('A+') ? 'bg-green-200 text-green-800' :
                                          playerData.skill_grades?.interior_defense?.startsWith('A') ? 'bg-green-100 text-green-700' :
                                          playerData.skill_grades?.interior_defense?.startsWith('B') ? 'bg-green-50 text-green-600' :
                                          playerData.skill_grades?.interior_defense?.startsWith('C') ? 'bg-yellow-50 text-yellow-600' :
                                          playerData.skill_grades?.interior_defense?.startsWith('D') ? 'bg-orange-50 text-orange-600' :
                                          'bg-red-50 text-red-600'}`}>
                                        {playerData.skill_grades?.interior_defense || 'C'}
                                    </div>
                                    <div className="ml-2 flex-1 h-2 bg-muted rounded-full overflow-hidden">
                                        <div className={`h-full ${
                                            playerData.skill_grades?.interior_defense?.startsWith('A+') ? 'bg-green-600 w-[95%]' :
                                            playerData.skill_grades?.interior_defense?.startsWith('A-') ? 'bg-green-500 w-[85%]' :
                                            playerData.skill_grades?.interior_defense?.startsWith('A') ? 'bg-green-500 w-[90%]' :
                                            playerData.skill_grades?.interior_defense?.startsWith('B+') ? 'bg-green-400 w-[80%]' :
                                            playerData.skill_grades?.interior_defense?.startsWith('B-') ? 'bg-green-400 w-[70%]' :
                                            playerData.skill_grades?.interior_defense?.startsWith('B') ? 'bg-green-400 w-[75%]' :
                                            playerData.skill_grades?.interior_defense?.startsWith('C+') ? 'bg-yellow-400 w-[65%]' :
                                            playerData.skill_grades?.interior_defense?.startsWith('C-') ? 'bg-yellow-400 w-[55%]' :
                                            playerData.skill_grades?.interior_defense?.startsWith('C') ? 'bg-yellow-400 w-[60%]' :
                                            playerData.skill_grades?.interior_defense?.startsWith('D+') ? 'bg-orange-400 w-[50%]' :
                                            playerData.skill_grades?.interior_defense?.startsWith('D-') ? 'bg-orange-400 w-[30%]' :
                                            playerData.skill_grades?.interior_defense?.startsWith('D') ? 'bg-orange-400 w-[40%]' :
                                            'bg-red-400 w-[20%]'
                                        }`}></div>
                                    </div>
                                </div>
                            </div>

                            <div className="p-3 rounded-lg border bg-card">
                                <p className="text-sm font-medium">Rebounding</p>
                                <div className="flex items-center mt-1">
                                    <div className={`text-lg font-bold w-8 h-8 rounded-full flex items-center justify-center
                                        ${playerData.skill_grades?.rebounding?.startsWith('A+') ? 'bg-green-200 text-green-800' :
                                          playerData.skill_grades?.rebounding?.startsWith('A') ? 'bg-green-100 text-green-700' :
                                          playerData.skill_grades?.rebounding?.startsWith('B') ? 'bg-green-50 text-green-600' :
                                          playerData.skill_grades?.rebounding?.startsWith('C') ? 'bg-yellow-50 text-yellow-600' :
                                          playerData.skill_grades?.rebounding?.startsWith('D') ? 'bg-orange-50 text-orange-600' :
                                          'bg-red-50 text-red-600'}`}>
                                        {playerData.skill_grades?.rebounding || 'C'}
                                    </div>
                                    <div className="ml-2 flex-1 h-2 bg-muted rounded-full overflow-hidden">
                                        <div className={`h-full ${
                                            playerData.skill_grades?.rebounding?.startsWith('A+') ? 'bg-green-600 w-[95%]' :
                                            playerData.skill_grades?.rebounding?.startsWith('A-') ? 'bg-green-500 w-[85%]' :
                                            playerData.skill_grades?.rebounding?.startsWith('A') ? 'bg-green-500 w-[90%]' :
                                            playerData.skill_grades?.rebounding?.startsWith('B+') ? 'bg-green-400 w-[80%]' :
                                            playerData.skill_grades?.rebounding?.startsWith('B-') ? 'bg-green-400 w-[70%]' :
                                            playerData.skill_grades?.rebounding?.startsWith('B') ? 'bg-green-400 w-[75%]' :
                                            playerData.skill_grades?.rebounding?.startsWith('C+') ? 'bg-yellow-400 w-[65%]' :
                                            playerData.skill_grades?.rebounding?.startsWith('C-') ? 'bg-yellow-400 w-[55%]' :
                                            playerData.skill_grades?.rebounding?.startsWith('C') ? 'bg-yellow-400 w-[60%]' :
                                            playerData.skill_grades?.rebounding?.startsWith('D+') ? 'bg-orange-400 w-[50%]' :
                                            playerData.skill_grades?.rebounding?.startsWith('D-') ? 'bg-orange-400 w-[30%]' :
                                            playerData.skill_grades?.rebounding?.startsWith('D') ? 'bg-orange-400 w-[40%]' :
                                            'bg-red-400 w-[20%]'
                                        }`}></div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {playerData.similar_players && playerData.similar_players.length > 0 && (
                            <div className="mt-6">
                                <h3 className="text-lg font-semibold mb-2">Similar Players</h3>
                                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                                    {playerData.similar_players.map((player, index) => (
                                        <div key={player.player_id} className="p-3 rounded-lg border bg-card flex items-center">
                                            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold">
                                                {index + 1}
                                            </div>
                                            <div className="ml-3">
                                                <p className="font-medium">{player.player_name}</p>
                                                <p className="text-sm text-muted-foreground">
                                                    Similarity: {(player.similarity_score * 100).toFixed(1)}%
                                                </p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center py-12">
                        <p className="text-muted-foreground text-center">Player analysis not available.</p>
                    </div>
                )}
            </TabsContent>

            {/* Shot Charts Content */}
            <TabsContent value="shotchart" className="space-y-4 pt-4">
                <ShotChartTab playerName={info.DISPLAY_FIRST_LAST} />
            </TabsContent>
         </Tabs>

      </CardContent>
    </Card>
  );
}