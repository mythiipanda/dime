"use client";

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { BarChart, LineChart, PieChart, DonutChart } from "@tremor/react";
import { cn } from "@/lib/utils";

interface TeamAnalysisProps {
  teamId: string;
  season: string;
}

export function TeamAnalysis({ teamId, season }: TeamAnalysisProps) {
  const [timeframe, setTimeframe] = useState("season");
  
  // This would be fetched from an API in a real implementation
  const shotDistribution = [
    { name: "Restricted Area", value: 28.5 },
    { name: "Paint (Non-RA)", value: 12.3 },
    { name: "Mid-Range", value: 15.7 },
    { name: "Corner 3", value: 10.2 },
    { name: "Above Break 3", value: 33.3 },
  ];
  
  const playTypeData = [
    { name: "Transition", efficiency: 1.21, frequency: 18.5 },
    { name: "Pick & Roll (Ball Handler)", efficiency: 0.92, frequency: 21.2 },
    { name: "Pick & Roll (Roll Man)", efficiency: 1.12, frequency: 8.5 },
    { name: "Post-Up", efficiency: 0.85, frequency: 5.1 },
    { name: "Isolation", efficiency: 0.95, frequency: 9.8 },
    { name: "Spot-Up", efficiency: 1.05, frequency: 22.5 },
    { name: "Handoff", efficiency: 0.98, frequency: 5.2 },
    { name: "Cut", efficiency: 1.32, frequency: 7.2 },
    { name: "Off Screen", efficiency: 1.08, frequency: 6.5 },
    { name: "Putbacks", efficiency: 1.15, frequency: 3.5 },
  ];
  
  const performanceTrend = [
    { date: "Oct", offRtg: 112.5, defRtg: 110.2, netRtg: 2.3 },
    { date: "Nov", offRtg: 114.8, defRtg: 109.5, netRtg: 5.3 },
    { date: "Dec", offRtg: 116.2, defRtg: 111.8, netRtg: 4.4 },
    { date: "Jan", offRtg: 115.5, defRtg: 112.5, netRtg: 3.0 },
    { date: "Feb", offRtg: 118.2, defRtg: 113.4, netRtg: 4.8 },
    { date: "Mar", offRtg: 117.5, defRtg: 112.8, netRtg: 4.7 },
  ];
  
  const fourFactors = {
    offense: {
      efg: { value: 56.2, rank: 4 },
      tov: { value: 12.5, rank: 6 },
      orb: { value: 25.8, rank: 15 },
      ftRate: { value: 22.1, rank: 27 },
    },
    defense: {
      efg: { value: 53.8, rank: 12 },
      tov: { value: 13.5, rank: 18 },
      drb: { value: 72.4, rank: 22 },
      ftRate: { value: 24.5, rank: 15 },
    }
  };
  
  const lineupData = [
    { name: "Starters", minutes: 450, netRtg: 8.5 },
    { name: "Bench", minutes: 280, netRtg: -3.3 },
    { name: "Closing", minutes: 120, netRtg: 5.4 },
    { name: "Small Ball", minutes: 180, netRtg: 5.2 },
    { name: "Defensive", minutes: 150, netRtg: 7.1 },
  ];
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Advanced Analysis</h2>
        <Select value={timeframe} onValueChange={setTimeframe}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Select timeframe" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="season">Full Season</SelectItem>
            <SelectItem value="last10">Last 10 Games</SelectItem>
            <SelectItem value="last20">Last 20 Games</SelectItem>
            <SelectItem value="home">Home Games</SelectItem>
            <SelectItem value="away">Away Games</SelectItem>
          </SelectContent>
        </Select>
      </div>
      
      <Tabs defaultValue="four-factors" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="four-factors">Four Factors</TabsTrigger>
          <TabsTrigger value="shot-distribution">Shot Distribution</TabsTrigger>
          <TabsTrigger value="play-types">Play Types</TabsTrigger>
          <TabsTrigger value="trends">Performance Trends</TabsTrigger>
        </TabsList>
        
        <TabsContent value="four-factors" className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Offensive Four Factors</CardTitle>
                <CardDescription>Key metrics that determine offensive efficiency</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  <FourFactorBar 
                    label="Effective FG%" 
                    value={fourFactors.offense.efg.value} 
                    rank={fourFactors.offense.efg.rank}
                    max={65}
                    higherIsBetter={true}
                  />
                  <FourFactorBar 
                    label="Turnover Rate" 
                    value={fourFactors.offense.tov.value} 
                    rank={fourFactors.offense.tov.rank}
                    max={20}
                    higherIsBetter={false}
                  />
                  <FourFactorBar 
                    label="Offensive Rebound %" 
                    value={fourFactors.offense.orb.value} 
                    rank={fourFactors.offense.orb.rank}
                    max={40}
                    higherIsBetter={true}
                  />
                  <FourFactorBar 
                    label="Free Throw Rate" 
                    value={fourFactors.offense.ftRate.value} 
                    rank={fourFactors.offense.ftRate.rank}
                    max={40}
                    higherIsBetter={true}
                  />
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>Defensive Four Factors</CardTitle>
                <CardDescription>Key metrics that determine defensive efficiency</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  <FourFactorBar 
                    label="Opponent eFG%" 
                    value={fourFactors.defense.efg.value} 
                    rank={fourFactors.defense.efg.rank}
                    max={65}
                    higherIsBetter={false}
                  />
                  <FourFactorBar 
                    label="Opponent Turnover Rate" 
                    value={fourFactors.defense.tov.value} 
                    rank={fourFactors.defense.tov.rank}
                    max={20}
                    higherIsBetter={true}
                  />
                  <FourFactorBar 
                    label="Defensive Rebound %" 
                    value={fourFactors.defense.drb.value} 
                    rank={fourFactors.defense.drb.rank}
                    max={90}
                    higherIsBetter={true}
                  />
                  <FourFactorBar 
                    label="Opponent Free Throw Rate" 
                    value={fourFactors.defense.ftRate.value} 
                    rank={fourFactors.defense.ftRate.rank}
                    max={40}
                    higherIsBetter={false}
                  />
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
        
        <TabsContent value="shot-distribution" className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Shot Distribution</CardTitle>
                <CardDescription>Breakdown of shot attempts by location</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <DonutChart
                    data={shotDistribution}
                    category="value"
                    index="name"
                    valueFormatter={(number: number) => `${number.toFixed(1)}%`}
                    colors={["blue", "cyan", "indigo", "violet", "fuchsia"]}
                    className="h-full"
                  />
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>Shot Distribution Analysis</CardTitle>
                <CardDescription>Detailed breakdown of shooting locations</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <div className="flex items-center">
                        <div className="w-3 h-3 rounded-full bg-blue-500 mr-2"></div>
                        <span>Restricted Area</span>
                      </div>
                      <span className="font-medium">28.5%</span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      67.5% FG (5th in NBA) | +2.3% vs League Avg
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <div className="flex items-center">
                        <div className="w-3 h-3 rounded-full bg-cyan-500 mr-2"></div>
                        <span>Paint (Non-RA)</span>
                      </div>
                      <span className="font-medium">12.3%</span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      42.8% FG (12th in NBA) | -0.5% vs League Avg
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <div className="flex items-center">
                        <div className="w-3 h-3 rounded-full bg-indigo-500 mr-2"></div>
                        <span>Mid-Range</span>
                      </div>
                      <span className="font-medium">15.7%</span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      44.2% FG (8th in NBA) | +2.1% vs League Avg
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <div className="flex items-center">
                        <div className="w-3 h-3 rounded-full bg-violet-500 mr-2"></div>
                        <span>Corner 3</span>
                      </div>
                      <span className="font-medium">10.2%</span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      39.8% FG (4th in NBA) | +3.2% vs League Avg
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <div className="flex items-center">
                        <div className="w-3 h-3 rounded-full bg-fuchsia-500 mr-2"></div>
                        <span>Above Break 3</span>
                      </div>
                      <span className="font-medium">33.3%</span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      37.5% FG (3rd in NBA) | +2.8% vs League Avg
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
        
        <TabsContent value="play-types" className="pt-6">
          <Card>
            <CardHeader>
              <CardTitle>Play Type Analysis</CardTitle>
              <CardDescription>Efficiency and frequency of different play types</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-96">
                <BarChart
                  data={playTypeData}
                  index="name"
                  categories={["efficiency"]}
                  colors={["blue"]}
                  valueFormatter={(number: number) => `${number.toFixed(2)} PPP`}
                  yAxisWidth={48}
                  className="h-full"
                />
              </div>
              
              <div className="mt-8 space-y-4">
                <h4 className="font-medium text-sm">Play Type Breakdown</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {playTypeData.map((playType, i) => (
                    <div key={i} className="flex justify-between items-center border-b pb-2">
                      <div>
                        <div className="font-medium">{playType.name}</div>
                        <div className="text-xs text-muted-foreground">
                          {playType.frequency.toFixed(1)}% frequency
                        </div>
                      </div>
                      <div className={cn(
                        "text-right",
                        playType.efficiency > 1.0 ? "text-green-600" : "text-red-600"
                      )}>
                        <div className="font-medium">{playType.efficiency.toFixed(2)} PPP</div>
                        <div className="text-xs">
                          {playType.efficiency > 1.0 ? "Above" : "Below"} Average
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="trends" className="pt-6">
          <div className="grid grid-cols-1 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Performance Trends</CardTitle>
                <CardDescription>Monthly offensive and defensive rating trends</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <LineChart
                    data={performanceTrend}
                    index="date"
                    categories={["offRtg", "defRtg", "netRtg"]}
                    colors={["green", "red", "blue"]}
                    valueFormatter={(number: number) => `${number.toFixed(1)}`}
                    yAxisWidth={48}
                    className="h-full"
                  />
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>Lineup Performance</CardTitle>
                <CardDescription>Net rating by lineup type and minutes played</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <BarChart
                    data={lineupData}
                    index="name"
                    categories={["netRtg"]}
                    colors={["blue"]}
                    valueFormatter={(number: number) => `${number.toFixed(1)}`}
                    yAxisWidth={48}
                    className="h-full"
                  />
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function FourFactorBar({ 
  label, 
  value, 
  rank, 
  max,
  higherIsBetter
}: { 
  label: string; 
  value: number; 
  rank: number;
  max: number;
  higherIsBetter: boolean;
}) {
  const percentage = (value / max) * 100;
  const isGoodRank = rank <= 10;
  const rankColor = isGoodRank ? "text-green-600" : rank <= 20 ? "text-amber-600" : "text-red-600";
  
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span>{label}</span>
        <div className="flex items-center gap-2">
          <span className="font-medium">{value.toFixed(1)}%</span>
          <span className={cn("text-xs", rankColor)}>
            #{rank} in NBA
          </span>
        </div>
      </div>
      <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
        <div 
          className={cn(
            "h-full",
            (higherIsBetter && isGoodRank) || (!higherIsBetter && isGoodRank) ? "bg-green-500" : 
            (higherIsBetter && rank <= 20) || (!higherIsBetter && rank <= 20) ? "bg-amber-500" : "bg-red-500"
          )} 
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
    </div>
  );
} 