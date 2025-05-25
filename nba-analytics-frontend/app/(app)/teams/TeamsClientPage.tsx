'use client';

import React from 'react';
import { TeamsOverview } from '@/components/teams/TeamsOverview';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AdvancedAnalyticsDashboard } from '@/components/analytics/AdvancedAnalyticsDashboard';
import AIOrchestrationHub from '@/components/charts/AIOrchestrationHub';
import GameIntelligenceDashboard from '@/components/charts/GameIntelligenceDashboard';
import MarketIntelligenceDashboard from '@/components/charts/MarketIntelligenceDashboard';
import { cn } from '@/lib/utils';
import {
  Users,
  Bot,
  Brain,
  Activity,
  Calendar
} from 'lucide-react';

interface TeamsClientPageProps {
  className?: string;
}

export default function TeamsClientPage({ className }: TeamsClientPageProps) {
  const currentSeason = '2024-25';

  return (
    <div className={cn("container mx-auto py-6", className)}>
      <Tabs defaultValue="teams" className="w-full">
        <TabsList className="flex w-full gap-1 p-1 h-auto overflow-x-auto">
          <TabsTrigger value="teams" className="flex-col h-16 text-xs p-1">
            <Users className="w-4 h-4 mb-1" />
            Teams Overview
          </TabsTrigger>
          <TabsTrigger value="intelligence" className="flex-col h-16 text-xs p-1">
            <Calendar className="w-4 h-4 mb-1" />
            Market Intelligence
          </TabsTrigger>
          <TabsTrigger value="advancedAnalytics" className="flex-col h-16 text-xs p-1">
            <Brain className="w-4 h-4 mb-1" />
            Advanced Analytics
          </TabsTrigger>
          <TabsTrigger value="aiHub" className="flex-col h-16 text-xs p-1">
            <Bot className="w-4 h-4 mb-1" />
            AI Hub
          </TabsTrigger>
          <TabsTrigger value="liveData" className="flex-col h-16 text-xs p-1">
            <Activity className="w-4 h-4 mb-1" />
            Live Data
          </TabsTrigger>
        </TabsList>

        <TabsContent value="teams">
          <TeamsOverview />
        </TabsContent>

        <TabsContent value="intelligence" className="space-y-6">
          <MarketIntelligenceDashboard />
        </TabsContent>

        <TabsContent value="advancedAnalytics" className="space-y-6">
          <AdvancedAnalyticsDashboard season={currentSeason} />
        </TabsContent>

        <TabsContent value="aiHub" className="space-y-6">
          <AIOrchestrationHub />
        </TabsContent>

        <TabsContent value="liveData" className="space-y-6">
          <GameIntelligenceDashboard
            gameData={{gameId: '', homeTeam: '', awayTeam: '', quarter: 0, timeRemaining: '', homeScore: 0, awayScore: 0, possession: 'home', shotClock: 0, gameStatus: 'upcoming', broadcast: ''}}
            homePerformances={[]}
            awayPerformances={[]}
            homeMetrics={{team: 'home', teamName: '', fieldGoalPercentage: 0, threePointPercentage: 0, freeThrowPercentage: 0, totalRebounds: 0, assists: 0, turnovers: 0, pace: 0, offensiveRating: 0, defensiveRating: 0, netRating: 0, momentum: 0, energyLevel: 0, chemistry: 0, coaching: 0, winProbability: 0, projectedFinalScore: 0}}
            awayMetrics={{team: 'away', teamName: '', fieldGoalPercentage: 0, threePointPercentage: 0, freeThrowPercentage: 0, totalRebounds: 0, assists: 0, turnovers: 0, pace: 0, offensiveRating: 0, defensiveRating: 0, netRating: 0, momentum: 0, energyLevel: 0, chemistry: 0, coaching: 0, winProbability: 0, projectedFinalScore: 0}}
            aiInsights={[]}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}