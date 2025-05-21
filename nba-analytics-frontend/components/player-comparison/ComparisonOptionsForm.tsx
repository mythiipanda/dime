`use client`;

import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"; // Ensure TabsContent is used if needed, or remove if not
import { seasons } from "@/lib/constants"; // Assuming this contains an array of season strings
import { Grid, Activity, BarChart2 } from "lucide-react"; // BarChart2 for a potential third chart type

interface ComparisonOptionsFormProps {
  season: string;
  onSeasonChange: (value: string) => void;
  seasonType: string;
  onSeasonTypeChange: (value: string) => void;
  chartType: string;
  onChartTypeChange: (value: string) => void;
}

export function ComparisonOptionsForm({
  season,
  onSeasonChange,
  seasonType,
  onSeasonTypeChange,
  chartType,
  onChartTypeChange,
}: ComparisonOptionsFormProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="comp-season">Season</Label>
        <Select value={season} onValueChange={onSeasonChange}>
          <SelectTrigger id="comp-season">
            <SelectValue placeholder="Select season" />
          </SelectTrigger>
          <SelectContent>
            {seasons.map(s => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="comp-season-type">Season Type</Label>
        <Select value={seasonType} onValueChange={onSeasonTypeChange}>
          <SelectTrigger id="comp-season-type">
            <SelectValue placeholder="Select season type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="Regular Season">Regular Season</SelectItem>
            <SelectItem value="Playoffs">Playoffs</SelectItem>
            <SelectItem value="Pre Season">Pre Season</SelectItem> {/* If supported by API */}
            <SelectItem value="All Star">All Star</SelectItem> {/* If supported by API */}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Chart Type</Label>
        <Tabs value={chartType} onValueChange={onChartTypeChange}>
          <TabsList className="grid grid-cols-3 w-full">
            <TabsTrigger value="scatter" className="flex items-center gap-1 text-xs sm:text-sm h-9 sm:h-10">
              <Grid className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">Scatter</span>
              <span className="sm:hidden">Scat.</span>
            </TabsTrigger>
            <TabsTrigger value="heatmap" className="flex items-center gap-1 text-xs sm:text-sm h-9 sm:h-10">
              <Activity className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">Heatmap</span>
              <span className="sm:hidden">Heat.</span>
            </TabsTrigger>
            <TabsTrigger value="hexbin" className="flex items-center gap-1 text-xs sm:text-sm h-9 sm:h-10">
              <BarChart2 className="h-3.5 w-3.5 sm:h-4 sm:w-4" /> {/* Using BarChart2 as a placeholder icon */}
              <span className="hidden sm:inline">Hexbin</span>
              <span className="sm:hidden">Hex.</span>
            </TabsTrigger>
          </TabsList>
          {/* TabsContent can be added here if needed, e.g., for descriptions per chart type */}
        </Tabs>
      </div>
    </div>
  );
} 