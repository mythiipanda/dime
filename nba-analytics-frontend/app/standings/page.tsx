import { Suspense } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { getLeagueStandings } from "@/lib/api/teams"
import { StandingsTable } from "@/components/standings/StandingsTable"
import { ErrorBoundaryHandler } from "@/components/ui/error-boundary"
import { TableSkeleton } from "@/components/ui/loading-state"
import { motion } from "framer-motion"
import { FADE_IN } from "@/lib/animations"
import { Metadata } from "next"
import { TeamStanding } from "@/lib/api/teams"

export const metadata: Metadata = {
  title: "NBA Standings | NBA Analytics",
  description: "Current NBA standings and team statistics",
}

export const revalidate = 300 // Revalidate every 5 minutes

function StandingsLoading() {
  return (
    <div className="space-y-4">
      <TableSkeleton />
    </div>
  )
}

export default async function StandingsPage() {
  try {
    const { standings } = await getLeagueStandings()

    const eastern = standings
      .filter((team) => team.Conference === "East")
      .sort((a, b) => a.PlayoffRank - b.PlayoffRank)
      
    const western = standings
      .filter((team) => team.Conference === "West")
      .sort((a, b) => a.PlayoffRank - b.PlayoffRank)

    return (
      <div className="flex-1 space-y-4 p-4 md:p-8 pt-6">
        <motion.div {...FADE_IN}>
          <Tabs defaultValue="eastern" className="space-y-4">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="eastern">Eastern Conference</TabsTrigger>
              <TabsTrigger value="western">Western Conference</TabsTrigger>
            </TabsList>

            <div className="text-sm text-muted-foreground flex flex-wrap gap-4">
              <span className="flex items-center gap-1">
                <span className="px-1 rounded bg-primary/20 text-primary text-xs">Division</span>
                Division Winner
              </span>
              <span className="flex items-center gap-1">
                <span className="px-1 rounded bg-green-500/20 text-green-500 text-xs">Playoff</span>
                Clinched Playoff Spot
              </span>
              <span className="flex items-center gap-1">
                <span className="px-1 rounded bg-yellow-500/20 text-yellow-500 text-xs">Conference</span>
                Conference Winner
              </span>
              <span className="flex items-center gap-1">
                <span className="px-1 rounded bg-blue-500/20 text-blue-500 text-xs">League</span>
                League Leader
              </span>
              <span className="flex items-center gap-1">
                <span className="px-1 rounded bg-orange-500/20 text-orange-500 text-xs">Play-In</span>
                Clinched Play-In
              </span>
              <span className="flex items-center gap-1">
                <span className="px-1 rounded bg-red-500/20 text-red-500 text-xs">Eliminated</span>
                Eliminated
              </span>
            </div>

            <Suspense fallback={<StandingsLoading />}>
              <TabsContent value="eastern" className="space-y-4">
                <StandingsTable teams={eastern} conference="Eastern" />
              </TabsContent>

              <TabsContent value="western" className="space-y-4">
                <StandingsTable teams={western} conference="Western" />
              </TabsContent>
            </Suspense>
          </Tabs>
        </motion.div>
      </div>
    )
  } catch (error) {
    console.error("Error loading standings:", error)
    return (
      <ErrorBoundaryHandler error={new Error("Failed to load standings data. Please try again later.")} />
    )
  }
}