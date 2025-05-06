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
import { cn } from "@/lib/utils" // Import cn

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
    <div className={cn(
      "flex flex-col gap-4 xs:flex-row xs:items-center xs:justify-between",
      "animate-in fade-in-0 slide-in-from-top-4 duration-500" // Entrance animation for the whole header
    )}>
      <div className="space-y-1 animate-in fade-in-0 slide-in-from-left-4 duration-500 delay-100">
        <h1 className="text-3xl font-bold tracking-tight">NBA Teams</h1>
        <p className="text-muted-foreground">
          Track team performance, rankings, and historical data
        </p>
      </div>

      <div className="flex items-center gap-2 animate-in fade-in-0 slide-in-from-right-4 duration-500 delay-200">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className={cn(
              "w-[140px] justify-between",
              "transition-transform duration-200 hover:scale-105 active:scale-95"
            )}>
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
          className={cn(
            "transition-all duration-200 hover:scale-110 hover:shadow-md active:scale-90 active:shadow-sm",
            "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2" // Added focus visible for accessibility
          )}
        >
          <RefreshCcw className="h-4 w-4 group-hover:animate-spin-slow" /> {/* Optional: subtle spin on hover */}
        </Button>
      </div>
    </div>
  )
}