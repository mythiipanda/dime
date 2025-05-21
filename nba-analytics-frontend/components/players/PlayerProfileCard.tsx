"use client";

import * as React from "react";
import { useMemo } from "react";
import { PlayerData, CareerOrSeasonStat, AdvancedMetrics, SkillGrades } from "@/app/(app)/players/types";
import {
  Card, CardContent, CardHeader,
} from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Tabs, TabsContent, TabsList, TabsTrigger,
} from "@/components/ui/tabs";
import { ExclamationTriangleIcon } from '@radix-ui/react-icons';
import { ShotChartTab } from "@/components/players/ShotChartTab";
import { PlayerHeader } from "./PlayerHeader";
import { SeasonStatsTable } from "./SeasonStatsTable";
import { CareerAverages } from "./CareerAverages";
import { Button } from "@/components/ui/button";
import { AdvancedMetricsDisplay } from "./AdvancedMetricsDisplay";
import { SkillGradesDisplay } from "./SkillGradesDisplay";
import { SimilarPlayersDisplay } from "./SimilarPlayersDisplay";

interface PlayerProfileCardProps {
  playerData: PlayerData;
  headshotUrl: string | null;
  onLoadAdvancedMetrics?: () => void;
}

export function PlayerProfileCard({ 
  playerData, 
  headshotUrl, 
  onLoadAdvancedMetrics,
}: PlayerProfileCardProps) {
  const info = playerData.player_info;
  const careerRegular = useMemo(() => playerData?.career_totals_regular_season, [playerData]);
  const seasonRegular = useMemo(() => playerData?.season_totals_regular_season, [playerData]);
  const seasonPost = useMemo(() => playerData?.season_totals_post_season, [playerData]);
  const careerPost = useMemo(() => playerData?.career_totals_post_season, [playerData]);

  const advancedMetrics = playerData.advanced_metrics;
  const skillGrades = playerData.skill_grades;
  const similarPlayers = playerData.similar_players;

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
    return (
      <Alert variant="destructive">
                  <ExclamationTriangleIcon className="h-4 w-4" />
                  <AlertTitle>Error</AlertTitle>
                  <AlertDescription>Could not load player information.</AlertDescription>
      </Alert>
    );
  }

  return (
    <Card className="mt-4 w-full max-w-4xl mx-auto">
      <CardHeader>
        <PlayerHeader info={info} headshotUrl={headshotUrl} />
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

            <TabsContent value="regular" className="space-y-4 pt-4">
            <CareerAverages careerStats={careerRegular} title="Career Regular Season Averages" />
            <SeasonStatsTable seasons={sortedRegularSeasons} title="Regular Season Stats by Season" />
            </TabsContent>

            <TabsContent value="postseason" className="space-y-4 pt-4">
            <CareerAverages careerStats={careerPost} title="Career Postseason Averages" />
            <SeasonStatsTable seasons={sortedPostSeasons} title="Postseason Stats by Season" />
            </TabsContent>

            <TabsContent value="advanced" className="space-y-4 pt-4">
              <h3 className="text-lg font-semibold mb-2">Advanced Player Metrics</h3>
              {onLoadAdvancedMetrics && !advancedMetrics && (
                <Button onClick={onLoadAdvancedMetrics} variant="outline">
                  Load Advanced Metrics
                </Button>
              )}
              {advancedMetrics ? (
                <AdvancedMetricsDisplay metrics={advancedMetrics} />
              ) : (
                !onLoadAdvancedMetrics && <p className="text-sm text-muted-foreground">Advanced metrics not available or not loaded.</p>
              )}
            </TabsContent>

            <TabsContent value="analysis" className="space-y-4 pt-4">
              <h3 className="text-lg font-semibold mb-2">Player Analysis</h3>
              {onLoadAdvancedMetrics && (!skillGrades || !similarPlayers) && !playerData.skill_grades && !playerData.similar_players && (
                <Button onClick={onLoadAdvancedMetrics} variant="outline" className="mb-4">
                  Load Analysis Data (Skill Grades & Similar Players)
                </Button>
              )}
              {skillGrades && Object.keys(skillGrades).length > 0 && (
                <SkillGradesDisplay grades={skillGrades} />
              )}
              {similarPlayers && similarPlayers.length > 0 && (
                <div className="mt-4">
                  <SimilarPlayersDisplay players={similarPlayers} />
                </div>
              )}
              {(!skillGrades || Object.keys(skillGrades).length === 0) && 
               (!similarPlayers || similarPlayers.length === 0) && 
               (playerData.skill_grades !== undefined || playerData.similar_players !== undefined) && // only show if attempted to load
                 <p className="text-sm text-muted-foreground">Analysis data (skill grades, similar players) not available or not loaded.</p>
              }
            </TabsContent>

            <TabsContent value="shotchart" className="space-y-4 pt-4">
            {info.PERSON_ID && (
                <ShotChartTab playerName={info.DISPLAY_FIRST_LAST} />
            )}
            </TabsContent>
         </Tabs>
      </CardContent>
    </Card>
  );
}