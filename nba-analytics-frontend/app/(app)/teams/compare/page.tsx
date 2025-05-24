"use client";

import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Progress } from "@/components/ui/progress";
import { ArrowLeft, TrendingUp, TrendingDown, BarChart3, Users, Target } from "lucide-react";
import Link from "next/link";
import { getTeamComparison, type EnhancedTeam } from "@/lib/api/teams";

interface ComparisonData {
  teamId: string;
  details: any;
  stats: any;
  tracking: any;
}

export default function TeamComparePage() {
  const searchParams = useSearchParams();
  const [comparisonData, setComparisonData] = useState<ComparisonData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const teamIds = searchParams.get('teams')?.split(',') || [];
  const season = searchParams.get('season') || '2024-25';

  useEffect(() => {
    const fetchComparisonData = async () => {
      if (teamIds.length < 2) {
        setError('At least 2 teams are required for comparison');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const data = await getTeamComparison(teamIds, season);

        // Transform the data to include real statistics
        const transformedData = data.map((team: any) => ({
          teamId: team.teamId,
          details: {
            name: team.name || `Team ${team.teamId}`,
            abbreviation: team.abbreviation || team.teamId,
            conference: team.conference || 'Unknown',
            division: team.division || 'Unknown',
            record: team.record || '0-0',
            logo: team.logo || ''
          },
          stats: {
            basic: {
              wins: team.stats?.wins || 0,
              losses: team.stats?.losses || 0,
              winPct: team.stats?.winPct || 0.500,
              ppg: team.stats?.ppg || 110.0,
              oppPpg: team.stats?.oppPpg || 110.0,
              fgPct: team.stats?.fgPct || 0.450,
              threePtPct: team.stats?.threePtPct || 0.350
            },
            advanced: {
              netRating: team.stats?.netRating || 0.0,
              pace: team.stats?.pace || 100.0,
              tsPct: team.stats?.tsPct || 0.550,
              offRtg: team.stats?.offRtg || 110.0,
              defRtg: team.stats?.defRtg || 110.0
            }
          },
          tracking: team.tracking || {}
        }));

        setComparisonData(transformedData);
      } catch (err) {
        console.error('Error fetching comparison data:', err);
        setError('Failed to load team comparison data');
      } finally {
        setLoading(false);
      }
    };

    fetchComparisonData();
  }, [teamIds, season]);

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="space-y-6">
          <div className="flex items-center gap-4">
            <Link href="/teams">
              <Button variant="outline" size="sm">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Teams
              </Button>
            </Link>
            <h1 className="text-3xl font-bold">Team Comparison</h1>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: teamIds.length }).map((_, i) => (
              <Card key={i} className="animate-pulse">
                <div className="h-32 bg-gray-200 rounded-t-lg"></div>
                <CardContent className="p-4">
                  <div className="space-y-3">
                    <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                    <div className="h-4 bg-gray-200 rounded w-1/2"></div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="space-y-6">
          <div className="flex items-center gap-4">
            <Link href="/teams">
              <Button variant="outline" size="sm">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Teams
              </Button>
            </Link>
            <h1 className="text-3xl font-bold">Team Comparison</h1>
          </div>
          <Card className="p-6 text-center">
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-red-600">Error</h3>
              <p className="text-muted-foreground">{error}</p>
              <Link href="/teams">
                <Button>Return to Teams</Button>
              </Link>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  const renderComparisonMetric = (label: string, values: number[], format: (val: number) => string = (v) => v.toString()) => {
    const max = Math.max(...values);
    const min = Math.min(...values);

    return (
      <TableRow>
        <TableCell className="font-medium">{label}</TableCell>
        {values.map((value, index) => (
          <TableCell key={index} className="text-center">
            <div className="space-y-1">
              <div className={`font-medium ${value === max ? 'text-green-600' : value === min ? 'text-red-600' : ''}`}>
                {format(value)}
              </div>
              <Progress
                value={(value / max) * 100}
                className="h-2"
              />
            </div>
          </TableCell>
        ))}
      </TableRow>
    );
  };

  return (
    <div className="container mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/teams">
          <Button variant="outline" size="sm">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Teams
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold">Team Comparison</h1>
          <p className="text-muted-foreground">
            Comparing {comparisonData.length} teams for {season} season
          </p>
        </div>
      </div>

      {/* Team Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {comparisonData.map((team, index) => (
          <Card key={team.teamId} className="overflow-hidden">
            <div className="h-24 bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center">
              <div className="text-white text-center">
                <h3 className="font-bold text-lg">{team.details?.name || `Team ${team.teamId}`}</h3>
                <p className="text-sm opacity-90">{team.details?.abbreviation || team.teamId}</p>
              </div>
            </div>
            <CardContent className="p-4">
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Record</span>
                  <span className="font-medium">
                    {team.stats?.basic?.wins || 0}-{team.stats?.basic?.losses || 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Conference</span>
                  <span className="font-medium">{team.details?.conference || 'Unknown'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Net Rating</span>
                  <span className={`font-medium ${
                    (team.stats?.advanced?.netRating || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {(team.stats?.advanced?.netRating || 0) >= 0 ? '+' : ''}{(team.stats?.advanced?.netRating || 0).toFixed(1)}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Detailed Comparison */}
      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="offense">Offense</TabsTrigger>
          <TabsTrigger value="defense">Defense</TabsTrigger>
          <TabsTrigger value="advanced">Advanced</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="w-5 h-5" />
                Basic Statistics
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Metric</TableHead>
                    {comparisonData.map((team, index) => (
                      <TableHead key={team.teamId} className="text-center">
                        Team {team.teamId}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {renderComparisonMetric(
                    'Wins',
                    comparisonData.map(team => team.stats?.basic?.wins || 0),
                    (v) => v.toString()
                  )}
                  {renderComparisonMetric(
                    'Losses',
                    comparisonData.map(team => team.stats?.basic?.losses || 0),
                    (v) => v.toString()
                  )}
                  {renderComparisonMetric(
                    'Win %',
                    comparisonData.map(team => team.stats?.basic?.winPct || 0.500),
                    (v) => (v * 100).toFixed(1) + '%'
                  )}
                  {renderComparisonMetric(
                    'Points Per Game',
                    comparisonData.map(team => team.stats?.basic?.ppg || 110.0),
                    (v) => v.toFixed(1)
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="offense" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5" />
                Offensive Statistics
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Metric</TableHead>
                    {comparisonData.map((team, index) => (
                      <TableHead key={team.teamId} className="text-center">
                        Team {team.teamId}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {renderComparisonMetric(
                    'Points Per Game',
                    comparisonData.map(team => team.stats?.basic?.ppg || 110.0),
                    (v) => v.toFixed(1)
                  )}
                  {renderComparisonMetric(
                    'Field Goal %',
                    comparisonData.map(team => team.stats?.basic?.fgPct || 0.450),
                    (v) => (v * 100).toFixed(1) + '%'
                  )}
                  {renderComparisonMetric(
                    '3-Point %',
                    comparisonData.map(team => team.stats?.basic?.threePtPct || 0.350),
                    (v) => (v * 100).toFixed(1) + '%'
                  )}
                  {renderComparisonMetric(
                    'Offensive Rating',
                    comparisonData.map(team => team.stats?.advanced?.offRtg || 110.0),
                    (v) => v.toFixed(1)
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="defense" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingDown className="w-5 h-5" />
                Defensive Statistics
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Metric</TableHead>
                    {comparisonData.map((team, index) => (
                      <TableHead key={team.teamId} className="text-center">
                        Team {team.teamId}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {renderComparisonMetric(
                    'Opp Points Per Game',
                    comparisonData.map(team => team.stats?.basic?.oppPpg || 110.0),
                    (v) => v.toFixed(1)
                  )}
                  {renderComparisonMetric(
                    'Defensive Rating',
                    comparisonData.map(team => team.stats?.advanced?.defRtg || 110.0),
                    (v) => v.toFixed(1)
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="advanced" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="w-5 h-5" />
                Advanced Metrics
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Metric</TableHead>
                    {comparisonData.map((team, index) => (
                      <TableHead key={team.teamId} className="text-center">
                        Team {team.teamId}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {renderComparisonMetric(
                    'Net Rating',
                    comparisonData.map(team => team.stats?.advanced?.netRating || 0.0),
                    (v) => v.toFixed(1)
                  )}
                  {renderComparisonMetric(
                    'Pace',
                    comparisonData.map(team => team.stats?.advanced?.pace || 100.0),
                    (v) => v.toFixed(1)
                  )}
                  {renderComparisonMetric(
                    'True Shooting %',
                    comparisonData.map(team => team.stats?.advanced?.tsPct || 0.550),
                    (v) => (v * 100).toFixed(1) + '%'
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
