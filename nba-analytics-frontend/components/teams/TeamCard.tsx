/**
 * TeamCard Component
 * Single Responsibility: Render individual team card
 * Clean, focused component following SRP
 */

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { BarChart3, AlertTriangle } from "lucide-react";
import { type EnhancedTeam } from "@/lib/api/teams";

interface TeamCardProps {
  team: EnhancedTeam;
  currentSeason: string;
  viewMode: 'grid' | 'list' | 'table' | 'analytics';
  isSelected: boolean;
  onToggleSelection: (teamId: string) => void;
}

export function TeamCard({ 
  team, 
  currentSeason, 
  viewMode, 
  isSelected, 
  onToggleSelection 
}: TeamCardProps) {
  const getStatusBadgeColor = (status: string) => {
    switch (status) {
      case 'contender': return 'bg-green-500';
      case 'playoff-push': return 'bg-yellow-500';
      case 'rebuilding': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  const winPercentage = (team.record.wins / (team.record.wins + team.record.losses)) * 100;

  return (
    <div className="relative group">
      {viewMode === 'grid' && (
        <div className="absolute top-2 right-2 z-10">
          <Checkbox
            checked={isSelected}
            onCheckedChange={() => onToggleSelection(team.id)}
            className="bg-white shadow-md"
          />
        </div>
      )}

      <Link 
        href={`/teams/${team.id}?season=${currentSeason}`} 
        className="block transition-all duration-300 hover:scale-[1.02]"
      >
        <Card className="overflow-hidden h-full hover:shadow-xl transition-all duration-300 border-2 hover:border-primary/20">
          {/* Team Header with Logo and Colors */}
          <div
            className="h-32 flex items-center justify-center p-4 relative"
            style={{
              backgroundColor: team.primaryColor,
              backgroundImage: `linear-gradient(45deg, ${team.primaryColor}, ${team.secondaryColor})`
            }}
          >
            <img
              src={team.logo}
              alt={`${team.name} logo`}
              className="h-full object-contain transition-transform duration-300 group-hover:scale-110"
              style={{ filter: "drop-shadow(0px 4px 6px rgba(0, 0, 0, 0.3))" }}
            />

            {/* Status Badge */}
            <Badge className={`absolute top-2 left-2 ${getStatusBadgeColor(team.status)} text-white`}>
              {team.status.replace('-', ' ')}
            </Badge>

            {/* Real Data Indicator */}
            <Badge className="absolute top-2 right-12 bg-green-500 text-white text-xs">
              <BarChart3 className="w-3 h-3 mr-1" />
              Live Data
            </Badge>

            {/* Win Percentage Progress Bar */}
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-black/20">
              <div
                className="h-full bg-white/80 transition-all duration-500"
                style={{ width: `${winPercentage}%` }}
              />
            </div>
          </div>

          <CardContent className="p-4">
            <div className="space-y-3">
              {/* Team Name and Record */}
              <div className="text-center">
                <h3 className="font-bold text-lg group-hover:text-primary transition-colors">
                  {team.name}
                </h3>
                <div className="flex items-center justify-center gap-2">
                  <span className="text-2xl font-bold">
                    {team.record.wins}-{team.record.losses}
                  </span>
                  <Badge variant={team.streak.type === 'W' ? 'default' : 'destructive'}>
                    {team.streak.type}{team.streak.count}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  {team.conference}ern • {team.division}
                </p>
              </div>

              {/* Performance Metrics */}
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">OFF</span>
                  <span className="font-medium">{team.offensiveRating.toFixed(1)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">DEF</span>
                  <span className="font-medium">{team.defensiveRating.toFixed(1)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Pace</span>
                  <span className="font-medium">{team.pace.toFixed(1)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Playoffs</span>
                  <span className="font-medium">{team.playoffOdds}%</span>
                </div>
              </div>

              {/* Last Game and Next Game */}
              <div className="space-y-1 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Last:</span>
                  <span className={team.lastGame.result === 'W' ? 'text-green-600' : 'text-red-600'}>
                    {team.lastGame.result} vs {team.lastGame.opponent} {team.lastGame.score}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Next:</span>
                  <span>
                    {team.nextGame.home ? 'vs' : '@'} {team.nextGame.opponent}
                  </span>
                </div>
              </div>

              {/* Injuries Indicator */}
              {team.injuries.length > 0 && (
                <div className="flex items-center gap-1 text-xs text-red-600">
                  <AlertTriangle className="w-3 h-3" />
                  <span>{team.injuries.length} injured</span>
                </div>
              )}

              {/* Key Players */}
              {team.keyPlayers.length > 0 && (
                <div className="text-xs">
                  <span className="text-muted-foreground">Stars: </span>
                  <span>{team.keyPlayers.slice(0, 2).join(', ')}</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </Link>
    </div>
  );
}
