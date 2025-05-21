"use client";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { CardTitle } from "@/components/ui/card"; // Assuming CardTitle is needed standalone or re-export if not
import { PlayerInfo } from "@/app/(app)/players/types"; // Adjust path as necessary

interface PlayerHeaderProps {
  info: PlayerInfo;
  headshotUrl: string | null;
}

export function PlayerHeader({ info, headshotUrl }: PlayerHeaderProps) {
  if (!info) {
    // This case should ideally be handled by the parent, but good to have a fallback
    return <p>Loading player details...</p>;
  }

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 border-b pb-4">
      <Avatar className="h-24 w-24 sm:h-32 sm:w-32 border-2 shadow-sm">
        {headshotUrl ? (
          <AvatarImage src={headshotUrl} alt={info.DISPLAY_FIRST_LAST} className="object-cover"/>
        ) : (
          <AvatarFallback className="text-4xl">
            {info.DISPLAY_FIRST_LAST?.split(' ').map((n: string) => n[0]).join('')}
          </AvatarFallback>
        )}
      </Avatar>
      <div className="flex-1 space-y-1">
        <CardTitle className="text-3xl sm:text-4xl font-bold">{info.DISPLAY_FIRST_LAST}</CardTitle>
        <div className="flex flex-wrap items-center gap-2 text-muted-foreground text-sm sm:text-base">
          {info.POSITION && <Badge variant="secondary">{info.POSITION}</Badge>}
          {info.HEIGHT && <span>{info.HEIGHT}</span>}
          {info.WEIGHT && <span>{info.WEIGHT} lbs</span>}
          {info.JERSEY && <Badge variant="outline">#{info.JERSEY}</Badge>}
          {info.TEAM_CITY && info.TEAM_ABBREVIATION && <span>{info.TEAM_CITY} {info.TEAM_ABBREVIATION}</span>}
        </div>
        <div className="text-xs sm:text-sm text-muted-foreground space-y-0.5">
          {info.SEASON_EXP !== undefined && <p>Experience: {info.SEASON_EXP} years</p>}
          {info.BIRTHDATE && <p>Born: {new Date(info.BIRTHDATE).toLocaleDateString()} {info.COUNTRY && `(${info.COUNTRY})`}</p>}
          {info.SCHOOL && <p>College: {info.SCHOOL}</p>}
          {(info.FROM_YEAR !== undefined && info.TO_YEAR !== undefined) && <p>Career: {info.FROM_YEAR} - {info.TO_YEAR}</p>}
        </div>
      </div>
    </div>
  );
} 