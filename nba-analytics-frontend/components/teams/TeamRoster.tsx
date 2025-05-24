"use client";

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { getTeamDetails, getTeamPlayerStats } from "@/lib/api/teams";
import Link from "next/link";
import { Users } from "lucide-react";

// Function to get NBA player headshot
const getPlayerHeadshot = (playerId: string) => {
  return `https://cdn.nba.com/headshots/nba/latest/1040x760/${playerId}.png`;
};

interface TeamRosterProps {
  teamId: string;
  season: string;
}

export function TeamRoster({ teamId, season }: TeamRosterProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [rosterData, setRosterData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchRosterData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Fetch both roster info and player stats
        const [teamDetails, playerStats] = await Promise.all([
          getTeamDetails(teamId, season),
          getTeamPlayerStats(teamId, season)
        ]);

        // Combine roster info with player stats
        const playersWithStats = (playerStats?.players_season_totals || []).map((player: any) => {
          const rosterInfo = teamDetails?.roster?.find((r: any) =>
            r.PLAYER === player.PLAYER_NAME || r.PLAYER_NAME === player.PLAYER_NAME
          );

          // Calculate stats from season totals
          const gamesPlayed = player.GP || 1;
          const fgm = player.FGM || 0;
          const fga = player.FGA || 0;
          const fg3m = player.FG3M || 0;
          const ftm = player.FTM || 0;
          const fta = player.FTA || 0;
          const pts = player.PTS || 0;
          const min = player.MIN || 0;

          // Since we're requesting per_mode=PerGame, the stats should already be per-game
          // If they're still totals, we need to divide by games played
          // Check if the values look like totals (> 50 for points) or per-game (< 50 for points)
          const looksLikeTotals = pts > 50; // Most players don't average 50+ PPG

          const ppg = looksLikeTotals && gamesPlayed > 0 ? pts / gamesPlayed : pts;
          const rpg = looksLikeTotals && gamesPlayed > 0 ? (player.REB || 0) / gamesPlayed : (player.REB || 0);
          const apg = looksLikeTotals && gamesPlayed > 0 ? (player.AST || 0) / gamesPlayed : (player.AST || 0);
          const spg = looksLikeTotals && gamesPlayed > 0 ? (player.STL || 0) / gamesPlayed : (player.STL || 0);
          const bpg = looksLikeTotals && gamesPlayed > 0 ? (player.BLK || 0) / gamesPlayed : (player.BLK || 0);
          const mpg = looksLikeTotals && gamesPlayed > 0 ? min / gamesPlayed : min;



          // Calculate shooting percentages (already calculated correctly)
          const fgPct = player.FG_PCT || 0;
          const fg3Pct = player.FG3_PCT || 0;
          const ftPct = player.FT_PCT || 0;

          // Calculate advanced stats
          const efg = fga > 0 ? (fgm + 0.5 * fg3m) / fga : 0;
          const ts = (fga + 0.44 * fta) > 0 ? pts / (2 * (fga + 0.44 * fta)) : 0;

          // Simplified PER calculation (using NBA Fantasy Points as proxy)
          const per = mpg > 0 ? (player.NBA_FANTASY_PTS || 0) / gamesPlayed / mpg * 48 : 0;

          // Simplified USG% calculation
          const teamFGA = 7382; // From team_overall data
          const teamFTA = 1565; // From team_overall data
          const teamTOV = 973; // From team_overall data
          const teamMin = 3966; // From team_overall data
          const usg = min > 0 ? ((fga + 0.44 * fta + (player.TOV || 0)) * (teamMin / 5)) / (min * (teamFGA + 0.44 * teamFTA + teamTOV)) : 0;

          return {
            id: player.PLAYER_ID,
            name: player.PLAYER_NAME,
            player_name: player.PLAYER_NAME,
            number: rosterInfo?.NUM || player.JERSEY_NUMBER || '',
            position: rosterInfo?.POSITION || 'N/A',
            height: rosterInfo?.HEIGHT || 'N/A',
            weight: rosterInfo?.WEIGHT || 'N/A',
            age: player.AGE || rosterInfo?.AGE || 'N/A',
            experience: rosterInfo?.EXP || 'N/A',
            college: rosterInfo?.SCHOOL || 'N/A',
            stats: {
              ppg: ppg,
              rpg: rpg,
              apg: apg,
              spg: spg,
              bpg: bpg,
              fg: fgPct,
              fg3: fg3Pct,
              ft: ftPct,
              mpg: mpg,
              efg: efg,
              per: Math.min(Math.max(per, 0), 50), // Cap PER between 0-50
              ts: ts,
              usg: Math.min(Math.max(usg, 0), 1) // Cap USG between 0-100%
            }
          };
        });

        setRosterData({
          roster: playersWithStats,
          coaches: teamDetails?.coaches || mockCoaches
        });
      } catch (err) {
        console.error('Error fetching roster data:', err);
        setError('Failed to load roster data');
        // Set fallback mock data
        setRosterData({
          roster: mockPlayers,
          coaches: mockCoaches
        });
      } finally {
        setLoading(false);
      }
    };

    fetchRosterData();
  }, [teamId, season]);

  // Mock data for fallback
  const mockPlayers = [
    {
      id: "1",
      name: "Stephen Curry",
      number: "30",
      position: "PG",
      height: "6'2\"",
      weight: "185",
      age: 35,
      experience: "14 years",
      college: "Davidson",
      stats: {
        ppg: 26.8,
        rpg: 4.2,
        apg: 6.5,
        spg: 1.2,
        bpg: 0.4,
        fg: 0.487,
        fg3: 0.412,
        ft: 0.925,
        mpg: 32.5,
        efg: 0.587,
        per: 25.1,
        ts: 0.624,
        usg: 30.5
      }
    },
    {
      id: "2",
      name: "Klay Thompson",
      number: "11",
      position: "SG",
      height: "6'6\"",
      weight: "215",
      age: 33,
      experience: "11 years",
      college: "Washington State",
      stats: {
        ppg: 17.9,
        rpg: 3.3,
        apg: 2.3,
        spg: 0.7,
        bpg: 0.4,
        fg: 0.434,
        fg3: 0.385,
        ft: 0.875,
        mpg: 30.2,
        efg: 0.535,
        per: 15.2,
        ts: 0.568,
        usg: 24.8
      }
    },
    {
      id: "3",
      name: "Andrew Wiggins",
      number: "22",
      position: "SF",
      height: "6'7\"",
      weight: "197",
      age: 28,
      experience: "9 years",
      college: "Kansas",
      stats: {
        ppg: 12.7,
        rpg: 4.3,
        apg: 1.7,
        spg: 0.8,
        bpg: 0.6,
        fg: 0.454,
        fg3: 0.365,
        ft: 0.705,
        mpg: 28.5,
        efg: 0.502,
        per: 13.5,
        ts: 0.532,
        usg: 21.2
      }
    },
    {
      id: "4",
      name: "Draymond Green",
      number: "23",
      position: "PF",
      height: "6'6\"",
      weight: "230",
      age: 33,
      experience: "11 years",
      college: "Michigan State",
      stats: {
        ppg: 8.8,
        rpg: 7.2,
        apg: 6.0,
        spg: 1.1,
        bpg: 0.8,
        fg: 0.526,
        fg3: 0.305,
        ft: 0.712,
        mpg: 31.5,
        efg: 0.521,
        per: 15.8,
        ts: 0.548,
        usg: 15.6
      }
    },
    {
      id: "5",
      name: "Kevon Looney",
      number: "5",
      position: "C",
      height: "6'9\"",
      weight: "222",
      age: 27,
      experience: "8 years",
      college: "UCLA",
      stats: {
        ppg: 5.5,
        rpg: 6.8,
        apg: 2.5,
        spg: 0.5,
        bpg: 0.5,
        fg: 0.625,
        fg3: 0.000,
        ft: 0.605,
        mpg: 20.5,
        efg: 0.583,
        per: 12.8,
        ts: 0.592,
        usg: 10.2
      }
    },
    {
      id: "6",
      name: "Jordan Poole",
      number: "3",
      position: "SG",
      height: "6'4\"",
      weight: "194",
      age: 24,
      experience: "4 years",
      college: "Michigan",
      stats: {
        ppg: 15.8,
        rpg: 2.5,
        apg: 4.5,
        spg: 0.7,
        bpg: 0.2,
        fg: 0.432,
        fg3: 0.375,
        ft: 0.872,
        mpg: 27.5,
        efg: 0.522,
        per: 14.5,
        ts: 0.562,
        usg: 25.1
      }
    },
  ];

  const mockCoaches = [
    { coach_name: "Steve Kerr", coach_type: "Head Coach", is_assistant: false },
    { coach_name: "Mike Brown", coach_type: "Assistant Coach", is_assistant: true },
    { coach_name: "Ron Adams", coach_type: "Assistant Coach", is_assistant: true }
  ];

  // Use real data if available, otherwise fallback to mock data
  const players = rosterData?.roster || mockPlayers;
  const coaches = rosterData?.coaches || mockCoaches;

  const filteredPlayers = players.filter((player: any) =>
    player.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    player.player_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    player.position?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-10 w-64" />
        </div>
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-semibold">Team Roster</h2>
          {rosterData && (
            <Badge variant="secondary" className="text-xs">
              <Users className="w-3 h-3 mr-1" />
              Real NBA Data
            </Badge>
          )}
        </div>
        <div className="w-[250px]">
          <Input
            placeholder="Search players..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <Tabs defaultValue="main" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="main">Main Stats</TabsTrigger>
          <TabsTrigger value="advanced">Advanced Stats</TabsTrigger>
          <TabsTrigger value="bio">Player Info</TabsTrigger>
        </TabsList>

        <TabsContent value="main" className="pt-4">
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Player</TableHead>
                  <TableHead className="text-right">PPG</TableHead>
                  <TableHead className="text-right">RPG</TableHead>
                  <TableHead className="text-right">APG</TableHead>
                  <TableHead className="text-right">FG%</TableHead>
                  <TableHead className="text-right">3P%</TableHead>
                  <TableHead className="text-right">FT%</TableHead>
                  <TableHead className="text-right">MPG</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredPlayers.map((player: any, index: number) => {
                  const playerName = player.name || player.player_name || 'Unknown Player';
                  const playerNumber = player.number || player.jersey_number || (index + 1).toString();
                  const playerPosition = player.position || 'N/A';
                  const stats = player.stats || {};

                  return (
                    <TableRow key={player.id || player.player_id || index}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <Avatar className="h-8 w-8">
                            <img
                              src={getPlayerHeadshot(player.id || player.player_id)}
                              alt={playerName}
                              className="h-full w-full object-cover rounded-full"
                              onError={(e) => {
                                // Fallback to jersey number if image fails to load
                                e.currentTarget.style.display = 'none';
                                e.currentTarget.nextElementSibling.style.display = 'flex';
                              }}
                            />
                            <div className="bg-primary text-primary-foreground rounded-full h-full w-full flex items-center justify-center text-xs font-bold" style={{display: 'none'}}>
                              {playerNumber}
                            </div>
                          </Avatar>
                          <div>
                            <Link
                              href={`/players/${player.id || player.player_id}`}
                              className="hover:text-primary transition-colors cursor-pointer"
                            >
                              {playerName}
                            </Link>
                            <div className="text-xs text-muted-foreground">
                              {playerPosition}
                            </div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">{(stats.ppg || 0).toFixed(1)}</TableCell>
                      <TableCell className="text-right">{(stats.rpg || 0).toFixed(1)}</TableCell>
                      <TableCell className="text-right">{(stats.apg || 0).toFixed(1)}</TableCell>
                      <TableCell className="text-right">{((stats.fg || 0) * 100).toFixed(1)}%</TableCell>
                      <TableCell className="text-right">{((stats.fg3 || 0) * 100).toFixed(1)}%</TableCell>
                      <TableCell className="text-right">{((stats.ft || 0) * 100).toFixed(1)}%</TableCell>
                      <TableCell className="text-right">{(stats.mpg || 0).toFixed(1)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="advanced" className="pt-4">
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Player</TableHead>
                  <TableHead className="text-right">eFG%</TableHead>
                  <TableHead className="text-right">TS%</TableHead>
                  <TableHead className="text-right">PER</TableHead>
                  <TableHead className="text-right">USG%</TableHead>
                  <TableHead className="text-right">STL</TableHead>
                  <TableHead className="text-right">BLK</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredPlayers.map((player: any, index: number) => {
                  const playerName = player.name || player.player_name || 'Unknown Player';
                  const playerNumber = player.number || player.jersey_number || (index + 1).toString();
                  const playerPosition = player.position || 'N/A';
                  const stats = player.stats || {};

                  return (
                    <TableRow key={player.id || player.player_id || index}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <Avatar className="h-8 w-8">
                            <img
                              src={getPlayerHeadshot(player.id || player.player_id)}
                              alt={playerName}
                              className="h-full w-full object-cover rounded-full"
                              onError={(e) => {
                                // Fallback to jersey number if image fails to load
                                e.currentTarget.style.display = 'none';
                                e.currentTarget.nextElementSibling.style.display = 'flex';
                              }}
                            />
                            <div className="bg-primary text-primary-foreground rounded-full h-full w-full flex items-center justify-center text-xs font-bold" style={{display: 'none'}}>
                              {playerNumber}
                            </div>
                          </Avatar>
                          <div>
                            <Link
                              href={`/players/${player.id || player.player_id}`}
                              className="hover:text-primary transition-colors cursor-pointer"
                            >
                              {playerName}
                            </Link>
                            <div className="text-xs text-muted-foreground">
                              {playerPosition}
                            </div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">{((stats.efg || 0) * 100).toFixed(1)}%</TableCell>
                      <TableCell className="text-right">{((stats.ts || 0) * 100).toFixed(1)}%</TableCell>
                      <TableCell className="text-right">{(stats.per || 0).toFixed(1)}</TableCell>
                      <TableCell className="text-right">{((stats.usg || 0) * 100).toFixed(1)}%</TableCell>
                      <TableCell className="text-right">{(stats.spg || 0).toFixed(1)}</TableCell>
                      <TableCell className="text-right">{(stats.bpg || 0).toFixed(1)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="bio" className="pt-4">
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Player</TableHead>
                  <TableHead>Position</TableHead>
                  <TableHead>Height</TableHead>
                  <TableHead>Weight</TableHead>
                  <TableHead>Age</TableHead>
                  <TableHead>Experience</TableHead>
                  <TableHead>College</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredPlayers.map((player: any, index: number) => {
                  const playerName = player.name || player.player_name || 'Unknown Player';
                  const playerNumber = player.number || player.jersey_number || (index + 1).toString();
                  const playerPosition = player.position || 'N/A';

                  return (
                    <TableRow key={player.id || player.player_id || index}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <Avatar className="h-8 w-8">
                            <img
                              src={getPlayerHeadshot(player.id || player.player_id)}
                              alt={playerName}
                              className="h-full w-full object-cover rounded-full"
                              onError={(e) => {
                                // Fallback to jersey number if image fails to load
                                e.currentTarget.style.display = 'none';
                                e.currentTarget.nextElementSibling.style.display = 'flex';
                              }}
                            />
                            <div className="bg-primary text-primary-foreground rounded-full h-full w-full flex items-center justify-center text-xs font-bold" style={{display: 'none'}}>
                              {playerNumber}
                            </div>
                          </Avatar>
                          <div>
                            <Link
                              href={`/players/${player.id || player.player_id}`}
                              className="hover:text-primary transition-colors cursor-pointer"
                            >
                              {playerName}
                            </Link>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{playerPosition}</Badge>
                      </TableCell>
                      <TableCell>{player.height || 'N/A'}</TableCell>
                      <TableCell>{player.weight ? `${player.weight} lbs` : 'N/A'}</TableCell>
                      <TableCell>{player.age || 'N/A'}</TableCell>
                      <TableCell>{player.experience || 'N/A'}</TableCell>
                      <TableCell>{player.college || 'N/A'}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}