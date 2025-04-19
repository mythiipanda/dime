'use client';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react"; // Optional icons for trends

interface StatCardProps {
  label: string;
  value: string | number;
  unit?: string;
  trend?: 'up' | 'down' | 'neutral'; // Optional trend indicator
  className?: string;
}

export default function StatCard({ 
    label,
    value,
    unit,
    trend,
    className 
}: StatCardProps) {

  const renderTrendIcon = () => {
    switch (trend) {
      case 'up':
        return <TrendingUp className="h-4 w-4 text-green-500" />;
      case 'down':
        return <TrendingDown className="h-4 w-4 text-red-500" />;
      case 'neutral':
        return <Minus className="h-4 w-4 text-muted-foreground" />;
      default:
        return null;
    }
  };

  return (
    <Card className={cn("overflow-hidden bg-card/80 backdrop-blur-sm border-border/50", className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {label}
        </CardTitle>
        {renderTrendIcon()} 
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold text-foreground">
          {value} 
          {unit && <span className="text-xs text-muted-foreground ml-1">{unit}</span>}
        </div>
        {/* Optional: Add a small description or comparison below? */}
        {/* <p className="text-xs text-muted-foreground pt-1">+20.1% from last month</p> */}
      </CardContent>
    </Card>
  );
} 