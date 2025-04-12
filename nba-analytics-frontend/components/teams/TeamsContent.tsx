"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TeamsHeader } from "@/components/teams/TeamsHeader";
import { TeamCard } from "@/components/teams/TeamCard";
import { motion } from "framer-motion";
import { STAGGER_PARENT } from "@/lib/animations";
import { TeamStats } from "@/lib/api/teams";
import { useSearchParams } from "next/navigation";

interface TeamsContentProps {
  eastern: TeamStats[];
  western: TeamStats[];
}

export function TeamsContent({ eastern, western }: TeamsContentProps) {
  const searchParams = useSearchParams()
  const season = searchParams.get("season") || "2024-25"

  return (
    <>
      <TeamsHeader />
      <div className="text-sm text-muted-foreground mb-4">
        Viewing {season} Season
      </div>
      <Tabs defaultValue="eastern" className="space-y-4">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="eastern">Eastern Conference</TabsTrigger>
          <TabsTrigger value="western">Western Conference</TabsTrigger>
        </TabsList>
        
        <TabsContent value="eastern" className="space-y-4">
          <motion.div 
            className="grid gap-4 md:grid-cols-2 lg:grid-cols-3"
            {...STAGGER_PARENT}
          >
            {eastern.map((team) => (
              <TeamCard key={team.info.team_id} team={team} />
            ))}
          </motion.div>
        </TabsContent>

        <TabsContent value="western" className="space-y-4">
          <motion.div 
            className="grid gap-4 md:grid-cols-2 lg:grid-cols-3"
            {...STAGGER_PARENT}
          >
            {western.map((team) => (
              <TeamCard key={team.info.team_id} team={team} />
            ))}
          </motion.div>
        </TabsContent>
      </Tabs>
    </>
  );
} 