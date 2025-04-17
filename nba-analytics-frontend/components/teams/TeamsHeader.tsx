"use client"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChevronDown, RefreshCcw } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"

type Season = "2024-25" | "2023-24" | "2022-23" | "2021-22"

export function TeamsHeader() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const currentSeason = (searchParams.get("season") as Season) || "2024-25"

  const handleSeasonChange = (season: Season) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("season", season)
    router.push(`/teams?${params.toString()}`)
  }

  return (
    <div className="flex flex-col gap-4 xs:flex-row xs:items-center xs:justify-between">
      <div className="space-y-1">
        <h1 className="text-3xl font-bold tracking-tight">NBA Teams</h1>
        <p className="text-muted-foreground">
          Track team performance, rankings, and historical data
        </p>
      </div>

      <div className="flex items-center gap-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="w-[140px] justify-between">
              {currentSeason}
              <ChevronDown className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-[140px]">
            <DropdownMenuLabel>Season</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => handleSeasonChange("2024-25")}>
              2024-25
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleSeasonChange("2023-24")}>
              2023-24
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleSeasonChange("2022-23")}>
              2022-23
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleSeasonChange("2021-22")}>
              2021-22
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <Button
          variant="outline"
          size="icon"
          onClick={() => router.refresh()}
          title="Refresh team data"
        >
          <RefreshCcw className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}