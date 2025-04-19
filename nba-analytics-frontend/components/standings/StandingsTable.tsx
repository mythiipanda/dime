"use client"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { TeamStanding } from "@/lib/api/teams"
import { formatWinPct, getGamesBehind, getRecordColor, formatStreak, getClinchIndicators } from "@/lib/utils/teams"
import { Trophy, Star } from "lucide-react"
import { motion } from "framer-motion"
import { STAGGER_CHILD } from "@/lib/animations"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

interface StandingsTableProps {
  teams: TeamStanding[]
  conference: "Eastern" | "Western"
}

export function StandingsTable({ 
  teams, 
  /* eslint-disable-next-line @typescript-eslint/no-unused-vars */
  conference: _conference 
}: StandingsTableProps) {
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">Rank</TableHead>
            <TableHead className="min-w-[200px]">Team</TableHead>
            <TableHead className="text-center w-[60px]">W</TableHead>
            <TableHead className="text-center w-[60px]">L</TableHead>
            <TableHead className="text-center w-[80px]">PCT</TableHead>
            <TableHead className="text-center w-[60px]">GB</TableHead>
            <TableHead className="text-center w-[100px]">L10</TableHead>
            <TableHead className="text-center w-[80px]">STRK</TableHead>
            <TableHead className="text-center hidden md:table-cell">CONF</TableHead>
            <TableHead className="text-center hidden md:table-cell">HOME</TableHead>
            <TableHead className="text-center hidden md:table-cell">ROAD</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {teams.map((team) => (
            <motion.tr
              key={team.TeamID}
              {...STAGGER_CHILD}
              className="group hover:bg-accent/50 cursor-pointer transition-colors"
            >
              <TableCell className="font-medium">
                <div className="flex items-center gap-2">
                  {team.PlayoffRank <= 3 ? (
                    <Trophy className="h-4 w-4 text-primary" />
                  ) : team.PlayoffRank <= 6 ? (
                    <Star className="h-4 w-4 text-primary/70" />
                  ) : (
                    team.PlayoffRank
                  )}
                </div>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  {team.ClinchIndicator && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger>
                          <div className="flex gap-1">
                            {getClinchIndicators(team.ClinchIndicator).map((indicator, i) => (
                              <span 
                                key={i}
                                className={`text-xs px-1 rounded ${
                                  indicator.includes('Division Winner') ? 'bg-primary/20 text-primary' :
                                  indicator.includes('Playoff') ? 'bg-green-500/20 text-green-500' :
                                  indicator.includes('Conference') ? 'bg-yellow-500/20 text-yellow-500' :
                                  indicator.includes('League') ? 'bg-blue-500/20 text-blue-500' :
                                  indicator.includes('Play-In') ? 'bg-orange-500/20 text-orange-500' :
                                  indicator.includes('Eliminated') ? 'bg-red-500/20 text-red-500' : ''
                                }`}
                              >
                                {indicator.split(' ')[0]}
                              </span>
                            ))}
                          </div>
                        </TooltipTrigger>
                        <TooltipContent>
                          <div className="flex flex-col gap-1">
                            {getClinchIndicators(team.ClinchIndicator).map((indicator, i) => (
                              <span key={i}>{indicator}</span>
                            ))}
                          </div>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}
                  <span>{team.TeamName}</span>
                </div>
              </TableCell>
              <TableCell className="text-center">{team.WINS}</TableCell>
              <TableCell className="text-center">{team.LOSSES}</TableCell>
              <TableCell className={`text-center ${getRecordColor(team.WINS, team.LOSSES)}`}>
                {formatWinPct(team.WinPct)}%
              </TableCell>
              <TableCell className="text-center text-muted-foreground">
                {getGamesBehind(team.GB)}
              </TableCell>
              <TableCell className="text-center">
                {team.L10}
              </TableCell>
              <TableCell className={`text-center ${team.STRK.startsWith('W') ? 'text-green-500' : 'text-red-500'}`}>
                {formatStreak(team.STRK)}
              </TableCell>
              <TableCell className="text-center hidden md:table-cell">
                {team.ConferenceRecord}
              </TableCell>
              <TableCell className="text-center hidden md:table-cell">
                {team.HOME}
              </TableCell>
              <TableCell className="text-center hidden md:table-cell">
                {team.ROAD}
              </TableCell>
            </motion.tr>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}