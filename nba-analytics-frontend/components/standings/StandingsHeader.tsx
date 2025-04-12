"use client"

import { cn } from "@/lib/utils"

interface StandingsHeaderProps {
  className?: string
}

export function StandingsHeader({ className }: StandingsHeaderProps) {
  return (
    <div className={cn("space-y-2", className)}>
      <h1 className="text-3xl font-bold tracking-tight">NBA Standings</h1>
      <div className="text-sm text-muted-foreground space-x-4">
        <span className="text-green-500">x</span>
        <span>Clinched Playoff Spot</span>
        <span className="text-yellow-500">y</span>
        <span>Clinched Division</span>
        <span className="text-blue-500">z</span>
        <span>Clinched Conference</span>
        <span className="text-red-500">e</span>
        <span>Eliminated</span>
      </div>
    </div>
  )
}