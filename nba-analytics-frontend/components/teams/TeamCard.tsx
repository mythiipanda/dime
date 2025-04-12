'use client'; // Add this directive for Framer Motion

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Trophy } from "lucide-react";
import { TeamStats } from "@/lib/api/teams";
import { motion } from "framer-motion"; // Import motion
import { STAGGER_CHILD } from "@/lib/animations"; // Import animation

interface TeamCardProps {
  team: TeamStats;
}

export function TeamCard({ team }: TeamCardProps) {
  return (
    <motion.div {...STAGGER_CHILD}> {/* Wrap with motion.div and apply animation */}
      <Card className="hover:bg-accent/50 cursor-pointer transition-colors">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <div className="space-y-1">
            <CardTitle className="text-base">{`${team.info.team_city} ${team.info.team_name}`}</CardTitle>
            <p className="text-sm text-muted-foreground">{team.info.team_division} Division</p>
          </div>
          <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center">
            {team.info.conf_rank <= 3 && <Trophy className="h-6 w-6 text-primary" />}
            {team.info.conf_rank > 3 && `#${team.info.conf_rank}`}
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-2 text-sm">
            <div className="space-y-1">
              <p className="text-muted-foreground">Record</p>
              <p className="font-regular">{`${team.info.wins}-${team.info.losses}`}</p>
            </div>
            <div className="space-y-1">
              <p className="text-muted-foreground">Win %</p>
              <p className="font-regular">{(team.info.win_pct * 100).toFixed(1)}%</p>
            </div>
            <div className="space-y-1">
              <p className="text-muted-foreground">L10</p>
              <p className="font-regular">{team.info.last_ten}</p>
            </div>
          </div>
          <div className="mt-3 space-y-1">
            <p className="text-sm text-muted-foreground">Team Stats</p>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>PPG: {team.stats.overall.pts.toFixed(1)}</div>
              <div>OPP PPG: {team.stats.overall.opp_pts.toFixed(1)}</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}