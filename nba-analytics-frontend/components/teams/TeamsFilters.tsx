/**
 * TeamsFilters Component
 * Single Responsibility: Handle all filtering and sorting logic for teams
 * Clean separation of concerns
 */

import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Grid3X3, List, TableIcon, BarChart3, GitCompare } from "lucide-react";

type ViewMode = 'grid' | 'list' | 'table' | 'analytics';
type SortOption = 'name' | 'record' | 'offense' | 'defense' | 'pace' | 'playoff-odds';
type FilterStatus = 'all' | 'contender' | 'playoff-push' | 'rebuilding';

interface TeamsFiltersProps {
  // Search and filters
  searchTerm: string;
  onSearchChange: (value: string) => void;
  selectedConference: string;
  onConferenceChange: (value: string) => void;
  filterStatus: FilterStatus;
  onStatusChange: (value: FilterStatus) => void;
  sortBy: SortOption;
  onSortChange: (value: SortOption) => void;
  showOnlyInjuries: boolean;
  onInjuriesToggle: (checked: boolean) => void;
  
  // View mode
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  
  // Season
  currentSeason: string;
  availableSeasons: string[];
  onSeasonChange: (season: string) => void;
  
  // Team selection
  selectedTeams: string[];
  onClearSelection: () => void;
}

export function TeamsFilters({
  searchTerm,
  onSearchChange,
  selectedConference,
  onConferenceChange,
  filterStatus,
  onStatusChange,
  sortBy,
  onSortChange,
  showOnlyInjuries,
  onInjuriesToggle,
  viewMode,
  onViewModeChange,
  currentSeason,
  availableSeasons,
  onSeasonChange,
  selectedTeams,
  onClearSelection
}: TeamsFiltersProps) {
  return (
    <div className="space-y-6">
      {/* Header with View Mode Toggle */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">NBA Teams</h1>
          <p className="text-muted-foreground">Comprehensive team analysis and intelligence</p>
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center gap-4">
          <Label className="text-sm font-medium">View:</Label>
          <RadioGroup
            value={viewMode}
            onValueChange={(value: string) => onViewModeChange(value as ViewMode)}
            className="flex items-center gap-2"
          >
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="grid" id="grid" />
              <Label htmlFor="grid" className="flex items-center gap-1 text-sm">
                <Grid3X3 className="h-4 w-4" />
                Grid
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="list" id="list" />
              <Label htmlFor="list" className="flex items-center gap-1 text-sm">
                <List className="h-4 w-4" />
                List
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="table" id="table" />
              <Label htmlFor="table" className="flex items-center gap-1 text-sm">
                <TableIcon className="h-4 w-4" />
                Table
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="analytics" id="analytics" />
              <Label htmlFor="analytics" className="flex items-center gap-1 text-sm">
                <BarChart3 className="h-4 w-4" />
                Analytics
              </Label>
            </div>
          </RadioGroup>
        </div>
      </div>

      {/* Main Filters */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Search */}
        <Input
          placeholder="Search teams..."
          value={searchTerm}
          onChange={(e) => onSearchChange(e.target.value)}
        />

        {/* Conference Filter */}
        <Select value={selectedConference} onValueChange={onConferenceChange}>
          <SelectTrigger>
            <SelectValue placeholder="Conference" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Conferences</SelectItem>
            <SelectItem value="east">Eastern</SelectItem>
            <SelectItem value="west">Western</SelectItem>
          </SelectContent>
        </Select>

        {/* Status Filter */}
        <Select value={filterStatus} onValueChange={(value) => onStatusChange(value as FilterStatus)}>
          <SelectTrigger>
            <SelectValue placeholder="Team Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Teams</SelectItem>
            <SelectItem value="contender">Contenders</SelectItem>
            <SelectItem value="playoff-push">Playoff Push</SelectItem>
            <SelectItem value="rebuilding">Rebuilding</SelectItem>
          </SelectContent>
        </Select>

        {/* Sort By */}
        <Select value={sortBy} onValueChange={(value) => onSortChange(value as SortOption)}>
          <SelectTrigger>
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="name">Team Name</SelectItem>
            <SelectItem value="record">Win Percentage</SelectItem>
            <SelectItem value="offense">Offensive Rating</SelectItem>
            <SelectItem value="defense">Defensive Rating</SelectItem>
            <SelectItem value="pace">Pace</SelectItem>
            <SelectItem value="playoff-odds">Playoff Odds</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Additional Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center space-x-2">
          <Checkbox
            id="injuries"
            checked={showOnlyInjuries}
            onCheckedChange={(checked) => onInjuriesToggle(checked === true)}
          />
          <Label htmlFor="injuries" className="text-sm">Teams with injuries only</Label>
        </div>

        {selectedTeams.length > 0 && (
          <div className="flex items-center gap-2">
            <Badge variant="secondary">
              {selectedTeams.length} team{selectedTeams.length > 1 ? 's' : ''} selected
            </Badge>
            <Button size="sm" variant="outline" onClick={onClearSelection}>
              Clear
            </Button>
            {selectedTeams.length > 1 && (
              <Button size="sm">
                <GitCompare className="w-4 h-4 mr-2" />
                Compare Teams
              </Button>
            )}
          </div>
        )}

        {/* Season Selector */}
        <div className="flex items-center gap-2 ml-auto">
          <Label htmlFor="season-select" className="text-sm font-medium">Season:</Label>
          <Select value={currentSeason} onValueChange={onSeasonChange}>
            <SelectTrigger id="season-select" className="w-[140px]">
              <SelectValue placeholder="Select Season" />
            </SelectTrigger>
            <SelectContent>
              {availableSeasons.map((season) => (
                <SelectItem key={season} value={season}>{season}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );
}
