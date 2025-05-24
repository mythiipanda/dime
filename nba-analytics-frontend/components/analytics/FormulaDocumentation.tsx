"use client";

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { 
  ChevronDown, 
  ChevronRight, 
  Calculator, 
  Target, 
  Activity, 
  Users, 
  TrendingUp,
  Brain,
  BookOpen,
  ExternalLink
} from "lucide-react";
import { cn } from "@/lib/utils";

interface FormulaItem {
  name: string;
  category: string;
  formula: string;
  description: string;
  variables: { symbol: string; description: string }[];
  example?: string;
  source?: string;
  complexity: 'Basic' | 'Intermediate' | 'Advanced' | 'Expert';
}

const formulas: FormulaItem[] = [
  {
    name: "RAPTOR (Offensive)",
    category: "Impact Metrics",
    formula: "RAPTOR_OFF = (Shooting_Impact + Playmaking_Impact + Rebounding_Impact) × Minutes_Weight + Position_Adjustment",
    description: "FiveThirtyEight's Robust Algorithm using Player Tracking and On/Off Ratings - Offensive component",
    variables: [
      { symbol: "Shooting_Impact", description: "(TS% - League_Avg_TS%) × FGA × 0.02" },
      { symbol: "Playmaking_Impact", description: "(AST_Ratio × 2 - TOV_Ratio) × Usage_Rate × 10" },
      { symbol: "Rebounding_Impact", description: "(REB_Rate - Expected_REB) × 0.1" },
      { symbol: "Minutes_Weight", description: "min(1.0, Minutes_Played / 2000)" },
      { symbol: "Position_Adjustment", description: "Position-specific offensive adjustment" }
    ],
    example: "For a PG with 58% TS, 25% AST ratio, 12% TOV ratio, 30% usage: RAPTOR_OFF ≈ 2.1",
    source: "FiveThirtyEight",
    complexity: "Expert"
  },
  {
    name: "EPM (Estimated Plus-Minus)",
    category: "Impact Metrics",
    formula: "EPM = Box_Score_Component + Tracking_Component + Team_Context_Adjustment",
    description: "Dunks and Threes' Estimated Plus-Minus model combining box score and tracking data",
    variables: [
      { symbol: "Box_Score_Component", description: "Traditional stats weighted by impact" },
      { symbol: "Tracking_Component", description: "Player tracking data (spacing, defense, etc.)" },
      { symbol: "Team_Context_Adjustment", description: "Adjustment for team strength and context" }
    ],
    example: "Elite player might have EPM of +5.2 (top 5% of league)",
    source: "Dunks and Threes",
    complexity: "Expert"
  },
  {
    name: "True Shooting Percentage",
    category: "Shooting",
    formula: "TS% = PTS / (2 × (FGA + 0.44 × FTA))",
    description: "Measures shooting efficiency accounting for 2-pointers, 3-pointers, and free throws",
    variables: [
      { symbol: "PTS", description: "Total points scored" },
      { symbol: "FGA", description: "Field goal attempts" },
      { symbol: "FTA", description: "Free throw attempts" },
      { symbol: "0.44", description: "Estimated free throws that end possessions" }
    ],
    example: "Player with 20 PTS on 15 FGA and 4 FTA: TS% = 20 / (2 × (15 + 0.44 × 4)) = 58.8%",
    source: "Basketball Reference",
    complexity: "Basic"
  },
  {
    name: "Player Efficiency Rating (PER)",
    category: "Overall Performance",
    formula: "PER = (Positive_Stats - Negative_Stats) / Minutes × Pace_Adjustment × League_Adjustment",
    description: "John Hollinger's all-in-one basketball rating that attempts to boil down all of a player's contributions",
    variables: [
      { symbol: "Positive_Stats", description: "Points, rebounds, assists, steals, blocks" },
      { symbol: "Negative_Stats", description: "Turnovers, missed shots, personal fouls" },
      { symbol: "Pace_Adjustment", description: "Adjustment for team pace" },
      { symbol: "League_Adjustment", description: "Scaled so league average = 15.0" }
    ],
    example: "League average PER = 15.0, All-Star level ≈ 20+, MVP level ≈ 25+",
    source: "ESPN/John Hollinger",
    complexity: "Intermediate"
  },
  {
    name: "Usage Rate",
    category: "Playmaking",
    formula: "USG% = 100 × ((FGA + 0.44 × FTA + TOV) × (Team_Minutes / 5)) / (Minutes × (Team_FGA + 0.44 × Team_FTA + Team_TOV))",
    description: "Estimates the percentage of team plays used by a player while on the floor",
    variables: [
      { symbol: "FGA", description: "Player field goal attempts" },
      { symbol: "FTA", description: "Player free throw attempts" },
      { symbol: "TOV", description: "Player turnovers" },
      { symbol: "Team_Minutes", description: "Total team minutes (240 for regulation)" },
      { symbol: "Minutes", description: "Player minutes played" }
    ],
    example: "20% usage = role player, 25% = secondary star, 30%+ = primary option",
    source: "Basketball Reference",
    complexity: "Intermediate"
  },
  {
    name: "Offensive Rating",
    category: "Team Metrics",
    formula: "ORtg = (Points Scored / Possessions) × 100",
    description: "Points scored per 100 possessions",
    variables: [
      { symbol: "Points Scored", description: "Total points scored by team" },
      { symbol: "Possessions", description: "Estimated team possessions" }
    ],
    example: "League average ≈ 112, Elite offense ≈ 118+",
    source: "Dean Oliver",
    complexity: "Basic"
  },
  {
    name: "Defensive Rating",
    category: "Team Metrics",
    formula: "DRtg = (Points Allowed / Possessions) × 100",
    description: "Points allowed per 100 possessions",
    variables: [
      { symbol: "Points Allowed", description: "Total points allowed by team" },
      { symbol: "Possessions", description: "Estimated opponent possessions" }
    ],
    example: "League average ≈ 112, Elite defense ≈ 108 or lower",
    source: "Dean Oliver",
    complexity: "Basic"
  },
  {
    name: "Four Factors (Offensive)",
    category: "Team Metrics",
    formula: "eFG% × 0.4 + TOV% × 0.25 + OREB% × 0.2 + FTR × 0.15",
    description: "Dean Oliver's four factors that determine offensive success, weighted by importance",
    variables: [
      { symbol: "eFG%", description: "Effective Field Goal Percentage" },
      { symbol: "TOV%", description: "Turnover Rate (lower is better)" },
      { symbol: "OREB%", description: "Offensive Rebound Percentage" },
      { symbol: "FTR", description: "Free Throw Rate (FTA/FGA)" }
    ],
    example: "Elite offense typically excels in 3+ factors",
    source: "Dean Oliver",
    complexity: "Intermediate"
  },
  {
    name: "Win Shares",
    category: "Overall Performance",
    formula: "WS = Offensive_WS + Defensive_WS",
    description: "Estimates the number of wins contributed by a player",
    variables: [
      { symbol: "Offensive_WS", description: "Based on offensive rating and possessions used" },
      { symbol: "Defensive_WS", description: "Based on defensive rating and possessions defended" }
    ],
    example: "10+ WS = All-Star level, 15+ WS = MVP candidate",
    source: "Basketball Reference",
    complexity: "Advanced"
  },
  {
    name: "Box Plus/Minus (BPM)",
    category: "Impact Metrics",
    formula: "BPM = Offensive_BPM + Defensive_BPM",
    description: "Estimates a player's contribution per 100 possessions relative to league average",
    variables: [
      { symbol: "Offensive_BPM", description: "Based on offensive box score stats" },
      { symbol: "Defensive_BPM", description: "Based on defensive box score stats and team defense" }
    ],
    example: "0 = league average, +5 = All-Star, +8 = MVP level",
    source: "Basketball Reference",
    complexity: "Advanced"
  }
];

export function FormulaDocumentation() {
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [expandedFormulas, setExpandedFormulas] = useState<Set<string>>(new Set());

  const categories = ["all", ...Array.from(new Set(formulas.map(f => f.category)))];

  const filteredFormulas = selectedCategory === "all" 
    ? formulas 
    : formulas.filter(f => f.category === selectedCategory);

  const toggleFormula = (formulaName: string) => {
    const newExpanded = new Set(expandedFormulas);
    if (newExpanded.has(formulaName)) {
      newExpanded.delete(formulaName);
    } else {
      newExpanded.add(formulaName);
    }
    setExpandedFormulas(newExpanded);
  };

  const getComplexityColor = (complexity: string) => {
    switch (complexity) {
      case 'Basic': return 'bg-green-100 text-green-800';
      case 'Intermediate': return 'bg-yellow-100 text-yellow-800';
      case 'Advanced': return 'bg-orange-100 text-orange-800';
      case 'Expert': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'Impact Metrics': return <Target className="w-4 h-4" />;
      case 'Shooting': return <Activity className="w-4 h-4" />;
      case 'Team Metrics': return <Users className="w-4 h-4" />;
      case 'Overall Performance': return <TrendingUp className="w-4 h-4" />;
      case 'Playmaking': return <Brain className="w-4 h-4" />;
      default: return <Calculator className="w-4 h-4" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-blue-500" />
            Formula Documentation
          </h2>
          <Badge variant="secondary" className="text-xs">
            {filteredFormulas.length} formulas
          </Badge>
        </div>
      </div>

      {/* Category Filter */}
      <div className="flex flex-wrap gap-2">
        {categories.map((category) => (
          <Button
            key={category}
            variant={selectedCategory === category ? "default" : "outline"}
            size="sm"
            onClick={() => setSelectedCategory(category)}
            className="flex items-center gap-2"
          >
            {category !== "all" && getCategoryIcon(category)}
            {category === "all" ? "All Categories" : category}
          </Button>
        ))}
      </div>

      {/* Formulas List */}
      <div className="space-y-4">
        {filteredFormulas.map((formula) => (
          <Card key={formula.name} className="overflow-hidden">
            <Collapsible
              open={expandedFormulas.has(formula.name)}
              onOpenChange={() => toggleFormula(formula.name)}
            >
              <CollapsibleTrigger asChild>
                <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {getCategoryIcon(formula.category)}
                      <div>
                        <CardTitle className="text-lg">{formula.name}</CardTitle>
                        <CardDescription>{formula.description}</CardDescription>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge className={getComplexityColor(formula.complexity)}>
                        {formula.complexity}
                      </Badge>
                      <Badge variant="outline">{formula.category}</Badge>
                      {expandedFormulas.has(formula.name) ? (
                        <ChevronDown className="w-4 h-4" />
                      ) : (
                        <ChevronRight className="w-4 h-4" />
                      )}
                    </div>
                  </div>
                </CardHeader>
              </CollapsibleTrigger>
              
              <CollapsibleContent>
                <CardContent className="pt-0">
                  <div className="space-y-4">
                    {/* Formula */}
                    <div>
                      <h4 className="font-semibold mb-2">Formula</h4>
                      <div className="bg-muted p-3 rounded-lg font-mono text-sm">
                        {formula.formula}
                      </div>
                    </div>

                    {/* Variables */}
                    <div>
                      <h4 className="font-semibold mb-2">Variables</h4>
                      <div className="space-y-2">
                        {formula.variables.map((variable, index) => (
                          <div key={index} className="flex gap-3">
                            <code className="bg-muted px-2 py-1 rounded text-sm font-mono min-w-fit">
                              {variable.symbol}
                            </code>
                            <span className="text-sm text-muted-foreground">
                              {variable.description}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Example */}
                    {formula.example && (
                      <div>
                        <h4 className="font-semibold mb-2">Example</h4>
                        <div className="bg-blue-50 p-3 rounded-lg text-sm">
                          {formula.example}
                        </div>
                      </div>
                    )}

                    {/* Source */}
                    {formula.source && (
                      <div className="flex items-center justify-between pt-2 border-t">
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <span>Source:</span>
                          <span className="font-medium">{formula.source}</span>
                        </div>
                        <Button variant="ghost" size="sm">
                          <ExternalLink className="w-3 h-3 mr-1" />
                          Learn More
                        </Button>
                      </div>
                    )}
                  </div>
                </CardContent>
              </CollapsibleContent>
            </Collapsible>
          </Card>
        ))}
      </div>

      {/* Summary Stats */}
      <Card>
        <CardHeader>
          <CardTitle>Formula Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {formulas.filter(f => f.complexity === 'Basic').length}
              </div>
              <div className="text-sm text-muted-foreground">Basic</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-600">
                {formulas.filter(f => f.complexity === 'Intermediate').length}
              </div>
              <div className="text-sm text-muted-foreground">Intermediate</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600">
                {formulas.filter(f => f.complexity === 'Advanced').length}
              </div>
              <div className="text-sm text-muted-foreground">Advanced</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">
                {formulas.filter(f => f.complexity === 'Expert').length}
              </div>
              <div className="text-sm text-muted-foreground">Expert</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
