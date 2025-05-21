`use client`;

import { AdvancedMetrics } from "@/app/(app)/players/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

interface AdvancedMetricsDisplayProps {
  metrics: AdvancedMetrics;
}

const metricDisplayConfig: { key: keyof AdvancedMetrics; label: string; description: string; format?: (value: number) => string }[] = [
  { key: "RAPTOR_TOTAL", label: "RAPTOR Total", description: "Overall RAPTOR rating (Box Regularized Adjusted Plus-Minus). Higher is better." },
  { key: "RAPTOR_OFFENSE", label: "RAPTOR Offense", description: "Offensive RAPTOR rating." },
  { key: "RAPTOR_DEFENSE", label: "RAPTOR Defense", description: "Defensive RAPTOR rating." },
  { key: "WAR", label: "WAR", description: "Wins Above Replacement. Estimates a player's contribution in wins." },
  { key: "ELO_CURRENT", label: "ELO Current", description: "Current ELO rating for the player." },
  { key: "TS_PCT", label: "True Shooting %", description: "True Shooting Percentage. Measures shooting efficiency.", format: (val) => `${(val * 100).toFixed(1)}%` },
  { key: "USG_PCT", label: "Usage %", description: "Usage Percentage. Estimates the percentage of team plays used by a player while on the floor.", format: (val) => `${(val * 100).toFixed(1)}%` },
  { key: "AST_PCT", label: "Assist %", description: "Assist Percentage. Estimates the percentage of teammate field goals a player assisted while on the floor.", format: (val) => `${(val * 100).toFixed(1)}%` },
  { key: "REB_PCT", label: "Rebound %", description: "Rebound Percentage. Estimates the percentage of missed shots a player rebounded while on the floor.", format: (val) => `${(val * 100).toFixed(1)}%` },
  { key: "OREB_PCT", label: "Off. Rebound %", description: "Offensive Rebound Percentage.", format: (val) => `${(val * 100).toFixed(1)}%` },
  { key: "DREB_PCT", label: "Def. Rebound %", description: "Defensive Rebound Percentage.", format: (val) => `${(val * 100).toFixed(1)}%` },
  { key: "PIE", label: "PIE", description: "Player Impact Estimate. Measures a player's overall statistical contribution.", format: (val) => `${(val * 100).toFixed(1)}%` },
  { key: "ORTG", label: "Offensive Rating", description: "Points scored per 100 possessions by the team while the player is on the floor." },
  { key: "DRTG", label: "Defensive Rating", description: "Points allowed per 100 possessions by the team while the player is on the floor." },
  { key: "NETRTG", label: "Net Rating", description: "Point differential per 100 possessions while the player is on the floor." },
  { key: "PER", label: "PER", description: "Player Efficiency Rating. A measure of per-minute production adjusted for pace." },
  { key: "BPM", label: "BPM", description: "Box Plus-Minus. A box score estimate of a player's contribution when on the court." },
  { key: "VORP", label: "VORP", description: "Value Over Replacement Player. Estimates a player's overall contribution in terms of points over a hypothetical 'replacement-level' player." },
  { key: "WS", label: "Win Shares", description: "Estimates a player's contribution to their team in wins." },
];

export function AdvancedMetricsDisplay({ metrics }: AdvancedMetricsDisplayProps) {
  if (!metrics || Object.keys(metrics).length === 0) {
    return <p className="text-sm text-muted-foreground">Advanced metrics data is not available.</p>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">Key Advanced Metrics</CardTitle>
      </CardHeader>
      <CardContent>
        <TooltipProvider>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[180px]">Metric</TableHead>
                <TableHead>Value</TableHead>
                <TableHead className="hidden md:table-cell">Description</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {metricDisplayConfig.map(({ key, label, description, format }) => {
                const value = metrics[key];
                if (value === undefined || value === null) return null;
                const displayValue = typeof value === 'number' 
                  ? (format ? format(value) : value.toFixed(1)) 
                  : String(value);

                return (
                  <TableRow key={key}>
                    <TableCell className="font-medium">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="cursor-help border-b border-dashed border-muted-foreground">{label}</span>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <p>{description}</p>
                        </TooltipContent>
                      </Tooltip>
                    </TableCell>
                    <TableCell>{displayValue}</TableCell>
                    <TableCell className="hidden md:table-cell text-sm text-muted-foreground">{description}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TooltipProvider>
      </CardContent>
    </Card>
  );
} 