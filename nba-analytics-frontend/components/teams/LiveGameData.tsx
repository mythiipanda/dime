'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { nbaDataService } from '@/lib/services/NBADataService';
import { cn } from '@/lib/utils';
import { 
  Clock, 
  Calendar, 
  MapPin, 
  TrendingUp, 
  TrendingDown,
  Target,
  Trophy,
  RefreshCw,
  Play,
  Pause,
  BarChart3
} from 'lucide-react';

interface LiveGameDataProps {
  className?: string;
}

interface GameData {
  gameId: string;
  gameDate: string;
  gameTime: string;
  homeTeam: {
    teamId: number;
    teamName: string;
    teamAbbreviation: string;
    score: number;
  };
  awayTeam: {
    teamId: number;
    teamName: string;
    teamAbbreviation: string;
    score: number;
  };
  gameStatus: string;
  gameStatusText: string;
  period: number;
  gameClock: string;
  arena: string;
  city: string;
  state: string;
  isLive: boolean;
  isCompleted: boolean;
  isUpcoming: boolean;
}

export function LiveGameData({ className }: LiveGameDataProps) {
  const [games, setGames] = useState<GameData[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [autoRefresh, setAutoRefresh] = useState(false);

  useEffect(() => {
    loadGameData();
  }, []);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (autoRefresh) {
      interval = setInterval(() => {
        loadGameData();
      }, 30000); // Refresh every 30 seconds
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  const loadGameData = async () => {
    try {
      setLoading(true);
      // Get today's date in YYYY-MM-DD format
      const today = new Date().toISOString().split('T')[0];
      
      // Fetch real scoreboard data from backend
      const scoreboardData = await nbaDataService.getScoreboard(today);
      
      // Transform scoreboard data to our format
      const transformedGames: GameData[] = scoreboardData.map(game => ({
        gameId: game.GAME_ID,
        gameDate: game.GAME_DATE_EST,
        gameTime: game.GAME_TIME,
        homeTeam: {
          teamId: game.HOME_TEAM_ID,
          teamName: game.HOME_TEAM_NAME,
          teamAbbreviation: game.HOME_TEAM_ABBREVIATION,
          score: game.HOME_TEAM_SCORE || 0
        },
        awayTeam: {
          teamId: game.VISITOR_TEAM_ID,
          teamName: game.VISITOR_TEAM_NAME,
          teamAbbreviation: game.VISITOR_TEAM_ABBREVIATION,
          score: game.VISITOR_TEAM_SCORE || 0
        },
        gameStatus: game.GAME_STATUS_TEXT,
        gameStatusText: game.GAME_STATUS_TEXT,
        period: game.PERIOD || 0,
        gameClock: game.GAME_CLOCK || '',
        arena: game.ARENA_NAME || '',
        city: game.GAME_DATE_EST, // Placeholder
        state: '', // Placeholder
        isLive: game.GAME_STATUS_TEXT.includes('Q') || game.GAME_STATUS_TEXT.includes('Half'),
        isCompleted: game.GAME_STATUS_TEXT === 'Final',
        isUpcoming: game.GAME_STATUS_TEXT.includes('ET') || game.GAME_STATUS_TEXT.includes('PM')
      }));
      
      setGames(transformedGames);
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Error loading game data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getGameStatusColor = (game: GameData) => {
    if (game.isLive) return 'text-red-600 font-bold';
    if (game.isCompleted) return 'text-gray-600';
    return 'text-blue-600';
  };

  const getGameStatusIcon = (game: GameData) => {
    if (game.isLive) return <Play className="w-4 h-4 text-red-500" />;
    if (game.isCompleted) return <Target className="w-4 h-4 text-gray-500" />;
    return <Clock className="w-4 h-4 text-blue-500" />;
  };

  const formatTimeAgo = (date: Date) => {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  const liveGames = games.filter(g => g.isLive);
  const completedGames = games.filter(g => g.isCompleted);
  const upcomingGames = games.filter(g => g.isUpcoming);

  if (loading) {
    return (
      <div className={cn("space-y-6", className)}>
        <div className="text-center py-8">
          <h2 className="text-xl font-semibold mb-4">Loading Live Game Data...</h2>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Live NBA Games</h1>
          <div className="flex items-center space-x-2 text-sm text-muted-foreground mt-1">
            <Clock className="w-4 h-4" />
            <span>Last updated: {formatTimeAgo(lastUpdated)}</span>
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={autoRefresh ? "bg-green-50 border-green-200" : ""}
          >
            <RefreshCw className={cn("w-4 h-4 mr-2", autoRefresh && "animate-spin")} />
            {autoRefresh ? 'Auto Refresh On' : 'Auto Refresh Off'}
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            onClick={loadGameData}
            disabled={loading}
          >
            <RefreshCw className={cn("w-4 h-4 mr-2", loading && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Game Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-red-600">{liveGames.length}</div>
            <div className="text-sm text-muted-foreground">Live Games</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">{upcomingGames.length}</div>
            <div className="text-sm text-muted-foreground">Upcoming Today</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-gray-600">{completedGames.length}</div>
            <div className="text-sm text-muted-foreground">Completed</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-green-600">{games.length}</div>
            <div className="text-sm text-muted-foreground">Total Games</div>
          </CardContent>
        </Card>
      </div>

      {/* Live Games Section */}
      {liveGames.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-2xl font-bold text-red-600">🔴 Live Games ({liveGames.length})</h2>
          {liveGames.map((game) => (
            <Card key={game.gameId} className="border-red-200 bg-red-50">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-3">
                      <Badge variant="destructive" className="animate-pulse">LIVE</Badge>
                      <span className="font-bold">{game.awayTeam.teamAbbreviation}</span>
                      <span className="text-2xl font-bold">{game.awayTeam.score}</span>
                      <span className="text-muted-foreground">@</span>
                      <span className="font-bold">{game.homeTeam.teamAbbreviation}</span>
                      <span className="text-2xl font-bold">{game.homeTeam.score}</span>
                    </div>
                  </div>
                  
                  <div className="text-right">
                    <div className="font-bold">{game.gameStatusText}</div>
                    <div className="text-sm text-muted-foreground">{game.gameClock}</div>
                  </div>
                </div>
                
                <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                  <div className="flex items-center space-x-1">
                    <MapPin className="w-4 h-4" />
                    <span>{game.arena}</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <BarChart3 className="w-4 h-4" />
                    <span>Period {game.period}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* All Games Section */}
      <div className="space-y-4">
        <h2 className="text-2xl font-bold">Today's Games ({games.length})</h2>
        
        {games.map((game) => (
          <Card key={game.gameId}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-4">
                  <div className="flex items-center space-x-3">
                    {getGameStatusIcon(game)}
                    <span className="font-bold">{game.awayTeam.teamAbbreviation}</span>
                    {game.isCompleted || game.isLive ? (
                      <span className="text-xl font-bold">{game.awayTeam.score}</span>
                    ) : (
                      <span className="text-muted-foreground">vs</span>
                    )}
                    <span className="text-muted-foreground">@</span>
                    <span className="font-bold">{game.homeTeam.teamAbbreviation}</span>
                    {game.isCompleted || game.isLive ? (
                      <span className="text-xl font-bold">{game.homeTeam.score}</span>
                    ) : null}
                  </div>
                </div>
                
                <div className="text-right">
                  <div className={cn("font-bold", getGameStatusColor(game))}>
                    {game.gameStatusText}
                  </div>
                  {game.gameClock && (
                    <div className="text-sm text-muted-foreground">{game.gameClock}</div>
                  )}
                </div>
              </div>
              
              <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                <div className="flex items-center space-x-1">
                  <Calendar className="w-4 h-4" />
                  <span>{game.gameDate}</span>
                </div>
                {game.arena && (
                  <div className="flex items-center space-x-1">
                    <MapPin className="w-4 h-4" />
                    <span>{game.arena}</span>
                  </div>
                )}
                {game.period > 0 && (
                  <div className="flex items-center space-x-1">
                    <BarChart3 className="w-4 h-4" />
                    <span>Period {game.period}</span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {games.length === 0 && (
        <Card>
          <CardContent className="p-8 text-center">
            <Calendar className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
            <h3 className="text-lg font-semibold mb-2">No Games Today</h3>
            <p className="text-muted-foreground">
              There are no NBA games scheduled for today.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
